import queue
import threading
import logging
import traceback
from typing import Callable

logger = logging.getLogger(__name__)

class AsyncIOWorker:
    """
    Non-blocking I/O worker.
    Ensures that the main AI inference loop never blocks on disk writes (JSON, JPEG)
    or network requests (Cloud upload, Telemetry).
    """
    def __init__(self, maxsize: int = 100, num_threads: int = 2):
        self.queue = queue.Queue(maxsize=maxsize)
        self.threads = []
        self._stop_event = threading.Event()
        
        for i in range(num_threads):
            t = threading.Thread(target=self._worker, name=f"IOWorker-{i}", daemon=True)
            t.start()
            self.threads.append(t)

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                # Block for a short time to allow checking the stop event
                task = self.queue.get(timeout=0.5)
                try:
                    task()
                except Exception as e:
                    logger.error(f"[IOWorker] Task execution error: {e}")
                    logger.error(traceback.format_exc())
                finally:
                    self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[IOWorker] Critical worker error: {e}")

    def submit(self, task_fn: Callable):
        """
        Submit a callable to be executed asynchronously.
        If the queue is full, the task is dropped to prevent backpressure.
        """
        try:
            self.queue.put_nowait(task_fn)
        except queue.Full:
            logger.warning("[IOWorker] Queue is full! Dropping I/O task to maintain real-time performance.")

    def stop(self):
        self._stop_event.set()
        for t in self.threads:
            t.join(timeout=1.0)

# Global singleton instance for easy imports across the orchestrator
io_worker = AsyncIOWorker()
