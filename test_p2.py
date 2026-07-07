import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import cv2
import face_recognition

class TestP2Fixes(unittest.TestCase):

    def test_p2_7_firebase_serialization(self):
        """Test that numpy float32 arrays serialize to float lists and back safely."""
        original_emb = np.random.rand(128).astype(np.float32)
        
        # Serialize like we do before sending to Firebase
        serialized = [float(x) for x in original_emb.tolist()]
        
        # This is pure python types
        self.assertIsInstance(serialized[0], float)
        
        # Deserialize like we do when reading from Firebase
        deserialized = np.array(serialized, dtype=np.float32)
        
        # Verify shape and values
        self.assertEqual(deserialized.shape, (128,))
        np.testing.assert_allclose(original_emb, deserialized, atol=1e-6)

    @patch('face_recognition.face_analyzer')
    def test_p2_8_image_quality_small_face(self, mock_analyzer):
        """Test quality gate rejects small faces."""
        face = MagicMock()
        face.det_score = 0.99
        # Width 50, Height 50 = Area 2500 (< 10000 threshold)
        face.bbox = np.array([0, 0, 50, 50])
        mock_analyzer.get.return_value = [face]
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with self.assertRaisesRegex(ValueError, "Face is too small"):
            face_recognition.enroll_face("test_user", frame)
            
    @patch('face_recognition.face_analyzer')
    def test_p2_8_image_quality_low_confidence(self, mock_analyzer):
        """Test quality gate rejects low confidence detections."""
        face = MagicMock()
        face.det_score = 0.5 # (< 0.6 threshold)
        mock_analyzer.get.return_value = [face]
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with self.assertRaisesRegex(ValueError, "confidence too low"):
            face_recognition.enroll_face("test_user", frame)

    @patch('face_recognition.face_analyzer')
    def test_p2_9_multiple_faces(self, mock_analyzer):
        """Test enrollment disambiguation rejects frames with >1 face."""
        face1 = MagicMock()
        face2 = MagicMock()
        mock_analyzer.get.return_value = [face1, face2]
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with self.assertRaisesRegex(ValueError, "Multiple faces detected"):
            face_recognition.enroll_face("test_user", frame)

if __name__ == '__main__':
    unittest.main()
