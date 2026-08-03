import numpy as np
import collections
import logging

logger = logging.getLogger(__name__)

class TemporalFeatureBuffer:
    """
    Tracks a rolling window of normalized pose keypoints for active PIDs.
    Used as the input feature vector for the Key Moment GRU classifier.
    """
    def __init__(self, window_size: int = 30, num_keypoints: int = 17, dims: int = 2):
        self.window_size = window_size
        self.num_keypoints = num_keypoints
        self.dims = dims
        # Dictionary of {pid: collections.deque(maxlen=window_size)}
        self.history = {}

    def update(self, pid: str, keypoints: np.ndarray, bbox: tuple):
        """
        Normalize keypoints relative to the bounding box and store in history.
        keypoints shape: (17, 2) or (17, 3) where the 3rd is confidence.
        bbox: (x1, y1, x2, y2)
        """
        if pid not in self.history:
            self.history[pid] = collections.deque(maxlen=self.window_size)

        x1, y1, x2, y2 = bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)

        # Normalize keypoints to [0, 1] relative to the bbox top-left
        normalized = np.zeros((self.num_keypoints, self.dims), dtype=np.float32)
        for i in range(min(self.num_keypoints, len(keypoints))):
            kp_x, kp_y = keypoints[i][:2]
            
            # If keypoint is (0,0), it's likely occluded/unseen. We can leave it as 0
            if kp_x == 0 and kp_y == 0:
                normalized[i] = [0.0, 0.0]
            else:
                norm_x = (kp_x - x1) / width
                norm_y = (kp_y - y1) / height
                # Clamp to [0, 1] to handle slight out-of-bounds estimations
                normalized[i] = [max(0.0, min(1.0, norm_x)), max(0.0, min(1.0, norm_y))]

        self.history[pid].append(normalized)

    def get_features(self, pid: str) -> np.ndarray:
        """
        Retrieves the (30, 17, 2) array for the GRU model.
        If history is less than window_size, pads with the first frame (standing still assumption).
        Returns None if no history exists for the PID.
        """
        if pid not in self.history or len(self.history[pid]) == 0:
            return None

        frames = list(self.history[pid])
        
        # Pad sequence if it's too short
        while len(frames) < self.window_size:
            frames.insert(0, frames[0])
            
        # Shape: (1, window_size, num_keypoints * dims) for standard RNN input
        feature_vector = np.array(frames, dtype=np.float32).reshape(1, self.window_size, -1)
        return feature_vector

    def remove_pid(self, pid: str):
        if pid in self.history:
            del self.history[pid]


class KeyMomentClassifier:
    """
    Wraps the ONNX GRU model to detect domain-specific moments (handshakes, spins).
    """
    def __init__(self, model_path: str = "models/key_moment_gru.onnx", threshold: float = 0.85):
        self.threshold = threshold
        self.model_loaded = False
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.model_loaded = True
            logger.info(f"[KeyMoment] Loaded GRU classifier from {model_path}")
        except Exception as e:
            logger.warning(f"[KeyMoment] Could not load ONNX model (fallback to mock). Reason: {e}")

    def predict(self, feature_vector: np.ndarray) -> bool:
        """
        Returns True if a key moment is detected above the confidence threshold.
        """
        if not self.model_loaded or feature_vector is None:
            return False

        try:
            # Output is expected to be a single probability float for binary classification
            output = self.session.run(None, {self.input_name: feature_vector})
            prob = output[0][0][0]
            return prob >= self.threshold
        except Exception as e:
            logger.error(f"[KeyMoment] Inference error: {e}")
            return False
