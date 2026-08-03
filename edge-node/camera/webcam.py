import os
import time
import cv2
import numpy as np
from .base import CameraDriver, CapturedImage

class WebcamDriver(CameraDriver):
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        # camera_id will be something like "Webcam_0"
        self.cam_index = int(camera_id.split('_')[-1]) if '_' in camera_id else 0
        self.cap = None
        self.connected = False
        self.buffer_dir = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")
        os.makedirs(self.buffer_dir, exist_ok=True)
        self.last_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def connect(self) -> bool:
        self.cap = cv2.VideoCapture(self.cam_index)
        if not self.cap.isOpened():
            print(f"[Webcam] Failed to connect to index {self.cam_index}")
            return False
        
        # Zero-latency configuration: avoid driver frame buffering
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.connected = True
        print(f"[Webcam] Connected to {self.camera_id} at index {self.cam_index}")
        return True

    def get_live_preview_frame(self) -> np.ndarray:
        if not self.connected or self.cap is None:
            raise Exception("Webcam not connected")
        ret, frame = self.cap.read()
        if ret:
            self.last_frame = frame
            return frame
        return self.last_frame

    def trigger_autofocus(self) -> bool:
        # Webcams usually have continuous autofocus, or we can't control it via standard OpenCV easily
        return True

    def capture_image(self) -> CapturedImage:
        if not self.connected:
            raise Exception("Webcam not connected")
        
        # Read the latest frame
        ret, frame = self.cap.read()
        if not ret:
            frame = self.last_frame
            
        timestamp = time.time()
        filename = f"capture_webcam_{int(timestamp)}.jpg"
        target_path = os.path.join(self.buffer_dir, filename)
        
        # Save frame to disk
        cv2.imwrite(target_path, frame)
        print(f"[Webcam] Captured {filename}")
        
        return CapturedImage(filepath=target_path, timestamp=timestamp, camera_id=self.camera_id)

    def disconnect(self):
        if self.cap:
            self.cap.release()
        self.connected = False

    # ─────────────────────────────────────────────────────────────────
    # DSLR Abstract Methods (No-Ops for standard Webcams)
    # ─────────────────────────────────────────────────────────────────
    def set_aperture(self, aperture: str) -> bool:
        return False

    def set_iso(self, iso: str) -> bool:
        return False

    def set_shutter_speed(self, speed: str) -> bool:
        return False
