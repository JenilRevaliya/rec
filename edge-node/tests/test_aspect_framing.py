import unittest
import numpy as np
from orchestrator.utils.aspect_framing import (
    compute_framing_box,
    parse_aspect_ratio,
    parse_framing_scale,
    compute_composition_score,
    _clean_config_string
)

class TestAspectFraming(unittest.TestCase):
    def setUp(self):
        self.frame_w = 640
        self.frame_h = 480

    def test_clean_config_string(self):
        self.assertEqual(_clean_config_string("16:9"), "16:9")
        self.assertEqual(_clean_config_string(b"9:16"), "9:16")
        self.assertEqual(_clean_config_string("b'1:1'"), "1:1")
        self.assertEqual(_clean_config_string('"4:3"'), "4:3")
        self.assertEqual(_clean_config_string(" AUTO "), "AUTO")

    def test_aspect_ratio_parsing(self):
        self.assertAlmostEqual(parse_aspect_ratio("16:9"), 16.0/9.0)
        self.assertAlmostEqual(parse_aspect_ratio("9:16"), 9.0/16.0)
        self.assertAlmostEqual(parse_aspect_ratio("1:1"), 1.0)
        self.assertAlmostEqual(parse_aspect_ratio("4:3"), 4.0/3.0)
        self.assertAlmostEqual(parse_aspect_ratio("3:4"), 3.0/4.0)
        self.assertAlmostEqual(parse_aspect_ratio("4:5"), 4.0/5.0)
        self.assertIsNone(parse_aspect_ratio("FULL"))

    def test_dynamic_tracking_left_to_right(self):
        # Person moving across sensor
        box_left = compute_framing_box([50, 100, 250, 400], self.frame_w, self.frame_h, "1:1", "AUTO")
        box_right = compute_framing_box([350, 100, 550, 400], self.frame_w, self.frame_h, "1:1", "AUTO")
        
        # Ensure left box is on the left and right box is on the right
        self.assertLess(box_left[0], box_right[0])
        self.assertLess(box_left[2], box_right[2])
        # Check aspect ratio 1:1
        w_left = box_left[2] - box_left[0]
        h_left = box_left[3] - box_left[1]
        self.assertAlmostEqual(w_left / float(h_left), 1.0, places=1)

    def test_dynamic_resizing_near_far(self):
        # Far person (small bbox) vs Near person (large bbox)
        box_far = compute_framing_box([270, 180, 370, 300], self.frame_w, self.frame_h, "1:1", "AUTO")
        box_near = compute_framing_box([150, 50, 450, 450], self.frame_w, self.frame_h, "1:1", "AUTO")
        
        area_far = (box_far[2] - box_far[0]) * (box_far[3] - box_far[1])
        area_near = (box_near[2] - box_near[0]) * (box_near[3] - box_near[1])
        
        self.assertLess(area_far, area_near)

    def test_sensor_bounds_containment(self):
        for ar in ["16:9", "9:16", "1:1", "4:3", "3:4", "4:5", "FULL"]:
            for scale in ["AUTO", "TIGHT", "MEDIUM", "WIDE", "FULL"]:
                box = compute_framing_box([10, 10, 630, 470], self.frame_w, self.frame_h, ar, scale)
                self.assertGreaterEqual(box[0], 0)
                self.assertGreaterEqual(box[1], 0)
                self.assertLessEqual(box[2], self.frame_w)
                self.assertLessEqual(box[3], self.frame_h)
                self.assertGreater(box[2], box[0])
                self.assertGreater(box[3], box[1])

if __name__ == '__main__':
    unittest.main()
