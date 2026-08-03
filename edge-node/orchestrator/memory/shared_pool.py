import multiprocessing.shared_memory as shm
import multiprocessing as mp
import threading
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def create_shared_frame(name: str, shape: tuple, dtype=np.uint8) -> Tuple[shm.SharedMemory, np.ndarray]:
    """
    Allocates a zero-copy shared memory block for a video frame.
    To be used by the Producer (Camera Capture Process).
    
    Args:
        name: Unique name for the shared memory block (e.g., 'camera_frame_buffer_0')
        shape: Dimensions of the frame (e.g., (720, 1280, 3))
        dtype: NumPy data type, defaults to uint8
        
    Returns:
        Tuple containing the SharedMemory object and the NumPy array view.
    """
    try:
        # Calculate exact byte size needed
        nbytes = int(np.prod(shape)) * np.dtype(dtype).itemsize
        
        # Clean up existing block if it was left dangling
        try:
            existing = shm.SharedMemory(name=name)
            existing.unlink()
        except FileNotFoundError:
            pass
            
        mem = shm.SharedMemory(name=name, create=True, size=nbytes)
        frame_view = np.ndarray(shape, dtype=dtype, buffer=mem.buf)
        return mem, frame_view
    except Exception as e:
        logger.error(f"Failed to create shared memory block '{name}': {e}")
        raise

def attach_shared_frame(name: str, shape: tuple, dtype=np.uint8) -> Tuple[shm.SharedMemory, np.ndarray]:
    """
    Attaches to an existing shared memory block.
    To be used by the Consumer (AI Inference Process).
    
    Args:
        name: Unique name of the existing shared memory block
        shape: Dimensions of the frame
        dtype: NumPy data type
        
    Returns:
        Tuple containing the SharedMemory object and the NumPy array view.
    """
    try:
        mem = shm.SharedMemory(name=name, create=False)
        frame_view = np.ndarray(shape, dtype=dtype, buffer=mem.buf)
        return mem, frame_view
    except Exception as e:
        logger.error(f"Failed to attach to shared memory block '{name}': {e}")
        raise

class LatestFrameBuffer:
    """
    Thread-safe single-slot LIFO buffer.
    Guarantees the AI always processes the freshest frame, completely avoiding backpressure lag.
    Writers never block. Readers always get the newest data.
    """
    def __init__(self):
        self._frame_index = None
        self._metadata = None
        self._lock = threading.Lock()
        self._new_frame_event = threading.Event()

    def write(self, frame_index: int, metadata: dict = None):
        """
        Overwrites the current slot with the newest frame index/metadata.
        Discards the old frame if it hasn't been read.
        """
        with self._lock:
            self._frame_index = frame_index
            self._metadata = metadata
        self._new_frame_event.set()

    def read(self, timeout: float = None) -> Tuple[Optional[int], Optional[dict]]:
        """
        Waits for a new frame and reads it.
        Returns (None, None) if timeout occurs.
        """
        if self._new_frame_event.wait(timeout):
            with self._lock:
                idx, meta = self._frame_index, self._metadata
                self._new_frame_event.clear()
            return idx, meta
        return None, None
