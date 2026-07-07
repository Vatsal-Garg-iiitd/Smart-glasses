import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
import main
import ai

class TestBugfixes(unittest.IsolatedAsyncioTestCase):

    @patch("main.run_analysis", new_callable=AsyncMock)
    @patch("main.fetch_recent_chat_history")
    async def test_issue3_and_4_navigation_mode(self, mock_fetch, mock_run_analysis):
        """
        Verify Issue 3 (try/except wrapper) and Issue 4 (no unconditional Firebase read).
        When mode="navigation", run_analysis exception should become a 502 HTTPException.
        Also, fetch_recent_chat_history should NOT be called.
        """
        mock_run_analysis.side_effect = Exception("Camera disconnected")
        
        req = main.AnalyzeRequest(mode="navigation")
        
        with self.assertRaises(HTTPException) as context:
            await main.analyze(req)
            
        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(context.exception.detail, "I'm having trouble analyzing the scene right now. Please try again.")
        
        mock_fetch.assert_not_called()

    @patch("main.run_analysis", new_callable=AsyncMock)
    @patch("main.triage_query", return_value=True)
    @patch("main.fetch_recent_chat_history", return_value=[])
    async def test_issue3_and_4_ask_mode(self, mock_fetch, mock_triage, mock_run_analysis):
        """
        When mode="ask", fetch_recent_chat_history SHOULD be called (Issue 4).
        And if run_analysis fails, it should also return a 502 (Issue 3).
        """
        mock_run_analysis.side_effect = Exception("Gemini failure")
        
        req = main.AnalyzeRequest(mode="ask", prompt="What's in front of me?")
        
        with self.assertRaises(HTTPException) as context:
            await main.analyze(req)
            
        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(context.exception.detail, "I'm having trouble processing the image. Please try again.")
        
        mock_fetch.assert_called_once()

    @patch("ai.save_capture_metadata")
    @patch("ai.init_camera", return_value=True)
    @patch("ai.capture_image", return_value=(True, None)) # success, frame
    @patch("ai.process_image", return_value="A test scene.")
    async def test_issue5_timestamp_format(self, mock_process, mock_capture, mock_init, mock_save):
        """
        Verify Issue 5: ai.run_analysis calls save_capture_metadata with an integer timestamp.
        """
        # Call the async function directly
        result = await ai.run_analysis("read")
        
        # Check that save_capture_metadata was called
        mock_save.assert_called_once()
        
        # The third positional argument (or kwarg 'timestamp') should be an integer
        call_kwargs = mock_save.call_args.kwargs
        self.assertIn("timestamp", call_kwargs)
        self.assertIsInstance(call_kwargs["timestamp"], int)
        # Should be a very large integer (epoch ms)
        self.assertGreater(call_kwargs["timestamp"], 1700000000000)

if __name__ == "__main__":
    unittest.main()
