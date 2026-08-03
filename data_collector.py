import cv2
import os
import numpy as np
from ultralytics import YOLO

# Setup directories for the micro-classification dataset
DATA_DIR = "dataset"
CATEGORIES = {
    "faces": ["smile", "neutral"],
    "hands": ["thumbs_up", "random_hand"]
}

for parent, subdirs in CATEGORIES.items():
    for sub in subdirs:
        os.makedirs(os.path.join(DATA_DIR, parent, sub), exist_ok=True)

print("Loading YOLOv8n-pose...")
model = YOLO('yolov8n-pose.pt')
cap = cv2.VideoCapture(1)

print("\n=======================================================")
print("  Micro-Classification Dataset Collector")
print("=======================================================")
print(" Controls:")
print("   [S] - Save Face Crop as SMILE")
print("   [N] - Save Face Crop as NEUTRAL")
print("   [T] - Save Hand Crop as THUMBS UP")
print("   [H] - Save Hand Crop as RANDOM HAND")
print("   [Q] - Quit")
print("=======================================================\n")

# Counters for saved images
counters = {
    "smile": len(os.listdir(os.path.join(DATA_DIR, "faces", "smile"))),
    "neutral": len(os.listdir(os.path.join(DATA_DIR, "faces", "neutral"))),
    "thumbs_up": len(os.listdir(os.path.join(DATA_DIR, "hands", "thumbs_up"))),
    "random_hand": len(os.listdir(os.path.join(DATA_DIR, "hands", "random_hand")))
}

def extract_crop(frame, cx, cy, size=100):
    """Extract a bounded low-quality crop around a center point"""
    h, w = frame.shape[:2]
    x1, y1 = max(0, int(cx - size/2)), max(0, int(cy - size/2))
    x2, y2 = min(w, int(cx + size/2)), min(h, int(cy + size/2))
    crop = frame[y1:y2, x1:x2]
    if crop.size > 0:
        return cv2.resize(crop, (size, size))
    return None

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    
    display = frame.copy()
    h, w = frame.shape[:2]
    
    results = model.track(frame, persist=True, verbose=False)
    
    face_crop = None
    hand_crop = None
    
    if len(results) > 0 and results[0].keypoints is not None:
        boxes = results[0].boxes
        kpts = results[0].keypoints.data.cpu().numpy()
        
        for i in range(len(boxes)):
            if int(boxes.cls[i].item()) != 0: continue # Only track persons
            
            pts = kpts[i]
            if len(pts) >= 11:
                # Face tracking (using nose)
                nx, ny, nc = pts[0]
                if nc > 0.5:
                    cv2.circle(display, (int(nx), int(ny)), 50, (0, 255, 0), 2)
                    cv2.putText(display, "Face Zone", (int(nx)-40, int(ny)-60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    face_crop = extract_crop(frame, nx, ny, 100)
                
                # Hand tracking (using wrists - pick the highest confidence one)
                lwx, lwy, lwc = pts[9]
                rwx, rwy, rwc = pts[10]
                
                best_wrist = None
                if lwc > 0.5 and rwc > 0.5:
                    # If both visible, pick the one raised higher (lower Y value)
                    best_wrist = (lwx, lwy) if lwy < rwy else (rwx, rwy)
                elif lwc > 0.5: best_wrist = (lwx, lwy)
                elif rwc > 0.5: best_wrist = (rwx, rwy)
                
                if best_wrist:
                    wx, wy = best_wrist
                    # Offset slightly to grab the hand instead of just the wrist joint
                    cv2.circle(display, (int(wx), int(wy - 40)), 60, (255, 100, 0), 2)
                    cv2.putText(display, "Hand Zone", (int(wx)-40, int(wy)-110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 2)
                    hand_crop = extract_crop(frame, wx, wy - 40, 120)
            break # Just use the first person found for dataset collection

    # Show live counts
    stats = f"S:{counters['smile']} | N:{counters['neutral']} | T:{counters['thumbs_up']} | H:{counters['random_hand']}"
    cv2.putText(display, stats, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Show preview windows of what is actually being extracted!
    if face_crop is not None:
        cv2.imshow("Face Crop (100x100)", face_crop)
    if hand_crop is not None:
        cv2.imshow("Hand Crop (120x120)", hand_crop)
        
    cv2.imshow("Dataset Collector", display)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s') and face_crop is not None:
        path = os.path.join(DATA_DIR, "faces", "smile", f"smile_{counters['smile']}.jpg")
        cv2.imwrite(path, face_crop)
        counters['smile'] += 1
        print(f"Saved -> {path}")
    elif key == ord('n') and face_crop is not None:
        path = os.path.join(DATA_DIR, "faces", "neutral", f"neutral_{counters['neutral']}.jpg")
        cv2.imwrite(path, face_crop)
        counters['neutral'] += 1
        print(f"Saved -> {path}")
    elif key == ord('t') and hand_crop is not None:
        path = os.path.join(DATA_DIR, "hands", "thumbs_up", f"thumb_{counters['thumbs_up']}.jpg")
        cv2.imwrite(path, hand_crop)
        counters['thumbs_up'] += 1
        print(f"Saved -> {path}")
    elif key == ord('h') and hand_crop is not None:
        path = os.path.join(DATA_DIR, "hands", "random_hand", f"hand_{counters['random_hand']}.jpg")
        cv2.imwrite(path, hand_crop)
        counters['random_hand'] += 1
        print(f"Saved -> {path}")

cap.release()
cv2.destroyAllWindows()
