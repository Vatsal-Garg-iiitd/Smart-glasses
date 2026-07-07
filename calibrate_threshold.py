import cv2
import numpy as np
import os
import glob
from face_recognition import init_face_analyzer, face_analyzer

def evaluate_thresholds():
    print("Threshold Calibration Script")
    print("To use this, create a folder 'eval_faces' with subfolders for each person (e.g. eval_faces/alice/1.jpg).")
    
    if not os.path.exists("eval_faces"):
        print("Skipping calibration: 'eval_faces' folder not found. Please create it and add test images.")
        return

    init_face_analyzer()
    
    # Load all images
    embeddings = {} # name -> list of embs
    for person_dir in glob.glob("eval_faces/*"):
        if os.path.isdir(person_dir):
            name = os.path.basename(person_dir)
            embeddings[name] = []
            for img_path in glob.glob(f"{person_dir}/*.jpg"):
                img = cv2.imread(img_path)
                if img is not None:
                    faces = face_analyzer.get(img)
                    if faces:
                        best_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
                        embeddings[name].append(best_face.normed_embedding)
                        
    if not embeddings:
        print("No valid faces found in eval_faces/")
        return
        
    print(f"Loaded faces for {len(embeddings)} people.")
    
    # Generate all pairs
    positive_pairs = [] # same person
    negative_pairs = [] # different people
    
    names = list(embeddings.keys())
    for i in range(len(names)):
        name1 = names[i]
        embs1 = embeddings[name1]
        
        # Positive pairs
        for j in range(len(embs1)):
            for k in range(j+1, len(embs1)):
                sim = np.dot(embs1[j], embs1[k])
                positive_pairs.append(sim)
                
        # Negative pairs
        for j in range(i+1, len(names)):
            name2 = names[j]
            embs2 = embeddings[name2]
            for emb1 in embs1:
                for emb2 in embs2:
                    sim = np.dot(emb1, emb2)
                    negative_pairs.append(sim)
                    
    print(f"Generated {len(positive_pairs)} positive pairs and {len(negative_pairs)} negative pairs.")
    
    if not positive_pairs or not negative_pairs:
        print("Need at least one positive pair (same person 2 photos) and one negative pair (2 people) to calibrate.")
        return
        
    print("\n--- Calibration Results ---")
    thresholds = [0.2, 0.3, 0.4, 0.5, 0.6]
    for t in thresholds:
        true_accepts = sum(1 for sim in positive_pairs if sim >= t)
        false_rejects = len(positive_pairs) - true_accepts
        
        false_accepts = sum(1 for sim in negative_pairs if sim >= t)
        true_rejects = len(negative_pairs) - false_accepts
        
        far = false_accepts / len(negative_pairs) if negative_pairs else 0
        frr = false_rejects / len(positive_pairs) if positive_pairs else 0
        
        print(f"Threshold: {t:.2f} | FAR: {far:.2%} | FRR: {frr:.2%}")

if __name__ == "__main__":
    evaluate_thresholds()
