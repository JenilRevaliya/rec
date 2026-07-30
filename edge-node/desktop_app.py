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

class CameraPreviewThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self._run_flag = True

    def run(self):
        # Instantiate correct driver for preview
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
                    self.change_pixmap_signal.emit(frame)
            except Exception as e:
                print(f"Preview error: {e}")
            time.sleep(0.06) # ~15 fps

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
        cameras = ["MOCK_CAM_01", "DSLR_01"]
        # Scan for local webcams (0 to 3)
        for i in range(4):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append(f"Webcam_{i}")
                cap.release()
        self.cam_combo.addItems(cameras)

    def start_preview(self):
        if self.preview_thread:
            self.preview_thread.stop()
        
        self.preview_thread = CameraPreviewThread(self.cam_combo.currentText())
        self.preview_thread.change_pixmap_signal.connect(self.update_image)
        self.preview_thread.start()
        
    def update_image(self, cv_img):
        # Read state to draw boxes
        state_file = "/tmp/rec_state.json"
        
        if self.orchestrator_process and os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                
                # Update status label
                gini = state.get("gini", 0)
                idle = state.get("global_idle", 0)
                msg = f"Global Idle: {idle:.1f}s | Fairness Gini: {gini:.2f}"
                if state.get("dancing"): msg += " [DANCE BURST MODE]"
                self.state_label.setText(msg)
                
                # Draw boxes
                for p in state.get("pids", []):
                    x1, y1, x2, y2 = p["bbox"]
                    color_tup = p.get("color", (0, 255, 0)) # BGR
                    # Draw rect
                    cv2.rectangle(cv_img, (x1, y1), (x2, y2), color_tup, 2)
                    
                    # Draw text background
                    label = f"{p['status']}: {p['reason']}"
                    (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(cv_img, (x1, y1 - 20), (x1 + w, y1), color_tup, -1)
                    # Draw text
                    cv2.putText(cv_img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0) if sum(color_tup)>300 else (255,255,255), 1)
            except Exception as e:
                pass
                
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
        if self.orchestrator_process:
            if self.orchestrator_process.poll() is None:
                # It's running, so stop it
                self.orchestrator_process.terminate()
                self.orchestrator_process = None
                self.toggle_orch_btn.setText("START CAPTURE AI")
                self.toggle_orch_btn.setStyleSheet("")
                print("Orchestrator stopped.")
            else:
                self.orchestrator_process = None # Clear dead process
        else:
            # Start it
            env = os.environ.copy()
            env["EDGE_API_TOKEN"] = self.token
            env["REC_CAMERA_ID"] = self.cam_combo.currentText()
            
            # Start python module orchestrator.main
            project_root = os.path.dirname(os.path.abspath(__file__))
            self.orchestrator_process = subprocess.Popen(
                [sys.executable, "-m", "orchestrator.main"],
                env=env,
                cwd=project_root
            )
            self.toggle_orch_btn.setText("STOP CAPTURE AI")
            self.toggle_orch_btn.setStyleSheet("background-color: #ff6b6b; border-color: #ff6b6b; color: white;")
            print("Orchestrator started.")

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
