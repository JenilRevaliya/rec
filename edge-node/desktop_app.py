import sys
import os
import time
import requests
import subprocess
import json
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QGridLayout, QMessageBox, QScrollArea,
    QComboBox, QFrame, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QPainter, QColor, QPen
from camera.detector import detect_available_cameras

from ultralytics import YOLO
import mediapipe as mp
import math

def compute_bbox_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def get_blur_score(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def crop_with_padding(image, bbox, padding_pct=0.1):
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    px, py = int(bw * padding_pct), int(bh * padding_pct)
    return image[max(0, y1-py):min(h, y2+py), max(0, x1-px):min(w, x2+px)]

def compute_framing_box(person_bbox, frame_w, frame_h, aspect_ratio="4:3", framing_scale="AUTO", keypoints=None, clamp_to_sensor=False):
    x1, y1, x2, y2 = person_bbox
    bw, bh = x2 - x1, y2 - y1
    scale_factor = 1.3
    if framing_scale == "AUTO" and keypoints is not None and len(keypoints) > 0:
        face_kpts = keypoints[:5]
        if np.mean([k[2] for k in face_kpts]) > 0.3: scale_factor = 1.8 
        else: scale_factor = 1.2
    target_h = int(bh * scale_factor)
    target_w = int(target_h * (4/3))
    cx, cy = int(x1 + bw/2), int(y1 + bh/2)
    if keypoints is not None and len(keypoints) > 0 and keypoints[0][2] > 0.3:
        cy = int(y1 + (keypoints[0][1] - y1) * 0.8)
    nx1, ny1 = cx - target_w//2, cy - target_h//2
    nx2, ny2 = nx1 + target_w, ny1 + target_h
    if clamp_to_sensor:
        nx1, ny1 = max(0, nx1), max(0, ny1)
        nx2, ny2 = min(frame_w, nx2), min(frame_h, ny2)
    return [nx1, ny1, nx2, ny2]

def compute_composition_score(person_bbox, frame_bbox, keypoints=None):
    px1, py1, px2, py2 = person_bbox
    fx1, fy1, fx2, fy2 = frame_bbox
    if px1 < fx1 or py1 < fy1 or px2 > fx2 or py2 > fy2: return 0.1
    score = 1.0
    if keypoints is not None and len(keypoints) > 0:
        nose = keypoints[0]
        if nose[2] > 0.3:
            grid_y = fy1 + (fy2 - fy1) * 0.33
            dist = abs(nose[1] - grid_y)
            score -= (dist / (fy2 - fy1)) * 1.5
    return max(0.0, min(1.0, score))


# ─────────────────────────────────────────────────────────────────
# Global Config
# ─────────────────────────────────────────────────────────────────
CLOUD_API_URL = os.environ.get("API_URL", "http://localhost:8000")
BUFFER_DIR = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")
os.makedirs(BUFFER_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────
# Styling (Neobrutalism / Professional Dark)
# ─────────────────────────────────────────────────────────────────
STYLESHEET = """
QWidget {
    background-color: #121212;
    color: #FFFFFF;
    font-family: "Courier New", Courier, monospace;
}
QLineEdit {
    background-color: #1E1E1E;
    border: 2px solid #333333;
    padding: 10px;
    font-size: 14px;
    font-weight: bold;
}
QLineEdit:focus {
    border: 2px solid #7bfa7b;
}
QPushButton {
    background-color: #FFFFFF;
    color: #000000;
    border: 3px solid #7bfa7b;
    padding: 10px;
    font-weight: 900;
    font-size: 14px;
    text-transform: uppercase;
}
QPushButton:hover {
    background-color: #7bfa7b;
}
QPushButton:pressed {
    background-color: #4CAF50;
    border: 3px solid #4CAF50;
}
QPushButton.danger {
    border-color: #ff6b6b;
}
QPushButton.danger:hover {
    background-color: #ff6b6b;
    color: #FFFFFF;
}
QLabel.title {
    font-size: 24px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 2px;
}
QFrame.box {
    background-color: #1A1A1A;
    border: 2px solid #333333;
}
"""

# ─────────────────────────────────────────────────────────────────
# Threads
# ─────────────────────────────────────────────────────────────────


class AIEngineThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)
    
    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self._run_flag = True
        self.ai_active = False
        self.req_smile = False
        self.req_thumbs = False
        
        self.yolo_model = None
        self.mp = None
        self.gesture_rec = None
        self.face_rec = None
        
        self.frame_counter = 0
        self.gesture_cache = {}
        self.gesture_history = {}
        self.last_optimal_bboxes = {}
        self.capture_buffers = {}
        self.cooldown_frames = 0
        
    def init_ai(self):
        if self.yolo_model is not None: return
        self.status_update.emit("Loading YOLOv8n-pose...")
        self.yolo_model = YOLO('../yolov8n-pose.pt')
        self.status_update.emit("Loading MediaPipe...")
        import mediapipe as mp
        self.mp = mp
        BaseOptions = mp.tasks.BaseOptions
        self.mp_image_format = mp.ImageFormat.SRGB
        self.gesture_rec = mp.tasks.vision.GestureRecognizer.create_from_options(
            mp.tasks.vision.GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path='../model/gesture_recognizer.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE)
        )
        self.face_rec = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path='../model/face_landmarker.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                output_face_blendshapes=True)
        )
        self.status_update.emit("AI Ready.")

    def run(self):
        if self.camera_id.startswith("MOCK"):
            from camera.mock import MockCameraDriver
            driver = MockCameraDriver(self.camera_id)
        elif self.camera_id.startswith("Webcam"):
            from camera.webcam import WebcamDriver
            driver = WebcamDriver(self.camera_id)
        else:
            from camera.dslr import DSLRDriver
            driver = DSLRDriver(self.camera_id)

        if not driver.connect():
            print("Preview Thread: Camera connect failed")
            return

        while self._run_flag:
            try:
                frame = driver.get_live_preview_frame()
                if frame is not None:
                    if self.ai_active:
                        self.init_ai()
                        display_frame = frame.copy()
                        h, w = display_frame.shape[:2]
                        self.frame_counter += 1
                        if self.cooldown_frames > 0: self.cooldown_frames -= 1
                        
                        results = self.yolo_model.track(frame, persist=True, verbose=False, imgsz=480)
                        optimal_found = False; captured_crop = None; captured_id = None
                        
                        for result in results:
                            boxes = result.boxes
                            if boxes is None or len(boxes) == 0: continue
                            if result.keypoints is None: continue
                            
                            for i in range(len(boxes)):
                                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                                track_id = int(boxes.id[i].cpu().numpy()) if boxes.id is not None else -1
                                if track_id == -1: continue
                                
                                kpts = result.keypoints.data[i].cpu().numpy()
                                fb = compute_framing_box([int(x1), int(y1), int(x2), int(y2)], w, h, aspect_ratio="4:3", framing_scale="AUTO", keypoints=kpts, clamp_to_sensor=False)
                                comp_score = compute_composition_score([int(x1), int(y1), int(x2), int(y2)], fb, kpts)
                                person_crop = frame[max(0, int(y1)):min(h, int(y2)), max(0, int(x1)):min(w, int(x2))]
                                
                                if track_id not in self.gesture_cache: self.gesture_cache[track_id] = (False, 0.0, False, None, None)
                                if track_id not in self.gesture_history: self.gesture_history[track_id] = {'smile': [], 'thumbs': []}
                                
                                is_smiling, s_score, is_thumbs, face_lms, hand_lms = self.gesture_cache[track_id]
                                
                                if self.frame_counter % 3 == 0:
                                    raw_smile, s_score, raw_thumbs = False, 0.0, False
                                    face_lms_cache, hand_lms_cache = None, None
                                    if person_crop.size > 0:
                                        try:
                                            mp_image = self.mp.Image(image_format=self.mp_image_format, data=cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB))
                                            if self.req_smile:
                                                face_result = self.face_rec.detect(mp_image)
                                                if face_result.face_blendshapes:
                                                    face_lms_cache = face_result.face_landmarks[0] if face_result.face_landmarks else None
                                                    for shape in face_result.face_blendshapes[0]:
                                                        if shape.category_name in ['mouthSmileLeft', 'mouthSmileRight'] and shape.score > 0.45:
                                                            raw_smile = True; s_score = shape.score * 100.0; break
                                            if self.req_thumbs:
                                                gesture_result = self.gesture_rec.recognize(mp_image)
                                                if gesture_result.gestures and len(gesture_result.gestures) > 0:
                                                    hand_lms_cache = gesture_result.hand_landmarks[0] if gesture_result.hand_landmarks else None
                                                    for gesture in gesture_result.gestures[0]:
                                                        if gesture.category_name == 'Thumb_Up' and gesture.score > 0.5:
                                                            raw_thumbs = True; break
                                        except Exception as e: print(e)
                                        
                                    self.gesture_history[track_id]['smile'].append(raw_smile)
                                    self.gesture_history[track_id]['thumbs'].append(raw_thumbs)
                                    if len(self.gesture_history[track_id]['smile']) > 4:
                                        self.gesture_history[track_id]['smile'].pop(0)
                                        self.gesture_history[track_id]['thumbs'].pop(0)
                                    is_smiling = sum(self.gesture_history[track_id]['smile']) >= 3
                                    is_thumbs = sum(self.gesture_history[track_id]['thumbs']) >= 3
                                    self.gesture_cache[track_id] = (is_smiling, s_score, is_thumbs, face_lms_cache, hand_lms_cache)

                                is_optimal = (comp_score >= 0.70)
                                alerts = []
                                
                                meets_requirements = False
                                if not self.req_smile and not self.req_thumbs: meets_requirements = True
                                else:
                                    if self.req_smile and self.req_thumbs and is_smiling and is_thumbs: meets_requirements = True
                                    if self.req_smile and not self.req_thumbs and is_smiling: meets_requirements = True
                                    if self.req_thumbs and not self.req_smile and is_thumbs: meets_requirements = True
                                    
                                if not meets_requirements:
                                    is_optimal = False
                                    if self.req_smile and self.req_thumbs: alerts.append("WAITING: Smile OR Thumbs Up")
                                    elif self.req_smile: alerts.append("WAITING: Smile")
                                    elif self.req_thumbs: alerts.append("WAITING: Thumbs Up")
                                    
                                if self.cooldown_frames > 0:
                                    alerts.append("COOLDOWN: Processing...")
                                    is_optimal = False
                                elif comp_score < 0.70:
                                    body_cx, fb_cx = (x1 + x2)/2, (fb[0] + fb[2])/2
                                    if body_cx < fb_cx - 30: alerts.append("REJECTED: Move Right ->")
                                    elif body_cx > fb_cx + 30: alerts.append("REJECTED: <- Move Left")
                                    else: alerts.append("REJECTED: Center Yourself")
                                
                                is_frontal = False
                                if kpts is not None and len(kpts) > 4:
                                    nose, le, re = kpts[0], kpts[1], kpts[2]
                                    if nose[2]>0.3 and le[2]>0.3 and re[2]>0.3: is_frontal = True
                                        
                                if not is_frontal:
                                    alerts.append("REJECTED: Face Not Frontal")
                                    is_optimal = False
                                    
                                cfb = [int(fb[0]), int(fb[1]), int(fb[2]), int(fb[3])]
                                raw_crop = crop_with_padding(frame, cfb)
                                
                                crop_blur = get_blur_score(raw_crop)
                                exposure = np.mean(cv2.cvtColor(raw_crop, cv2.COLOR_BGR2GRAY)) if raw_crop.size > 0 else 127
                                    
                                if crop_blur < 150.0:
                                    alerts.append("REJECTED: Blurry")
                                    is_optimal = False
                                elif exposure > 235:
                                    alerts.append("REJECTED: Overexposed")
                                    is_optimal = False
                                elif exposure < 30:
                                    alerts.append("REJECTED: Underexposed")
                                    is_optimal = False
                                    
                                if track_id in self.last_optimal_bboxes:
                                    iou = compute_bbox_iou(cfb, self.last_optimal_bboxes[track_id])
                                    if iou > 0.85:
                                        alerts.append("CHANGE POSE (Move around)")
                                        is_optimal = False
                                        
                                if track_id not in self.capture_buffers: self.capture_buffers[track_id] = []
                                self.capture_buffers[track_id].append({
                                    "crop": raw_crop, "fb": cfb, "is_optimal": is_optimal,
                                    "comp_score": comp_score, "smile_score": s_score if is_smiling else 0.0,
                                    "blur_score": crop_blur
                                })
                                
                                if len(self.capture_buffers[track_id]) > 10: self.capture_buffers[track_id].pop(0)
                                
                                buffer = self.capture_buffers[track_id]
                                if len(buffer) >= 5 and self.cooldown_frames == 0:
                                    recent = buffer[-5:]
                                    if sum(1 for b in recent if b["is_optimal"]) >= 4 and recent[-1]["is_optimal"]:
                                        best_frame = max(recent, key=lambda x: x["comp_score"] + (x["smile_score"] * 0.5) + (x["blur_score"] * 0.001))
                                        alerts.append("CONSENSUS: Captured Best Frame!")
                                        optimal_found = True
                                        captured_id = track_id
                                        captured_crop = best_frame["crop"]
                                        self.last_optimal_bboxes[track_id] = best_frame["fb"]

                                if is_smiling:
                                    cv2.putText(display_frame, "SMILING :D", (int(x1), max(30, int(y1) - 10)), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 255), 3)
                                    if face_lms:
                                        for lm in face_lms:
                                            cx, cy = int(lm.x * (x2 - x1) + x1), int(lm.y * (y2 - y1) + y1)
                                            cv2.circle(display_frame, (cx, cy), 1, (203, 192, 255), -1)
                                if is_thumbs:
                                    cv2.putText(display_frame, "THUMBS UP!", (int(x1), max(70, int(y1) - 45)), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 100, 100), 3)
                                    if hand_lms:
                                        pts = np.array([[int(lm.x * (x2 - x1) + x1), int(lm.y * (y2 - y1) + y1)] for lm in hand_lms], np.int32)
                                        cv2.polylines(display_frame, [pts.reshape((-1, 1, 2))], True, (203, 192, 255), 2)
                                        for pt in pts: cv2.circle(display_frame, tuple(pt), 4, (203, 192, 255), -1)

                                if is_frontal:
                                    box_color = (0, 255, 0) if is_optimal else (0, 0, 255)
                                    if not is_optimal and ((self.req_smile and is_smiling) or (self.req_thumbs and is_thumbs)): box_color = (0, 255, 255)
                                    cv2.rectangle(display_frame, (fb[0], fb[1]), (fb[2], fb[3]), box_color, 4)
                                    y_offset = max(25, fb[1] + 25)
                                    for alert in reversed(alerts):
                                        color = (0, 255, 0) if "OPTIMAL" in alert else (0, 0, 255)
                                        if "BLOCKED" in alert or "MOVE" in alert: color = (0, 165, 255)
                                        (tw, th), _ = cv2.getTextSize(alert, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                                        text_x = max(5, min(fb[0] + 5, w - tw - 5))
                                        cv2.rectangle(display_frame, (text_x, y_offset - th - 5), (text_x + tw + 5, y_offset + 5), (0, 0, 0), -1)
                                        cv2.putText(display_frame, alert, (text_x, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                                        y_offset += 25

                        if optimal_found and captured_id is not None and captured_crop is not None:
                            if captured_crop.size > 0:
                                import time as t
                                filename = f"capture_{int(t.time())}_{captured_id}.jpg"
                                path = os.path.join(BUFFER_DIR, filename)
                                cv2.imwrite(path, captured_crop)
                            self.cooldown_frames = 45
                            self.capture_buffers[captured_id].clear()
                            
                        self.change_pixmap_signal.emit(display_frame)
                    else:
                        self.change_pixmap_signal.emit(frame)
                        self.status_update.emit("AI Offline")
            except Exception as e:
                print(f"Preview error: {e}")
            time.sleep(0.06)

    def stop(self):
        self._run_flag = False
        self.wait()



class BufferPollingThread(QThread):
    new_photos_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.last_files = set()

    def run(self):
        while self._run_flag:
            try:
                files = [f for f in os.listdir(BUFFER_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                current_files = set(files)
                
                # Check for new files to upload if toggle is on (handled by UI)
                new_files = current_files - self.last_files
                if new_files:
                    pass # We will handle upload in the main thread

                photos = []
                for f in current_files:
                    path = os.path.join(BUFFER_DIR, f)
                    stat = os.stat(path)
                    photos.append({
                        "filename": f,
                        "path": path,
                        "timestamp": stat.st_mtime
                    })
                photos.sort(key=lambda x: x["timestamp"], reverse=True)
                self.new_photos_signal.emit(photos[:50]) # Top 50
                self.last_files = current_files
                
            except Exception as e:
                print(f"Buffer poll error: {e}")
            time.sleep(2)

    def stop(self):
        self._run_flag = False
        self.wait()

# ─────────────────────────────────────────────────────────────────
# UI Components
# ─────────────────────────────────────────────────────────────────

class LoginWindow(QWidget):
    def __init__(self, on_success_callback):
        super().__init__()
        self.on_success = on_success_callback
        self.initUI()

    def initUI(self):
        self.setWindowTitle("REC Edge - Photographer Login")
        self.setFixedSize(400, 500)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 60, 40, 60)

        title = QLabel("REC Edge Node")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("class", "title")
        title.setStyleSheet("font-size: 28px; margin-bottom: 10px;")
        
        subtitle = QLabel("SECURE PHOTOGRAPHER ACCESS")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888888; font-weight: bold; margin-bottom: 20px;")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.login_btn = QPushButton("Authenticate")
        self.login_btn.clicked.connect(self.handle_login)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_btn)
        layout.addWidget(self.error_label)
        layout.addStretch()

        self.setLayout(layout)

    def handle_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        
        if not email or not password:
            self.error_label.setText("Please enter all fields")
            return
            
        self.login_btn.setText("VERIFYING...")
        self.login_btn.setEnabled(False)
        QApplication.processEvents()
        
        # Hardcoded Sandbox Backdoor
        if email == "photographer1" and password == "password":
            print("Sandbox mode activated.")
            self.on_success(email, "OFFLINE_TEST_TOKEN")
            return
            
        # Call Cloud API
        try:
            resp = requests.post(
                f"{CLOUD_API_URL}/api/v1/auth/login",
                json={"email": email, "password": password, "role": "photographer"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token")
                self.on_success(email, token)
            else:
                self.error_label.setText("Invalid credentials")
        except requests.exceptions.RequestException:
            self.error_label.setText("API Unreachable. Use demo credentials.")
                
        self.login_btn.setText("Authenticate")
        self.login_btn.setEnabled(True)


class DashboardWindow(QMainWindow):
    def __init__(self, email, token):
        super().__init__()
        self.email = email
        self.token = token
        self.orchestrator_process = None
        self.preview_thread = None
        self.buffer_thread = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("REC Edge - Live Capture Dashboard")
        self.resize(1200, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ── LEFT PANEL (Controls & Live Feed) ──
        left_panel = QFrame()
        left_panel.setProperty("class", "box")
        left_layout = QVBoxLayout(left_panel)
        
        # Header
        header = QLabel("PHOTOGRAPHER TERMINAL")
        header.setProperty("class", "title")
        user_lbl = QLabel(f"Logged in as: {self.email}")
        user_lbl.setStyleSheet("color: #888; font-weight: bold;")
        
        left_layout.addWidget(header)
        left_layout.addWidget(user_lbl)
        left_layout.addSpacing(20)
        
        # Camera Feed Overlay Container
        self.feed_container = QWidget()
        feed_layout = QVBoxLayout(self.feed_container)
        feed_layout.setContentsMargins(0,0,0,0)

        self.feed_label = QLabel("INITIALIZING CAMERA...")
        self.feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feed_label.setStyleSheet("background-color: #000; border: 2px solid #333;")
        self.feed_label.setMinimumSize(640, 480)
        self.feed_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        feed_layout.addWidget(self.feed_label)
        left_layout.addWidget(self.feed_container)
        
        # State display
        self.state_label = QLabel("Orchestrator Offline")
        self.state_label.setStyleSheet("color: #7bfa7b; font-weight: bold; font-family: monospace;")
        left_layout.addWidget(self.state_label)
        
        # Controls

        self.smile_toggle = QCheckBox("Require Smile")
        self.thumbs_toggle = QCheckBox("Require Thumbs Up")
        
        def update_reqs():
            if self.preview_thread:
                self.preview_thread.req_smile = self.smile_toggle.isChecked()
                self.preview_thread.req_thumbs = self.thumbs_toggle.isChecked()
                
        self.smile_toggle.stateChanged.connect(update_reqs)
        self.thumbs_toggle.stateChanged.connect(update_reqs)
        
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.smile_toggle)
        controls_layout.addWidget(self.thumbs_toggle)
        left_layout.addLayout(controls_layout)
        
        controls_layout = QHBoxLayout()

        self.cam_combo = QComboBox()
        self.cam_combo.setStyleSheet("padding: 5px; background: #333; color: white;")
        self.populate_cameras()
        self.cam_combo.currentTextChanged.connect(self.start_preview)
        
        self.toggle_orch_btn = QPushButton("START CAPTURE AI")
        self.toggle_orch_btn.clicked.connect(self.toggle_orchestrator)
        
        self.manual_btn = QPushButton("⚪ MANUAL SHUTTER")
        self.manual_btn.setStyleSheet("background-color: white; color: black; border-radius: 15px; font-weight: bold; padding: 10px;")
        self.manual_btn.clicked.connect(self.manual_capture)
        
        controls_layout.addWidget(QLabel("Target:"))
        controls_layout.addWidget(self.cam_combo)
        controls_layout.addWidget(self.toggle_orch_btn)
        controls_layout.addWidget(self.manual_btn)
        
        left_layout.addLayout(controls_layout)
        
        # ── RIGHT PANEL (Capture Grid) ──
        right_panel = QFrame()
        right_panel.setProperty("class", "box")
        right_layout = QVBoxLayout(right_panel)
        
        right_header = QHBoxLayout()
        grid_header = QLabel("LIVE CAPTURE BUFFER")
        grid_header.setProperty("class", "title")
        
        self.sync_toggle = QCheckBox("CLOUD AUTO-SYNC")
        self.sync_toggle.setStyleSheet("font-weight: bold; color: #7bfa7b;")
        
        right_header.addWidget(grid_header)
        right_header.addStretch()
        right_header.addWidget(self.sync_toggle)
        right_layout.addLayout(right_header)
        
        # Scroll Area for Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background: transparent;")
        
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)
        
        right_layout.addWidget(self.scroll_area)
        
        # Add to main
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 3)
        
        # Start background threads
        self.start_preview()
        self.start_buffer_polling()
        
        # Process monitor
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.check_orchestrator_status)
        self.process_timer.start(1000)
        
    def check_orchestrator_status(self):
        if self.orchestrator_process and self.orchestrator_process.poll() is not None:
            # Process crashed or stopped unexpectedly
            print(f"WARNING: Orchestrator process exited with code {self.orchestrator_process.poll()}")
            self.orchestrator_process = None
            self.toggle_orch_btn.setText("START CAPTURE AI")
            self.toggle_orch_btn.setStyleSheet("")

    def populate_cameras(self):
        """Scan for available cameras."""
        cameras = detect_available_cameras()
        self.cam_combo.clear()
        for cam in cameras:
            self.cam_combo.addItem(cam.get("label", cam["id"]), userData=cam["id"])

    def start_preview(self):
        if self.preview_thread:
            self.preview_thread.stop()
        
        cam_id = self.cam_combo.currentData() or self.cam_combo.currentText()
        self.preview_thread = CameraPreviewThread(cam_id)
        self.preview_thread.change_pixmap_signal.connect(self.update_image)
        self.preview_thread.start()
        

    def update_image(self, cv_img):
        qt_img = self.convert_cv_qt(cv_img)
        self.feed_label.setPixmap(qt_img)

        
    def convert_cv_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
        return QPixmap.fromImage(p)

    def start_buffer_polling(self):
        self.buffer_thread = BufferPollingThread()
        self.buffer_thread.new_photos_signal.connect(self.update_grid)
        self.buffer_thread.start()
        
    def update_grid(self, photos):
        # Clear layout safely
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)
                
        row, col = 0, 0
        for p in photos:
            # Container for image + button
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(0,0,0,0)
            vbox.setSpacing(5)
            
            # Thumbnail
            lbl = QLabel()
            pixmap = QPixmap(p["path"]).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            lbl.setPixmap(pixmap)
            
            # Delete Btn
            del_btn = QPushButton("DISCARD")
            del_btn.setProperty("class", "danger")
            del_btn.setStyleSheet("padding: 5px; font-size: 10px;")
            # Using lambda with default arg to capture current path
            del_btn.clicked.connect(lambda checked, path=p["path"]: self.discard_photo(path))
            
            vbox.addWidget(lbl)
            vbox.addWidget(del_btn)
            
            self.grid_layout.addWidget(container, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        # Handle uploading new files
        if self.sync_toggle.isChecked():
            current_paths = {p["path"] for p in photos}
            if not hasattr(self, 'uploaded_paths'):
                self.uploaded_paths = set()
            new_paths = current_paths - self.uploaded_paths
            
            for path in new_paths:
                self.upload_photo(path)
                self.uploaded_paths.add(path)

    def upload_photo(self, path):
        try:
            print(f"Uploading {path} to cloud...")
            with open(path, "rb") as f:
                resp = requests.post(
                    f"{CLOUD_API_URL}/upload",
                    files={"file": f},
                    data={"event": "EVT-UNKNOWN", "photographer": self.email},
                    timeout=5
                )
                if resp.status_code == 200:
                    print(f"Uploaded {path} successfully.")
        except Exception as e:
            print(f"Upload failed for {path}: {e}")

    def discard_photo(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Discarded: {path}")
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

    def manual_capture(self):
        filename = f"manual_{int(time.time())}.jpg"
        target_path = os.path.join(BUFFER_DIR, filename)
        
        # Grab current pixmap from feed_label
        pixmap = self.feed_label.pixmap()
        if pixmap:
            pixmap.save(target_path, "JPG")
            print(f"Manual capture saved to {target_path}")


    def toggle_orchestrator(self):
        if self.preview_thread:
            self.preview_thread.ai_active = not self.preview_thread.ai_active
            if self.preview_thread.ai_active:
                self.toggle_orch_btn.setText("STOP CAPTURE AI")
                self.toggle_orch_btn.setStyleSheet("background-color: #ff6b6b; border-color: #ff6b6b; color: white;")
                
                # Setup Toggles
                self.preview_thread.req_smile = getattr(self, 'smile_toggle', QCheckBox("Require Smile")).isChecked()
                self.preview_thread.req_thumbs = getattr(self, 'thumbs_toggle', QCheckBox("Require Thumbs Up")).isChecked()
            else:
                self.toggle_orch_btn.setText("START CAPTURE AI")
                self.toggle_orch_btn.setStyleSheet("")


    def closeEvent(self, event):
        if self.orchestrator_process:
            self.orchestrator_process.terminate()
        if self.preview_thread:
            self.preview_thread.stop()
        if self.buffer_thread:
            self.buffer_thread.stop()
        event.accept()

# ─────────────────────────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────────────────────────

class ApplicationManager:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyleSheet(STYLESHEET)
        
        self.login_window = LoginWindow(self.on_login_success)
        self.dashboard_window = None
        
    def run(self):
        self.login_window.show()
        sys.exit(self.app.exec())
        
    def on_login_success(self, email, token):
        self.login_window.hide()
        self.dashboard_window = DashboardWindow(email, token)
        self.dashboard_window.show()


if __name__ == "__main__":
    manager = ApplicationManager()
    manager.run()
