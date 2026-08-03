import multiprocessing as mp
import time
import logging
import cv2
import numpy as np

# We'll import the shared_pool we created
from orchestrator.memory.shared_pool import create_shared_frame

logger = logging.getLogger(__name__)

class CameraIngestionProcess:
    """
    Runs the camera driver in a dedicated background process.
    Reads frames at maximum hardware speed and writes them directly
    to a zero-copy shared memory buffer.
    """
    def __init__(self, camera_id: str, driver_class, buffer_name: str = "camera_frame_buffer_0", shape: tuple = (480, 640, 3)):
        self.camera_id = camera_id
        self.driver_class = driver_class
        self.buffer_name = buffer_name
        self.shape = shape
        
        # Multiprocessing primitives
        self.shutdown_event = mp.Event()
        self.new_frame_event = mp.Event()
        
        # We also pass a small multiprocessing Value to store the latest frame index
        self.frame_index = mp.Value('i', 0)
        
        self.process = mp.Process(target=self._run_loop, daemon=True)

    def start(self):
        self.process.start()

    def stop(self):
        self.shutdown_event.set()
        self.process.join(timeout=2.0)
        if self.process.is_alive():
            self.process.terminate()

    def _run_loop(self):
        """Runs entirely in the child process."""
        try:
            # Instantiate driver in the child process so resources (like cv2.VideoCapture)
            # aren't shared across process boundaries.
            driver = self.driver_class(self.camera_id)
            if not driver.connect():
                logger.warning(f"[Ingestion] Failed to connect camera {self.camera_id}. Falling back to MockCameraDriver...")
                from camera.mock import MockCameraDriver
                driver = MockCameraDriver(self.camera_id)
                driver.connect()

            # Allocate the shared memory block from the producer side
            mem, frame_view = create_shared_frame(name=self.buffer_name, shape=self.shape)
            
            logger.info(f"[Ingestion] Started capture loop for {self.camera_id} into {self.buffer_name}")
            
            local_idx = 0
            while not self.shutdown_event.is_set():
                # Read from hardware
                frame = driver.get_live_preview_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                # Resize if necessary to match the shared memory shape
                if frame.shape != self.shape:
                    frame = cv2.resize(frame, (self.shape[1], self.shape[0]), interpolation=cv2.INTER_NEAREST)
                
                # Zero-copy write: copy into the NumPy view backed by shared memory
                np.copyto(frame_view, frame)
                
                local_idx += 1
                with self.frame_index.get_lock():
                    self.frame_index.value = local_idx
                
                # Signal consumer
                self.new_frame_event.set()
                
        except Exception as e:
            logger.error(f"[Ingestion] Critical error in capture loop: {e}")
        finally:
            # Clean up
            try:
                driver.disconnect()
            except:
                pass
            try:
                mem.close()
                mem.unlink()
            except:
                pass
            logger.info("[Ingestion] Shutting down.")
