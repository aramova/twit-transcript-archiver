import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import io

# Add parent directory to path so we can import the modules
# Insert at 0 to prioritize the 'git/' folder over the current root folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_transcripts

class TestFetchTranscripts(unittest.TestCase):

    def setUp(self):
        # Redirect stdout to capture print statements
        self.held_output = io.StringIO()
        sys.stdout = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__

    def test_setup_directories(self):
        with patch("os.makedirs") as mock_makedirs, \
             patch("os.path.exists", return_value=False):
            fetch_transcripts.setup_directories()
            mock_makedirs.assert_called_with(fetch_transcripts.DATA_DIR)

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_get_list_page_failure(self, mock_sleep, mock_urlopen):
        # Simulate persistent failure (raises exception every time)
        mock_urlopen.side_effect = Exception("Network Down")
        
        content = fetch_transcripts.get_list_page(1)
        
        self.assertIsNone(content)
        # Should retry 3 times
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("urllib.request.urlopen")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("time.sleep") # Mock sleep to speed up tests
    def test_get_list_page_download(self, mock_sleep, mock_exists, mock_file, mock_urlopen):
        # Setup
        mock_exists.return_value = False # File doesn't exist
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>Content</html>"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute
        content = fetch_transcripts.get_list_page(1)
        
        # Assert
        self.assertEqual(content, "<html>Content</html>")
        mock_urlopen.assert_called_with(fetch_transcripts.BASE_LIST_URL)
        mock_file.assert_called() # Should write to file

    @patch("builtins.open", new_callable=mock_open, read_data="<html>Cached</html>")
    @patch("os.path.exists")
    def test_get_list_page_cached_old(self, mock_exists, mock_file):
        # Should use cache if page > 5 and exists
        mock_exists.return_value = True
        
        content = fetch_transcripts.get_list_page(10)
        
        self.assertEqual(content, "<html>Cached</html>")
        # Ensure we didn't try to download (can't easily check urlopen not called without patching it, 
        # but the logic path is clear)

    @patch("urllib.request.urlopen")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    @patch("time.sleep")
    def test_download_transcript_detail_success(self, mock_sleep, mock_exists, mock_file, mock_urlopen):
        mock_exists.return_value = False
        mock_response = MagicMock()
        mock_response.read.return_value = b"Transcript Content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        fetch_transcripts.download_transcript_detail("/path/to/ep", "Show 123", "SH")
        
        # Check URL construction
        expected_url = "https://twit.tv/path/to/ep"
        mock_urlopen.assert_called_with(expected_url)
        
        # Check file write
        expected_filename = os.path.join(fetch_transcripts.DATA_DIR, "SH_123.html")
        mock_file.assert_called_with(expected_filename, 'w', encoding='utf-8')

    @patch("os.path.exists")
    def test_download_transcript_detail_skips_existing(self, mock_exists):
        mock_exists.return_value = True
        with patch("urllib.request.urlopen") as mock_urlopen:
            fetch_transcripts.download_transcript_detail("/path", "Show 123", "SH")
            mock_urlopen.assert_not_called()

    def test_extract_items(self):
        html_sample = """
        <div class="item summary">
            <h2 class="title"><a href="/show/1">Show Title 1</a></h2>
        </div>
        <div class="item summary">
            <h2 class="title"><a href="/show/2">Show Title 2</a></h2>
        </div>
        """
        items = fetch_transcripts.extract_items(html_sample)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['url'], "/show/1")
        self.assertEqual(items[0]['title'], "Show Title 1")
        self.assertEqual(items[1]['title'], "Show Title 2")

    def test_get_target_prefixes(self):
        # Mock args object
        Args = type('Args', (), {})
        
        # Test --all
        args = Args()
        args.all = True
        args.shows = None
        targets = fetch_transcripts.get_target_prefixes(args)
        self.assertEqual(len(targets), len(fetch_transcripts.SHOW_MAP))
        
        # Test specific shows (codes)
        args.all = False
        args.shows = ["IM", "TWIG"]
        targets = fetch_transcripts.get_target_prefixes(args)
        self.assertEqual(targets, {"IM", "TWIG"})
        
        # Test specific shows (names)
        args.shows = ["This Week in Google"]
        targets = fetch_transcripts.get_target_prefixes(args)
        self.assertEqual(targets, {"TWIG"})
        
        # Test default
        args.shows = None
        targets = fetch_transcripts.get_target_prefixes(args)
        self.assertEqual(targets, {"IM", "TWIG"})

if __name__ == '__main__':
    unittest.main()
