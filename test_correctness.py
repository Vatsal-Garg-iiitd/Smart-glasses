import unittest
import numpy as np
import cv2
import urllib.request
import os
from insightface.app import FaceAnalysis

class TestFaceCorrectness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
        cls.app.prepare(ctx_id=0, det_size=(320, 320))
        
        # Download a test face
        cls.img_path = "test_align_face.jpg"
        if not os.path.exists(cls.img_path):
            url = "https://upload.wikimedia.org/wikipedia/commons/3/33/Tom_Cruise_by_Gage_Skidmore_2.jpg"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(cls.img_path, 'wb') as out_file:
                out_file.write(response.read())
                
        cls.img = cv2.imread(cls.img_path)

    def test_p1_6_l2_normalization(self):
        """Verify L2 norm of the returned embedding is exactly 1.0"""
        faces = self.app.get(self.img)
        self.assertTrue(len(faces) > 0)
        
        emb = faces[0].normed_embedding
        norm = np.linalg.norm(emb)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_p1_5_affine_alignment(self):
        """
        Verify the system internally aligns faces.
        If we slightly rotate the image, the affine transform should cancel it out,
        so the embedding similarity to the unrotated image should remain very high.
        """
        # Get baseline embedding
        faces_base = self.app.get(self.img)
        emb_base = faces_base[0].normed_embedding
        
        # Rotate image slightly
        h, w = self.img.shape[:2]
        M = cv2.getRotationMatrix2D((w/2, h/2), 15, 1.0) # rotate 15 degrees
        rotated = cv2.warpAffine(self.img, M, (w, h))
        
        faces_rot = self.app.get(rotated)
        self.assertTrue(len(faces_rot) > 0)
        
        emb_rot = faces_rot[0].normed_embedding
        
        # Calculate similarity
        sim = np.dot(emb_base, emb_rot)
        
        # If alignment wasn't happening, the raw pixels would be drastically different,
        # and cosine similarity would drop significantly (e.g. < 0.5)
        # With alignment, the model corrects for rotation and similarity remains > 0.8
        self.assertGreater(sim, 0.80)

if __name__ == '__main__':
    unittest.main()
