import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print("="*50)
    print("REC Model Lab: Real-Time Face Embedding & Matching")
    print("="*50)
    print("Initializing InsightFace (AuraFace/ArcFace backend)...")
    
    # Initialize InsightFace
    # buffalo_l includes RetinaFace for detection and ArcFace/AuraFace for embeddings
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("Model loaded successfully!")
    
    # Find available cameras
    print("\nScanning for available cameras...")
    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(i)
            cap.release()
            
    if not available_cameras:
        print("Error: No cameras found!")
        return
        
    print("\nAvailable Camera Indices:")
    for idx in available_cameras:
        print(f"  [{idx}] Camera {idx}")
        
    if len(available_cameras) == 1:
        cam_idx = available_cameras[0]
        print(f"Only one camera found. Using Camera {cam_idx}.")
    else:
        try:
            cam_idx = int(input(f"\nEnter the camera index you want to use {available_cameras}: "))
            if cam_idx not in available_cameras:
                print("Invalid index. Using default (0).")
                cam_idx = available_cameras[0]
        except ValueError:
            print("Invalid input. Using default (0).")
            cam_idx = available_cameras[0]
            
    cap = cv2.VideoCapture(cam_idx)

    registered_embeddings = []
    registered_face_thumbs = []

    print("\nControls:")
    print("  [R] - Register face (saves current face embedding)")
    print("  [D] - Delete all registered faces")
    print("  [V] - Verify face (compares current face to registered faces)")
    print("  [Q] - Quit")
    print("\nOpening webcam window... Make sure to give terminal Camera permissions!")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        display_frame = frame.copy()
        
        # Display instructions
        cv2.putText(display_frame, "Press R to Register | V to Verify | Q to Quit", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
        if registered_embeddings:
            cv2.putText(display_frame, f"Status: {len(registered_embeddings)} FACE(S) REGISTERED", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)
            
            h, w = display_frame.shape[:2]
            thumb_size = 100
            margin = 10
            for idx, thumb in enumerate(registered_face_thumbs):
                y_offset = margin + idx * (thumb_size + margin)
                if y_offset + thumb_size > h:
                    break # Out of vertical space
                display_frame[y_offset:y_offset+thumb_size, w-thumb_size-margin:w-margin] = thumb
                # Add a label to the thumbnail
                cv2.putText(display_frame, f"P{idx+1}", (w-thumb_size-margin+5, y_offset+20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            cv2.putText(display_frame, "Status: NO FACE REGISTERED", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow('REC Model Lab', display_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('r'):
            print("\nDetecting face for registration...")
            faces = app.get(frame)
            if len(faces) == 0:
                print("❌ No faces detected! Try again.")
            else:
                # Get the largest face
                faces = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)
                emb = faces[0].embedding
                registered_embeddings.append(emb)
                
                box = faces[0].bbox.astype(int)
                face_crop = frame[max(0, box[1]):min(frame.shape[0], box[3]), max(0, box[0]):min(frame.shape[1], box[2])]
                if face_crop.size > 0:
                    thumb = cv2.resize(face_crop, (100, 100))
                    registered_face_thumbs.append(thumb)
                    
                print(f"✅ Success! Person {len(registered_embeddings)} registered. Embedding shape: {emb.shape}")
                
        elif key == ord('d'):
            registered_embeddings.clear()
            registered_face_thumbs.clear()
            print("\n🗑️ All registered faces deleted.")
            
                
        elif key == ord('v'):
            if not registered_embeddings:
                print("\n⚠️ Please register a face first (press R).")
                continue
                
            print("\nDetecting face for verification...")
            faces = app.get(frame)
            if len(faces) == 0:
                print("❌ No faces detected in current frame!")
            else:
                faces = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]), reverse=True)
                current_embedding = faces[0].embedding
                
                # Compute Cosine Similarity against all registered faces
                max_score = -1
                best_match_idx = -1
                for idx, reg_emb in enumerate(registered_embeddings):
                    score = cosine_similarity(reg_emb, current_embedding)
                    if score > max_score:
                        max_score = score
                        best_match_idx = idx
                
                score = max_score
                
                # InsightFace cosine thresholds generally: > 0.45 is a match for ArcFace
                match = f"YES (Person {best_match_idx+1})" if score > 0.45 else "NO (Unknown)"
                print(f"🧠 Match Score: {score:.4f} -> {match}")
                
                # Show result on screen briefly
                color = (0, 255, 0) if score > 0.45 else (0, 0, 255)
                cv2.putText(display_frame, f"SCORE: {score:.4f} ({match})", (10, 100), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 3)
                
                # Draw bounding box
                box = faces[0].bbox.astype(int)
                cv2.rectangle(display_frame, (box[0], box[1]), (box[2], box[3]), color, 2)
                
                cv2.imshow('REC Model Lab', display_frame)
                cv2.waitKey(2000) # Pause for 2 seconds to show result

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
