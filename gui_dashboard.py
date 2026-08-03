import sys
import cv2
import time
import numpy as np
import os

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QCheckBox
)
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt, QSize

# Add edge-node to path to use REC's core modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'edge-node'))

from ultralytics import YOLO
from orchestrator.utils.aspect_framing import compute_framing_box, compute_composition_score, compute_bbox_iou

def convert_cv_qt(cv_img):
    """Convert from an opencv image to QPixmap"""
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb_image.shape
    bytes_per_line = ch * w
    convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return QPixmap.fromImage(convert_to_Qt_format)

def get_blur_score(image):
    if image is None or image.size == 0: return 0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def analyze_eye(frame, cx, cy, size=20):
    x1, y1 = max(0, int(cx - size/2)), max(0, int(cy - size/2))
    x2, y2 = min(frame.shape[1], int(cx + size/2)), min(frame.shape[0], int(cy + size/2))
    
    if x2 - x1 < 5 or y2 - y1 < 5:
        return True, 1000.0 # Ignore if too small to analyze
        
    eye_crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(eye_crop, cv2.COLOR_BGR2GRAY)
    
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    std_dev = np.std(gray)
    
    # An open eye has white sclera and dark pupil (high std_dev/contrast).
    # A closed eye is mostly uniform skin (low std_dev).
    is_open = std_dev > 12.0 and lap_var > 30.0
    return is_open, lap_var

def crop_with_padding(frame, box):
    """Crops an image to a box, padding with black if the box goes out of bounds."""
    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = frame.shape[:2]
    out_h, out_w = y2 - y1, x2 - x1
    
    if out_h <= 0 or out_w <= 0:
        return np.zeros((10, 10, 3), dtype=np.uint8)
        
    canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w, x2), min(h, y2)
    
    if src_x1 >= src_x2 or src_y1 >= src_y2:
        return canvas
        
    dst_x1 = src_x1 - x1
    dst_y1 = src_y1 - y1
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    dst_y2 = dst_y1 + (src_y2 - src_y1)
    
    canvas[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
    return canvas

def draw_emoji(cv_img, is_smile, is_thumb):
    if not is_smile and not is_thumb:
        return cv_img
    
    # Fallback OpenCV text if PIL fails
    if is_smile: cv2.putText(cv_img, "SMILING", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,255), 1, cv2.LINE_AA)
    if is_thumb: cv2.putText(cv_img, "THUMBS UP", (5, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,100,100), 1, cv2.LINE_AA)
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 16)
        pil_img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        text = ""
        if is_smile: text += "😊"
        if is_thumb: text += "✋"
        
        # Embedded color rendering for MacOS emojis
        try:
            draw.text((5, 35), text, font=font, embedded_color=True)
        except:
            draw.text((5, 35), text, font=font)
            
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return cv_img

class EllipseKalmanFilter:
    def __init__(self):
        self.q = 0.05  # process noise (higher = trusts new measurements more)
        self.r = 0.5   # measurement noise (higher = smoother but more lag)
        self.p = np.ones(5)
        self.x = None

    def update(self, meas):
        meas = np.array(meas, dtype=np.float32)
        if self.x is None:
            self.x = meas
            return self.x
            
        # Unwrap angle to prevent 180-degree jump jitter
        if meas[4] - self.x[4] > 90:
            meas[4] -= 180
        elif meas[4] - self.x[4] < -90:
            meas[4] += 180
            
        # 1D Kalman update for each parameter
        self.p = self.p + self.q
        k = self.p / (self.p + self.r)
        self.x = self.x + k * (meas - self.x)
        self.p = (1 - k) * self.p
        return self.x

class CaptureDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("REC Edge Dashboard")
        self.setGeometry(100, 100, 1280, 720)
        self.showMaximized()
        self.setStyleSheet("background-color: #121212; color: #FFFFFF;")

        # AI Models
        print("Loading YOLOv8n-pose engine...")
        self.model = YOLO('yolov8n-pose.pt')
        
        print("Loading MediaPipe Intelligence Engine...")
        import mediapipe as mp
        self.mp = mp
        
        BaseOptions = mp.tasks.BaseOptions
        self.mp_image_format = mp.ImageFormat.SRGB
        
        self.gesture_rec = mp.tasks.vision.GestureRecognizer.create_from_options(
            mp.tasks.vision.GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path='model/gesture_recognizer.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE)
        )
        self.face_rec = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path='model/face_landmarker.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                output_face_blendshapes=True)
        )

        # Camera
        self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            print("Webcam 1 failed to open. Trying Webcam 0 instead...")
            self.cap = cv2.VideoCapture(0)
        
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Prevent frame queuing lag

        # State
        self.last_optimal_bboxes = {}
        self.neutral_frames = {}
        self.smoothed_boxes = {}
        self.ellipse_kalmans = {}
        self.capture_buffers = {}
        self.cooldown_frames = 0
        self.captured_count = 0
        
        # Inference Throttling
        self.frame_counter = 0
        self.gesture_cache = {} # track_id -> (is_smiling, s_score, is_thumbs)
        self.gesture_history = {} # track_id -> {'smile': [], 'thumbs': []}

        # Build UI
        self.init_ui()

        # Start Video Loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30) # ~33fps

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel (Live Feed)
        left_panel = QVBoxLayout()
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet("border: 2px solid #333; background-color: #000;")
        left_panel.addWidget(self.video_label, stretch=1)
        main_layout.addLayout(left_panel, stretch=2)

        # Right Panel (Live Faces & Queue)
        right_panel = QVBoxLayout()
        
        # Settings Toggles
        settings_title = QLabel("Capture Triggers")
        settings_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        right_panel.addWidget(settings_title)
        
        toggles_layout = QHBoxLayout()
        self.smile_toggle = QCheckBox("Require Smile")
        self.thumbs_toggle = QCheckBox("Require Thumbs Up")
        style = "QCheckBox { color: white; font-size: 14px; font-weight: bold; margin-bottom: 10px; }"
        self.smile_toggle.setStyleSheet(style)
        self.thumbs_toggle.setStyleSheet(style)
        
        toggles_layout.addWidget(self.smile_toggle)
        toggles_layout.addWidget(self.thumbs_toggle)
        toggles_layout.addStretch()
        right_panel.addLayout(toggles_layout)
        
        # Live Faces Section
        faces_title = QLabel("Live Visible Faces")
        faces_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        right_panel.addWidget(faces_title)
        
        self.live_faces_label = QLabel()
        self.live_faces_label.setAlignment(Qt.AlignLeft)
        self.live_faces_label.setMinimumHeight(150)
        self.live_faces_label.setStyleSheet("background-color: #1e1e1e; padding: 5px;")
        right_panel.addWidget(self.live_faces_label)

        # Captured Queue Section
        queue_title = QLabel("Captured Images Queue")
        queue_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        right_panel.addWidget(queue_title)

        self.queue_list = QListWidget()
        self.queue_list.setIconSize(QSize(160, 120))  # Set thumbnail size
        self.queue_list.setStyleSheet("""
            QListWidget { background-color: #1e1e1e; border: none; }
            QListWidget::item { border-bottom: 1px solid #333; padding: 5px; }
        """)
        right_panel.addWidget(self.queue_list, stretch=1)

        main_layout.addLayout(right_panel, stretch=1)

    def add_to_queue(self, frame, track_id, reason="Auto-Framing"):
        self.captured_count += 1
        # Create thumbnail
        thumb = cv2.resize(frame, (160, 120))
        pixmap = convert_cv_qt(thumb)
        
        item = QListWidgetItem()
        item.setIcon(QIcon(pixmap))
        item.setText(f"Capture #{self.captured_count} (ID {track_id})\n{time.strftime('%H:%M:%S')} - {reason}")
        self.queue_list.insertItem(0, item) # Insert at top

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
            
        self.frame_counter += 1

        display_frame = frame.copy()
        h, w = display_frame.shape[:2]
        
        # Reduce pose estimation resolution internally to increase speed
        results = self.model.track(frame, persist=True, verbose=False, imgsz=480)
        
        if self.cooldown_frames > 0:
            self.cooldown_frames -= 1

        live_faces = [] # Store cropped face images
        optimal_found = False
        captured_crop = None
        captured_id = None
        captured_reason = None


        for result in results:
            boxes = result.boxes
            keypoints = result.keypoints
            
            if boxes is None or len(boxes) == 0:
                continue
                
            for i in range(len(boxes)):
                if int(boxes.cls[i].item()) != 0:
                    continue
                    
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                conf = boxes.conf[i].item()
                track_id = int(boxes.id[i].item()) if boxes.id is not None else i
                
                if conf < 0.5:
                    continue

                # EMA Smoothing to fix jitter
                alpha = 0.5
                if track_id in self.smoothed_boxes:
                    px1, py1, px2, py2 = self.smoothed_boxes[track_id]
                    x1 = alpha * x1 + (1 - alpha) * px1
                    y1 = alpha * y1 + (1 - alpha) * py1
                    x2 = alpha * x2 + (1 - alpha) * px2
                    y2 = alpha * y2 + (1 - alpha) * py2
                self.smoothed_boxes[track_id] = (x1, y1, x2, y2)
                    
                kpts = keypoints.data[i].cpu().numpy() if keypoints is not None else None
                
                # Aspect framing box (Unconstrained to automatically center user!)
                fb = compute_framing_box([int(x1), int(y1), int(x2), int(y2)], w, h, aspect_ratio="4:3", framing_scale="AUTO", keypoints=kpts, clamp_to_sensor=False)
                comp_score = compute_composition_score([int(x1), int(y1), int(x2), int(y2)], fb, kpts)
                
                # Common Person Crop for Classifiers
                person_crop = frame[max(0, int(y1)):min(h, int(y2)), max(0, int(x1)):min(w, int(x2))]

                # Evaluate Expressions via Throttled ONNX Models
                if track_id not in self.gesture_cache:
                    self.gesture_cache[track_id] = (False, 0.0, False, None, None)
                if track_id not in self.gesture_history:
                    self.gesture_history[track_id] = {'smile': [], 'thumbs': []}
                    
                is_smiling, s_score, is_thumbs, face_lms, hand_lms = self.gesture_cache[track_id]
                
                if self.frame_counter % 3 == 0:
                    raw_smile, s_score, raw_thumbs = False, 0.0, False
                    face_lms_cache, hand_lms_cache = None, None
                    
                    if person_crop.size > 0:
                        try:
                            # Convert to MediaPipe Image
                            mp_image = self.mp.Image(image_format=self.mp_image_format, data=cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB))
                            
                            if self.smile_toggle.isChecked():
                                face_result = self.face_rec.detect(mp_image)
                                if face_result.face_blendshapes:
                                    face_lms_cache = face_result.face_landmarks[0] if face_result.face_landmarks else None
                                    for shape in face_result.face_blendshapes[0]:
                                        # Check if either side of the mouth is smiling heavily
                                        if shape.category_name in ['mouthSmileLeft', 'mouthSmileRight'] and shape.score > 0.45:
                                            raw_smile = True
                                            s_score = shape.score * 100.0
                                            break
                                            
                            if self.thumbs_toggle.isChecked():
                                gesture_result = self.gesture_rec.recognize(mp_image)
                                if gesture_result.gestures and len(gesture_result.gestures) > 0:
                                    hand_lms_cache = gesture_result.hand_landmarks[0] if gesture_result.hand_landmarks else None
                                    for gesture in gesture_result.gestures[0]:
                                        if gesture.category_name == 'Thumb_Up' and gesture.score > 0.5:
                                            raw_thumbs = True
                                            break
                        except Exception as e:
                            print(f"MediaPipe inference failed: {e}")
                                    
                    # Maintain sliding window history (last 4 inference cycles = ~12 frames)
                    self.gesture_history[track_id]['smile'].append(raw_smile)
                    self.gesture_history[track_id]['thumbs'].append(raw_thumbs)
                    
                    if len(self.gesture_history[track_id]['smile']) > 4:
                        self.gesture_history[track_id]['smile'].pop(0)
                        self.gesture_history[track_id]['thumbs'].pop(0)
                        
                    # Temporal Voting: Require 3 out of last 4 checks to be True to prevent false flashes
                    is_smiling = sum(self.gesture_history[track_id]['smile']) >= 3
                    is_thumbs = sum(self.gesture_history[track_id]['thumbs']) >= 3
                    
                    # Update cache
                    self.gesture_cache[track_id] = (is_smiling, s_score, is_thumbs, face_lms_cache, hand_lms_cache)

                # Extract face box for thumbnail
                fx1, fy1, fx2, fy2 = int(x1), int(y1), int(x2), int(y1 + (y2-y1)*0.3)
                face_visible = False
                if kpts is not None and len(kpts) >= 5:
                    nx, ny, nc = kpts[0]
                    lx, ly, lc = kpts[1]
                    rx, ry, rc = kpts[2]
                    if nc > 0.2:
                        face_visible = True
                        eye_dist = np.sqrt((rx - lx)**2 + (ry - ly)**2) if (lc>0.2 and rc>0.2) else (x2 - x1)*0.22
                        face_size = max(40, eye_dist * 3.0)
                        fx1, fy1 = max(0, int(nx - face_size/2)), max(0, int(ny - face_size/2))
                        fx2, fy2 = min(w, int(nx + face_size/2)), min(h, int(ny + face_size/2))
                
                # Crop and resize face
                if face_visible and fx2 > fx1 and fy2 > fy1:
                    face_crop = frame[fy1:fy2, fx1:fx2]
                    if face_crop.size > 0:
                        face_crop = cv2.resize(face_crop, (100, 100))
                        face_crop = draw_emoji(face_crop, is_smiling, is_thumbs)
                        cv2.putText(face_crop, f"ID {track_id}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
                        live_faces.append(face_crop)
                
                is_optimal = (comp_score >= 0.70)
                alerts = []
                
                # Apply Toggles
                req_smile = self.smile_toggle.isChecked()
                req_thumbs = self.thumbs_toggle.isChecked()
                
                meets_requirements = True
                if req_smile or req_thumbs:
                    meets_requirements = False
                    if req_smile and is_smiling: meets_requirements = True
                    if req_thumbs and is_thumbs: meets_requirements = True
                    
                if not meets_requirements:
                    is_optimal = False
                    if req_smile and req_thumbs:
                        alerts.append("WAITING: Smile OR Thumbs Up")
                    elif req_smile:
                        alerts.append("WAITING: Smile")
                    elif req_thumbs:
                        alerts.append("WAITING: Thumbs Up")

                if self.cooldown_frames > 0:
                    alerts.append("COOLDOWN: Processing...")
                    is_optimal = False
                elif comp_score < 0.70:
                    # Provide dynamic instructions to fix framing
                    body_cx = (x1 + x2) / 2
                    fb_cx = (fb[0] + fb[2]) / 2
                    fb_h = fb[3] - fb[1]
                    
                    if body_cx < fb_cx - 30:
                        alerts.append("REJECTED: Move Right ->")
                    elif body_cx > fb_cx + 30:
                        alerts.append("REJECTED: <- Move Left")
                    elif y1 < fb[1] + fb_h * 0.1:
                        alerts.append("REJECTED: Too High (Move Down)")
                    elif y1 > fb[1] + fb_h * 0.25:
                        alerts.append("REJECTED: Too Low (Move Up)")
                    else:
                        alerts.append("REJECTED: Center Yourself")

                fill = ((x2 - x1) * (y2 - y1)) / (w * h)
                if fill < 0.15:
                    alerts.append("MOVE NEAR (Too Far)")
                    is_optimal = False
                elif fill > 0.65:
                    alerts.append("MOVE BACK (Too Close)")
                    is_optimal = False
                    
                is_frontal = False
                left_eye_open = True
                right_eye_open = True
                eye_dist = 20
                
                if kpts is not None and len(kpts) >= 5:
                    if kpts[0][2] > 0.2 and kpts[1][2] > 0.2 and kpts[2][2] > 0.2:
                        is_frontal = True
                        eye_dist = np.sqrt((kpts[1][0] - kpts[2][0])**2 + (kpts[1][1] - kpts[2][1])**2)
                        eye_size = max(10, int(eye_dist * 0.45))
                        
                        # Analyze eyes for blinks
                        left_eye_open, _ = analyze_eye(frame, kpts[1][0], kpts[1][1], size=eye_size)
                        right_eye_open, _ = analyze_eye(frame, kpts[2][0], kpts[2][1], size=eye_size)
                
                if not is_frontal:
                    alerts.append("REJECTED: Face Not Frontal")
                    is_optimal = False
                elif not left_eye_open or not right_eye_open:
                    alerts.append("REJECTED: Open Eyes Wide!")
                    is_optimal = False
                    
                if x1 <= 5 or y1 <= 5 or x2 >= w - 5:
                    alerts.append("REJECTED: Cut Off Frame")
                    is_optimal = False

                # Temporal Consensus & Frame Voting
                cfb = [int(fb[0]), int(fb[1]), int(fb[2]), int(fb[3])]
                raw_crop = crop_with_padding(frame, cfb)
                
                # Check overall blur of the crop
                crop_blur = get_blur_score(raw_crop)
                
                # Check Exposure (0-255)
                if raw_crop.size > 0:
                    gray_crop = cv2.cvtColor(raw_crop, cv2.COLOR_BGR2GRAY)
                    exposure = np.mean(gray_crop)
                else:
                    exposure = 127
                    
                if crop_blur < 150.0: # Increased strictness for blur (must be sharp)
                    alerts.append("REJECTED: Blurry/Subject Moving")
                    is_optimal = False
                elif exposure > 235:
                    alerts.append("REJECTED: Overexposed (Too Bright)")
                    is_optimal = False
                elif exposure < 30:
                    alerts.append("REJECTED: Underexposed (Too Dark)")
                    is_optimal = False
                    
                # Enforce Change Pose logic (Physical Movement)
                if track_id in self.last_optimal_bboxes:
                    iou = compute_bbox_iou(cfb, self.last_optimal_bboxes[track_id])
                    if iou > 0.85:
                        alerts.append("CHANGE POSE (Move around)")
                        is_optimal = False
                    
                if track_id not in self.capture_buffers:
                    self.capture_buffers[track_id] = []
                    
                # Determine reason for UI
                trigger_reason = "Auto-Framing"
                if req_smile and req_thumbs:
                    if is_smiling and is_thumbs: trigger_reason = "Smile & Thumbs Up"
                    elif is_smiling: trigger_reason = "Smile"
                    elif is_thumbs: trigger_reason = "Thumbs Up"
                elif req_smile:
                    trigger_reason = "Smile"
                elif req_thumbs:
                    trigger_reason = "Thumbs Up"
                    
                # Cache the highest quality raw crop for this frame
                self.capture_buffers[track_id].append({
                    "crop": raw_crop,
                    "fb": cfb,
                    "is_optimal": is_optimal,
                    "comp_score": comp_score,
                    "smile_score": s_score if is_smiling else 0.0,
                    "blur_score": crop_blur,
                    "reason": trigger_reason
                })
                
                # Keep sliding window of 10 frames (~300ms)
                if len(self.capture_buffers[track_id]) > 10:
                    self.capture_buffers[track_id].pop(0)
                    
                buffer = self.capture_buffers[track_id]
                
                if len(buffer) >= 5 and self.cooldown_frames == 0:
                    recent = buffer[-5:]
                    # Consensus: Require 4 out of last 5 frames to be optimal to trigger capture
                    if sum(1 for b in recent if b["is_optimal"]) >= 4 and recent[-1]["is_optimal"]:
                        # Voting: Pick the frame with best composition, smile, and sharpness
                        best_frame = max(recent, key=lambda x: x["comp_score"] + (x["smile_score"] * 0.5) + (x["blur_score"] * 0.001))
                        
                        alerts.append("CONSENSUS: Captured Best Frame!")
                        optimal_found = True
                        captured_id = track_id
                        captured_crop = best_frame["crop"]
                        captured_reason = best_frame["reason"]
                        self.last_optimal_bboxes[track_id] = best_frame["fb"]

                # Dynamic Pose Ellipse & Closed Eye Overlays
                overlay = display_frame.copy()
                drawn_ellipse = False
                
                if not left_eye_open and is_frontal:
                    cv2.ellipse(overlay, (int(kpts[1][0]), int(kpts[1][1])), (int(eye_dist*0.3), int(eye_dist*0.15)), 0, 0, 360, (200, 105, 255), -1) # Pink
                if not right_eye_open and is_frontal:
                    cv2.ellipse(overlay, (int(kpts[2][0]), int(kpts[2][1])), (int(eye_dist*0.3), int(eye_dist*0.15)), 0, 0, 360, (200, 105, 255), -1) # Pink
                    
                if kpts is not None and len(kpts) >= 5:
                    valid_pts = []
                    for kp in kpts:
                        if kp[2] > 0.3:
                            valid_pts.append([kp[0], kp[1]])
                            
                    if len(valid_pts) >= 5:
                        pts_array = np.array(valid_pts, dtype=np.int32)
                        # cv2.fitEllipse requires at least 5 points
                        box2d = cv2.fitEllipse(pts_array)
                        (cx, cy), (MA, ma), angle = box2d
                        
                        if track_id not in self.ellipse_kalmans:
                            self.ellipse_kalmans[track_id] = EllipseKalmanFilter()
                            
                        # Apply Kalman smoothing
                        filtered = self.ellipse_kalmans[track_id].update([cx, cy, MA, ma, angle])
                        cx, cy, MA, ma, angle = filtered
                        
                        axes = (int(MA/2 * 1.3), int(ma/2 * 1.3)) # Pad it slightly as a bubble
                        center = (int(cx), int(cy))
                        
                        if axes[0] > 10 and axes[1] > 10:
                            cv2.ellipse(overlay, center, axes, angle, 0, 360, (235, 206, 135), -1)
                            cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)
                            cv2.ellipse(display_frame, center, axes, angle, 0, 360, (235, 206, 135), 2)
                            drawn_ellipse = True
                            
                if not drawn_ellipse:
                    # Fallback to standard vertical ellipse based on bounding box
                    center_oval = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                    axes = (int((x2 - x1) * 0.35), int((y2 - y1) / 2))
                    cv2.ellipse(overlay, center_oval, axes, 0, 0, 360, (235, 206, 135), -1)
                    cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)
                    cv2.ellipse(display_frame, center_oval, axes, 0, 0, 360, (235, 206, 135), 2)

                # Plot gestures visibly on the main feed
                if is_smiling:
                    cv2.putText(display_frame, "SMILING :D", (int(x1), max(30, int(y1) - 10)), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 255), 3)
                    if face_lms:
                        # Draw pink points on the face
                        for lm in face_lms:
                            cx, cy = int(lm.x * (x2 - x1) + x1), int(lm.y * (y2 - y1) + y1)
                            cv2.circle(display_frame, (cx, cy), 1, (203, 192, 255), -1)
                            
                if is_thumbs:
                    cv2.putText(display_frame, "THUMBS UP!", (int(x1), max(70, int(y1) - 45)), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 100, 100), 3)
                    if hand_lms:
                        # Draw pink polygon/lines on the hand
                        pts = np.array([[int(lm.x * (x2 - x1) + x1), int(lm.y * (y2 - y1) + y1)] for lm in hand_lms], np.int32)
                        cv2.polylines(display_frame, [pts.reshape((-1, 1, 2))], True, (203, 192, 255), 2)
                        for pt in pts:
                            cv2.circle(display_frame, tuple(pt), 4, (203, 192, 255), -1)

                if is_frontal:
                    if is_optimal:
                        box_color = (0, 255, 0) # Green for perfect capture ready
                    elif (self.smile_toggle.isChecked() and is_smiling) or (self.thumbs_toggle.isChecked() and is_thumbs):
                        box_color = (0, 255, 255) # Yellow for gesture detected (checking/confirming)
                    else:
                        box_color = (0, 0, 255) # Red
                        
                    cv2.rectangle(display_frame, (fb[0], fb[1]), (fb[2], fb[3]), box_color, 4)
                    
                    cell_w, cell_h = max(1, fb[2] - fb[0]) // 3, max(1, fb[3] - fb[1]) // 3
                    cv2.line(display_frame, (fb[0] + cell_w, fb[1]), (fb[0] + cell_w, fb[3]), box_color, 1)
                    cv2.line(display_frame, (fb[0] + 2*cell_w, fb[1]), (fb[0] + 2*cell_w, fb[3]), box_color, 1)
                    cv2.line(display_frame, (fb[0], fb[1] + cell_h), (fb[2], fb[1] + cell_h), box_color, 1)
                    cv2.line(display_frame, (fb[0], fb[1] + 2*cell_h), (fb[2], fb[1] + 2*cell_h), box_color, 1)
                    
                    for row in range(3):
                        for col in range(3):
                            cv2.putText(display_frame, str(row*3 + col + 1), (fb[0] + col*cell_w + cell_w//2 - 10, fb[1] + row*cell_h + cell_h//2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)
                    
                    score_txt = f"Score: {comp_score:.2f}"
                    (sw, sh), _ = cv2.getTextSize(score_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    sx = max(5, min(fb[0], w - sw - 5))
                    sy = min(fb[3] + 25, h - 5)
                    cv2.rectangle(display_frame, (sx, sy - sh - 5), (sx + sw + 5, sy + 5), (0, 0, 0), -1)
                    cv2.putText(display_frame, score_txt, (sx, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
                    
                    if is_smiling:
                        (sw, sh), _ = cv2.getTextSize("SMILE!", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        sm_x = max(5, min(fb[0] + 120, w - sw - 5))
                        cv2.rectangle(display_frame, (sm_x, sy - sh - 5), (sm_x + sw + 5, sy + 5), (0, 0, 0), -1)
                        cv2.putText(display_frame, f"SMILE!", (sm_x, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)

                # Stacked Alerts
                total_alert_height = len(alerts) * 25
                if fb[1] - total_alert_height >= 10:
                    y_offset = fb[1] - 15
                    y_step = -25
                else:
                    # Place inside the box, guaranteed visible below top edge
                    y_offset = max(25, fb[1] + 25)
                    y_step = 25

                for alert in reversed(alerts):
                    color = (0, 255, 0) if "OPTIMAL" in alert else (0, 0, 255)
                    if "BLOCKED" in alert or "MOVE" in alert:
                        color = (0, 165, 255)
                    (tw, th), _ = cv2.getTextSize(alert, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    
                    text_x = max(5, min(fb[0] + 5, w - tw - 5))
                    # Ensure y_offset is also strictly inside height
                    if y_offset < th + 5: y_offset = th + 5
                    if y_offset > h - 5: break # Stop drawing if we run out of screen at bottom

                    cv2.rectangle(display_frame, (text_x, y_offset - th - 5), (text_x + tw + 5, y_offset + 5), (0, 0, 0), -1)
                    cv2.putText(display_frame, alert, (text_x, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    y_offset += y_step

        # Show Live Feed Scaled
        pixmap = convert_cv_qt(display_frame)
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Show Live Faces
        if len(live_faces) > 0:
            faces_strip = cv2.hconcat(live_faces)
            self.live_faces_label.setPixmap(convert_cv_qt(faces_strip))
        else:
            self.live_faces_label.clear()
            self.live_faces_label.setText("No faces detected.")

        # Handle Captures
        if optimal_found and captured_id is not None and captured_crop is not None:
            if captured_crop.size > 0:
                self.add_to_queue(captured_crop, captured_id, captured_reason)
            self.cooldown_frames = 45 # 1.5s pause to prevent rapid-fire capture
            self.capture_buffers[captured_id].clear() # Flush buffer after capture

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CaptureDashboard()
    window.show()
    sys.exit(app.exec_())
