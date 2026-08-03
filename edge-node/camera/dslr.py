import os
import time
import numpy as np
import cv2
try:
    import gphoto2 as gp
except ImportError:
    gp = None
from .base import CameraDriver, CapturedImage

class DSLRDriver(CameraDriver):
    def __init__(self, camera_id: str = "DSLR_01"):
        self.camera_id = camera_id
        self.camera = gp.Camera() if gp is not None else None
        self.connected = False
        self.buffer_dir = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")
        os.makedirs(self.buffer_dir, exist_ok=True)

    def connect(self) -> bool:
        if gp is None or self.camera is None:
            print(f"[DSLR] gphoto2 module is not installed. Cannot connect to DSLR.")
            return False
        try:
            self.camera.init()
            self.connected = True
            print(f"[DSLR] Connected to {self.camera_id}")
            return True
        except Exception as e:
            print(f"[DSLR] Connection failed: {e}")
            return False

    def get_live_preview_frame(self) -> np.ndarray:
        if not self.connected:
            raise Exception("DSLR not connected")
        try:
            camera_file = self.camera.capture_preview()
            file_data = camera_file.get_data_and_size()
            nparr = np.frombuffer(memoryview(file_data), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except gp.GPhoto2Error as e:
            print(f"[DSLR] Preview error: {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8)

    def trigger_autofocus(self) -> bool:
        if not self.connected: return False
        try:
            config = self.camera.get_config()
            OK, autofocus = gp.gp_widget_get_child_by_name(config, 'autofocusdrive')
            if OK >= gp.OK:
                autofocus.set_value(1)
                self.camera.set_config(config)
            return True
        except Exception:
            return False

    def capture_image(self) -> CapturedImage:
        if not self.connected:
            raise Exception("DSLR not connected")
        
        file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE)
        print(f"[DSLR] Captured {file_path.folder}/{file_path.name}")
        
        target_path = os.path.join(self.buffer_dir, file_path.name)
        camera_file = self.camera.file_get(
            file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
        camera_file.save(target_path)
        
        return CapturedImage(filepath=target_path, timestamp=time.time(), camera_id=self.camera_id)

    def set_aperture(self, aperture: str) -> bool:
        return self._set_config("aperture", aperture)

    def set_iso(self, iso: str) -> bool:
        return self._set_config("iso", iso)

    def set_shutter_speed(self, speed: str) -> bool:
        return self._set_config("shutterspeed", speed)

    def _set_config(self, config_name: str, value: str) -> bool:
        if not self.connected: return False
        try:
            config = self.camera.get_config()
            OK, widget = gp.gp_widget_get_child_by_name(config, config_name)
            if OK >= gp.OK:
                widget.set_value(value)
                self.camera.set_config(config)
                return True
        except Exception as e:
            print(f"[DSLR] Error setting {config_name}: {e}")
        return False
