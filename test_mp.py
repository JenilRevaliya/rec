import cv2
import mediapipe as mp
print("Testing MP Tasks Vision...")
try:
    BaseOptions = mp.tasks.BaseOptions
    GestureRecognizer = mp.tasks.vision.GestureRecognizer
    GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    
    g_opts = GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path='model/gesture_recognizer.task'),
        running_mode=mp.tasks.vision.RunningMode.IMAGE)
    g_rec = GestureRecognizer.create_from_options(g_opts)
    
    f_opts = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path='model/face_landmarker.task'),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        output_face_blendshapes=True)
    f_rec = FaceLandmarker.create_from_options(f_opts)
    
    print("SUCCESS!")
except Exception as e:
    import traceback
    traceback.print_exc()
