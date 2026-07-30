from abc import ABC, abstractmethod
from typing import Optional
import numpy as np
from dataclasses import dataclass

@dataclass
class CapturedImage:
    filepath: str
    timestamp: float
    camera_id: str

class CameraDriver(ABC):
    
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def get_live_preview_frame(self) -> np.ndarray:
        pass

    @abstractmethod
    def trigger_autofocus(self) -> bool:
        pass

    @abstractmethod
    def capture_image(self) -> CapturedImage:
        pass

    @abstractmethod
    def set_aperture(self, aperture: str) -> bool:
        pass

    @abstractmethod
    def set_iso(self, iso: str) -> bool:
        pass

    @abstractmethod
    def set_shutter_speed(self, speed: str) -> bool:
        pass

    def move_ptz(self, pan: float, tilt: float, zoom: float) -> bool:
        raise NotImplementedError("move_ptz is only supported on PTZ cameras")
