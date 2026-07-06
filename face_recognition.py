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

@traceable(name="recognize_faces")
def recognize_faces(frame, threshold=0.4):
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
                e_arr = np.array(e)
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

    # Get the largest face by bounding box area
    faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
    best_face = faces[0]
    emb = best_face.normed_embedding.tolist()

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
