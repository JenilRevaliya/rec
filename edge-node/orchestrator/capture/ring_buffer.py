from collections import deque
import numpy as np
import cv2
import time
import logging

logger = logging.getLogger(__name__)

class FrameRingBuffer:
    """
    Always-on circular buffer storing raw frames for retroactive capture.
    Memory footprint depends on resolution. To respect budget (~200MB max), 
    we implement in-memory JPEG compression if required, or keep raw 720p frames.
    """
    def __init__(self, max_seconds: float = 5.0, fps: int = 15, compress: bool = True):
        self.max_frames = int(max_seconds * fps)
        self.compress = compress
        # Use deque with maxlen for O(1) appending and automatic O(1) eviction
        self.buffer = deque(maxlen=self.max_frames)
        self.timestamps = deque(maxlen=self.max_frames)
        logger.info(f"[RingBuffer] Initialized for {self.max_frames} frames (Compress={self.compress})")

    def push(self, frame: np.ndarray):
        """Called every frame from the capture thread. O(1) amortized."""
        if self.compress:
            # Compress to JPEG in memory (Quality 85 drops 720p from ~2.7MB to ~80KB)
            success, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if success:
                self.buffer.append(encoded_frame)
            else:
                logger.error("[RingBuffer] Failed to compress frame.")
                return
        else:
            self.buffer.append(frame.copy())
            
        self.timestamps.append(time.monotonic())

    def backtrack(self, lookback_seconds: float = 1.0, candidates: int = 15) -> list:
        """
        Returns the last N frames.
        """
        n = min(candidates, len(self.buffer))
        if n == 0:
            return []
            
        raw_candidates = list(self.buffer)[-n:]
        
        # Decode if necessary
        if self.compress:
            decoded_candidates = []
            for item in raw_candidates:
                decoded_candidates.append(cv2.imdecode(item, cv2.IMREAD_COLOR))
            return decoded_candidates
            
        return raw_candidates

    @property
    def memory_usage_mb(self) -> float:
        """Estimated RAM usage."""
        if not self.buffer:
            return 0.0
        # For numpy arrays, check nbytes
        frame_bytes = self.buffer[0].nbytes
        return (frame_bytes * len(self.buffer)) / (1024 * 1024)
