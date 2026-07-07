import cv2
import numpy as np
import logging
from langsmith import traceable

# We will lazily load insightface so it doesn't slow down global imports
face_analyzer = None
enrolled_faces_cache = None

def init_face_analyzer():
    global face_analyzer
    if face_analyzer is None:
        from insightface.app import FaceAnalysis
        logging.info("[FACE] Initializing FaceAnalysis (buffalo_sc)...")
        # using 'buffalo_sc' for better speed on constrained hardware
        face_analyzer = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
        # det_size limits the max image size for detection to speed it up
        face_analyzer.prepare(ctx_id=0, det_size=(320, 320))
        logging.info("[FACE] FaceAnalysis initialized.")

def update_enrolled_faces_cache():
    global enrolled_faces_cache
    from ai import db, init_firebase
    init_firebase()
    ref = db.reference("enrolled_faces")
    data = ref.get()
    enrolled_faces_cache = data if data else {}
    logging.info(f"[FACE] Enrolled cache updated: {len(enrolled_faces_cache)} people")

import os

# Configurable match threshold, default 0.4
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.4"))

@traceable(name="recognize_faces")
def recognize_faces(frame, threshold=FACE_MATCH_THRESHOLD):
    """
    Detect faces in a raw numpy frame and recognize them via cosine similarity
    against Firebase-stored embeddings.
    """
    global face_analyzer, enrolled_faces_cache
    if face_analyzer is None:
        init_face_analyzer()
    if enrolled_faces_cache is None:
        update_enrolled_faces_cache()

    faces = face_analyzer.get(frame)
    results = []

    for face in faces:
        emb = face.normed_embedding
        best_match = "Unknown"
        best_sim = -1.0

        # Compare against all enrolled embeddings
        for name, data in enrolled_faces_cache.items():
            enrolled_embs = data.get("embeddings", [])
            for e in enrolled_embs:
                e_arr = np.array(e, dtype=np.float32) # Explicit float32 cast (P2.7)
                sim = np.dot(emb, e_arr)
                if sim > best_sim:
                    best_sim = float(sim)
                    if sim >= threshold:
                        best_match = name

        results.append({
            "bbox": face.bbox.tolist(), # [x1, y1, x2, y2]
            "name": best_match,
            "confidence": best_sim
        })

    logging.info(f"[FACE] Detected {len(faces)} faces: {[r['name'] for r in results]}")
    return results

def enroll_face(name, frame):
    """
    Detects the largest face in the frame and enrolls its embedding to Firebase.
    Returns True if successful, raises ValueError otherwise.
    """
    global face_analyzer
    if face_analyzer is None:
        init_face_analyzer()

    faces = face_analyzer.get(frame)
    if not faces:
        raise ValueError("No face detected in the image.")
        
    # P2.9: Multiple faces disambiguation
    if len(faces) > 1:
        raise ValueError("Multiple faces detected. Please ensure only the person being enrolled is in the frame.")

    # P2.8: Image quality gate
    best_face = faces[0]
    
    # Check detection confidence
    if best_face.det_score < 0.6:
        raise ValueError(f"Face detection confidence too low ({best_face.det_score:.2f}). Please ensure good lighting and look straight at the camera.")
        
    # Check face bounding box area (width * height)
    bbox_width = best_face.bbox[2] - best_face.bbox[0]
    bbox_height = best_face.bbox[3] - best_face.bbox[1]
    if bbox_width * bbox_height < 10000:
        raise ValueError("Face is too small in the frame. Please move closer to the camera.")
        
    # Check blur (variance of Laplacian on the cropped face)
    x1, y1, x2, y2 = map(int, best_face.bbox)
    # Ensure coordinates are within image bounds
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(frame.shape[1], x2); y2 = min(frame.shape[0], y2)
    face_crop = frame[y1:y2, x1:x2]
    
    if face_crop.size > 0:
        gray_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
        if blur_score < 50.0: # Threshold for blurriness
            raise ValueError("Face image is too blurry. Please hold still.")

    # P2.7: Explicit float casting for robust JSON serialization
    emb = [float(x) for x in best_face.normed_embedding.tolist()]

    from ai import db, init_firebase
    init_firebase()
    ref = db.reference(f"enrolled_faces/{name}")
    data = ref.get() or {"embeddings": []}
    data["embeddings"].append(emb)
    ref.set(data)

    update_enrolled_faces_cache()
    return True

def delete_enrollment(name):
    """Deletes a person from the enrolled faces database."""
    from ai import db, init_firebase
    init_firebase()
    ref = db.reference(f"enrolled_faces/{name}")
    ref.delete()
    update_enrolled_faces_cache()
    return True
