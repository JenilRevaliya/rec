import cv2
import time
import numpy as np
import sys
import os

# Add edge-node to path to use REC's core modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'edge-node'))

from ultralytics import YOLO
from orchestrator.utils.aspect_framing import compute_framing_box, compute_composition_score, compute_bbox_iou
from orchestrator.intelligence.smile_detector import SmileDetector

def main():
    print("Loading YOLOv8n-pose engine...")
    model = YOLO('yolov8n-pose.pt')
    smile_detector = SmileDetector(confidence_threshold=0.35)

    print("Opening Webcam 1...")
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Webcam 1 failed to open. Trying Webcam 0 instead...")
        cap = cv2.VideoCapture(0)

    # Let the webcam warm up
    time.sleep(1.0)
    
    display_frame = None
    last_optimal_bboxes = {}  # Store last optimal box per track_id
    cooldown_frames = 0
    
    print("\n--- REC CAPTURE DEBUGGER ---")
    print("Press Ctrl+C in this terminal to quit.")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame.")
                break
                
            # Run YOLO inference with tracking
            results = model.track(frame, persist=True, verbose=False)
            
            # Base layer is raw webcam feed
            display_frame = frame.copy()
            h, w = display_frame.shape[:2]
            
            optimal_found = False
            
            if cooldown_frames > 0:
                cooldown_frames -= 1
            
            for result in results:
                boxes = result.boxes
                keypoints = result.keypoints
                
                if boxes is None or len(boxes) == 0:
                    continue
                    
                for i in range(len(boxes)):
                    # Check if object is person (class 0 in COCO)
                    if int(boxes.cls[i].item()) != 0:
                        continue
                        
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                    conf = boxes.conf[i].item()
                    track_id = int(boxes.id[i].item()) if boxes.id is not None else i
                    
                    if conf < 0.5:
                        continue
                        
                    kpts = keypoints.data[i].cpu().numpy() if keypoints is not None else None
                    
                    # 1. Always show white square box on the face
                    if kpts is not None and len(kpts) >= 5:
                        nx, ny, nc = kpts[0]
                        lx, ly, lc = kpts[1]
                        rx, ry, rc = kpts[2]
                        
                        if nc > 0.2:
                            if lc > 0.2 and rc > 0.2:
                                eye_dist = np.sqrt((rx - lx)**2 + (ry - ly)**2)
                            else:
                                eye_dist = (x2 - x1) * 0.22
                                
                            face_size = max(40, eye_dist * 2.8)
                            fx1 = int(nx - face_size/2)
                            fy1 = int(ny - face_size/2)
                            fx2 = int(nx + face_size/2)
                            fy2 = int(ny + face_size/2)
                            
                            cv2.rectangle(display_frame, (fx1, fy1), (fx2, fy2), (255, 255, 255), 2)
                            cv2.putText(display_frame, "Face", (fx1, fy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    else:
                        pw = x2 - x1
                        ph = y2 - y1
                        fx1 = int(x1 + pw*0.3)
                        fy1 = int(y1 + ph*0.1)
                        fx2 = int(x1 + pw*0.7)
                        fy2 = int(y1 + ph*0.35)
                        cv2.rectangle(display_frame, (fx1, fy1), (fx2, fy2), (255, 255, 255), 2)
                        cv2.putText(display_frame, "Face", (fx1, fy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # 2. Compute the dynamic aspect framing box (testing 4:3 landscape)
                    fb = compute_framing_box(
                        [int(x1), int(y1), int(x2), int(y2)], w, h, 
                        aspect_ratio="4:3", framing_scale="AUTO", 
                        keypoints=kpts
                    )
                    
                    # 3. Evaluate Composition Quality
                    comp_score = compute_composition_score([int(x1), int(y1), int(x2), int(y2)], fb, kpts)
                    
                    # 4. Evaluate Smile
                    is_smiling, s_score, _ = smile_detector.evaluate(frame, [int(x1), int(y1), int(x2), int(y2)], kpts)
                    
                    # Define "Optimal Capturing Frame" Criteria
                    is_optimal = (comp_score >= 0.70)
                    
                    if cooldown_frames > 0:
                        is_optimal = False
                        
                    alerts = []
                    
                    # Size Check (Move near/far)
                    fill = ((x2 - x1) * (y2 - y1)) / (w * h)
                    if fill < 0.15:
                        alerts.append("MOVE NEAR (Too Far)")
                        is_optimal = False
                    elif fill > 0.65:
                        alerts.append("MOVE BACK (Too Close)")
                        is_optimal = False
                        
                    # Frontal Face Check
                    is_frontal = False
                    if kpts is not None and len(kpts) >= 5:
                        nx, ny, nc = kpts[0]
                        lx, ly, lc = kpts[1]
                        rx, ry, rc = kpts[2]
                        if nc > 0.2 and lc > 0.2 and rc > 0.2:
                            is_frontal = True
                            
                    if not is_frontal:
                        alerts.append("REJECTED: Face Not Frontal")
                        is_optimal = False
                    
                    # Cutoff Rejection: Reject if subject touches frame edges
                    if x1 <= 5 or y1 <= 5 or x2 >= w - 5:
                        alerts.append("REJECTED: Cut Off Frame")
                        is_optimal = False
                    
                    # Pose Gate: Block optimal if pose hasn't changed since last optimal
                    if is_optimal:
                        old_box = last_optimal_bboxes.get(track_id)
                        if old_box is not None:
                            iou = compute_bbox_iou([int(x1), int(y1), int(x2), int(y2)], old_box)
                            if iou > 0.60:
                                is_optimal = False
                                alerts.append(f"BLOCKED: ID {track_id} Change Pose!")
                            else:
                                last_optimal_bboxes[track_id] = [int(x1), int(y1), int(x2), int(y2)]
                        else:
                            last_optimal_bboxes[track_id] = [int(x1), int(y1), int(x2), int(y2)]
                            
                    if is_optimal:
                        alerts.append("OPTIMAL: CAPTURING!")
                    
                    # Draw Sky Blue squashed ellipse on visible body with 30% opacity
                    overlay = display_frame.copy()
                    center_oval = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                    axes = (int((x2 - x1) * 0.35), int((y2 - y1) / 2)) # Squashed width for body
                    sky_blue = (235, 206, 135)
                    # Filled ellipse on overlay
                    cv2.ellipse(overlay, center_oval, axes, 0, 0, 360, sky_blue, -1)
                    # Alpha blend overlay with main frame (30% visibility)
                    cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)
                    # Solid outline on main frame for sharpness
                    cv2.ellipse(display_frame, center_oval, axes, 0, 0, 360, sky_blue, 2)
                    
                    if is_frontal:
                        # 5. Plotted Box Layer (Green if optimal, Red if not)
                        box_color = (0, 255, 0) if is_optimal else (0, 0, 255)
                        cv2.rectangle(display_frame, (fb[0], fb[1]), (fb[2], fb[3]), box_color, 4)
                        
                        # Draw 9-box grid inside the framing box
                        fb_w = max(1, fb[2] - fb[0])
                        fb_h = max(1, fb[3] - fb[1])
                        cell_w = fb_w // 3
                        cell_h = fb_h // 3
                        
                        cv2.line(display_frame, (fb[0] + cell_w, fb[1]), (fb[0] + cell_w, fb[3]), box_color, 1)
                        cv2.line(display_frame, (fb[0] + 2*cell_w, fb[1]), (fb[0] + 2*cell_w, fb[3]), box_color, 1)
                        cv2.line(display_frame, (fb[0], fb[1] + cell_h), (fb[2], fb[1] + cell_h), box_color, 1)
                        cv2.line(display_frame, (fb[0], fb[1] + 2*cell_h), (fb[2], fb[1] + 2*cell_h), box_color, 1)
                        
                        box_num = 1
                        for row in range(3):
                            for col in range(3):
                                text_x = fb[0] + col * cell_w + int(cell_w / 2) - 10
                                text_y = fb[1] + row * cell_h + int(cell_h / 2) + 10
                                cv2.putText(display_frame, str(box_num), (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)
                                box_num += 1
                    # Overlays (Stacked Alerts)
                    total_alert_height = len(alerts) * 25
                    if fb[1] - total_alert_height < 10:
                        # Not enough space above, print inside the box downwards
                        y_offset = fb[1] + 25
                        y_step = 25
                    else:
                        # Space above, print upwards
                        y_offset = fb[1] - 15
                        y_step = -25

                    for alert in reversed(alerts):
                        color = (0, 255, 0) if "OPTIMAL" in alert else (0, 0, 255)
                        if "BLOCKED" in alert or "MOVE" in alert:
                            color = (0, 165, 255)  # Orange
                        cv2.putText(display_frame, alert, (fb[0] + 5, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        y_offset += y_step
                        
                    if is_frontal:
                        cv2.putText(display_frame, f"Comp Score: {comp_score:.2f}", (fb[0], fb[3] + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
                        if is_smiling:
                            cv2.putText(display_frame, f"SMILE!", (fb[0] + 180, fb[3] + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)
                        
                    if is_optimal:
                        optimal_found = True
                        
            cv2.imshow("REC Capture Debugger (Red=Bad, Green=Optimal)", display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("Quitting by user request...")
                break
            
            if optimal_found:
                print("\n[!] Optimal frame found! Pausing display for 2 seconds...")
                
                # Display the optimal frame frozen for 2 seconds
                pause_end_time = time.time() + 2.0
                while time.time() < pause_end_time:
                    cv2.imshow("REC Capture Debugger (Red=Bad, Green=Optimal)", display_frame)
                    key = cv2.waitKey(30) & 0xFF
                    if key == ord('q') or key == ord('Q'):
                        print("Quitting by user request...")
                        sys.exit(0)
                
                print("[!] Auto-resuming video feed...")
                # Add a cooldown so it doesn't instantly re-trigger from old buffered frames
                cooldown_frames = 15
                
    except KeyboardInterrupt:
        print("\n[!] Shutting down cleanly by user request...")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
