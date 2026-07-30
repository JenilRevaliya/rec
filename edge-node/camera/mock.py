import time
import os
import uuid
import numpy as np
import cv2
from .base import CameraDriver, CapturedImage

class MockCameraDriver(CameraDriver):
    def __init__(self, camera_id: str = "MOCK_CAM_01"):
        self.camera_id = camera_id
        self.connected = False
        self.buffer_dir = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")
        os.makedirs(self.buffer_dir, exist_ok=True)

    def connect(self) -> bool:
        print(f"[MockCamera] Connected to {self.camera_id}")
        self.connected = True
        return True

    def get_live_preview_frame(self) -> np.ndarray:
        # Return a simple black 640x480 image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "MOCK LIVE PREVIEW", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        return img

    def trigger_autofocus(self) -> bool:
        print(f"[MockCamera] Auto-focusing...")
        time.sleep(0.5)
        return True

    def capture_image(self) -> CapturedImage:
        if not self.connected:
            raise Exception("Camera not connected")
        
        # Simulate capture delay
        time.sleep(1.0)
        filename = f"mock_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(self.buffer_dir, filename)
        
        # Generate dummy 1080p image
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Fill with random noise for testing compression/transfer
        img[:] = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
        cv2.putText(img, "MOCK CAPTURE", (500, 540), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        cv2.imwrite(filepath, img)
        
        print(f"[MockCamera] Captured {filepath}")
        return CapturedImage(filepath=filepath, timestamp=time.time(), camera_id=self.camera_id)

    def set_aperture(self, aperture: str) -> bool:
        print(f"[MockCamera] Aperture set to {aperture}")
        return True

    def set_iso(self, iso: str) -> bool:
        print(f"[MockCamera] ISO set to {iso}")
        return True

    def set_shutter_speed(self, speed: str) -> bool:
        print(f"[MockCamera] Shutter speed set to {speed}")
        return True
