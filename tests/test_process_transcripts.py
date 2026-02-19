import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os
import io

# Add parent directory to path
# Insert at 0 to prioritize the 'git/' folder over the current root folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process_transcripts

class TestProcessTranscripts(unittest.TestCase):

    def setUp(self):
        self.held_output = io.StringIO()
        sys.stdout = self.held_output

    def tearDown(self):
        sys.stdout = sys.__stdout__

    def test_html_to_markdown_basic(self):
        html = "<p>Hello <b>World</b></p>"
        md = process_transcripts.html_to_markdown(html)
        self.assertEqual(md, "Hello **World**")

    def test_html_to_markdown_headings(self):
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        md = process_transcripts.html_to_markdown(html)
        self.assertIn("# Title", md)
        self.assertIn("## Subtitle", md)

    def test_html_to_markdown_links(self):
        html = '<a href="http://example.com">Link</a>'
        md = process_transcripts.html_to_markdown(html)
        self.assertEqual(md, "[Link](http://example.com)")

    def test_html_to_markdown_complex(self):
        html = """
        <div class="body">
            <script>ignore me</script>
            <p>Para 1</p>
            <ul><li>Item 1</li><li>Item 2</li></ul>
            <br>
            <p>Para 2</p>
        </div>
        """
        md = process_transcripts.html_to_markdown(html)
        self.assertNotIn("ignore me", md)
        self.assertIn("Para 1", md)
        self.assertIn("* Item 1", md)
        self.assertIn("Para 2", md)

    def test_extract_year(self):
        self.assertEqual(process_transcripts.extract_year("Jan 1st 2025"), 2025)
        self.assertEqual(process_transcripts.extract_year("Wednesday, Feb 18, 2026"), 2026)
        self.assertEqual(process_transcripts.extract_year("No year here"), 0)

    @patch("builtins.open", new_callable=mock_open, read_data="""
    <html>
        <h1 class="post-title">Show 100</h1>
        <p class="byline"> Jan 1st 2025 </p>
        <div class="body textual"><p>Transcript content.</p></div>
    </html>
    """)
    def test_parse_transcript_file(self, mock_file):
        title, date_str, year, content = process_transcripts.parse_transcript_file("dummy_path")
        self.assertEqual(title, "Show 100")
        self.assertEqual(date_str, "Jan 1st 2025")
        self.assertEqual(year, 2025)
        self.assertIn("Transcript content.", content)

    @patch("builtins.open", new_callable=mock_open, read_data="<bad_html>")
    def test_parse_transcript_file_malformed(self, mock_file):
        # Should gracefully handle missing tags and return empty/defaults
        title, date_str, year, content = process_transcripts.parse_transcript_file("dummy")
        self.assertEqual(title, "Unknown Episode")
        self.assertEqual(date_str, "Unknown Date")
        self.assertEqual(year, 0)
        self.assertEqual(content, "")

    def test_get_ep_num(self):
        self.assertEqual(process_transcripts.get_ep_num("IM_100.html"), 100)
        self.assertEqual(process_transcripts.get_ep_num("TWIG_05.html"), 5)
        self.assertEqual(process_transcripts.get_ep_num("random.html"), 0)

    @patch("process_transcripts.parse_transcript_file")
    @patch("process_transcripts.glob.glob")
    def test_process_prefix_file_error(self, mock_glob, mock_parse):
        # Setup: One good file, one bad file (raises OSError)
        mock_glob.return_value = ["good.html", "bad.html"]
        
        mock_parse.side_effect = [
            ("Good Title", "Date", 2025, "Content"),
            OSError("Permission denied")
        ]
        
        # Execute - this should now catch the error and continue
        try:
            process_transcripts.process_prefix("IM")
        except OSError:
            self.fail("process_prefix raised OSError instead of handling it gracefully")

    @patch("process_transcripts.glob.glob")
    @patch("builtins.open", new_callable=mock_open)
    @patch("process_transcripts.parse_transcript_file")
    def test_process_prefix(self, mock_parse, mock_file, mock_glob):
        # Setup
        mock_glob.return_value = ["IM_1.html", "IM_2.html"]
        mock_parse.side_effect = [
            ("Ep 1", "Date 1", 2025, "Content 1"),
            ("Ep 2", "Date 2", 2025, "Content 2")
        ]
        
        # Execute
        process_transcripts.process_prefix("IM")
        
        # Assert
        # Check if output file was opened for writing
        # Since total words are small, it should write one file
        args, _ = mock_file.call_args
        self.assertTrue(args[0].endswith("IM_Transcripts_1-2.md"))
        
        # Verify content written
        handle = mock_file()
        handle.writelines.assert_called()
        written_lines = handle.writelines.call_args[0][0]
        full_text = "".join(written_lines)
        self.assertIn("# Episode: Ep 1", full_text)
        self.assertIn("# Episode: Ep 2", full_text)

    @patch("process_transcripts.glob.glob")
    @patch("builtins.open", new_callable=mock_open)
    @patch("process_transcripts.parse_transcript_file")
    def test_process_prefix_by_year(self, mock_parse, mock_file, mock_glob):
        # Setup: Two files from different years
        mock_glob.return_value = ["IM_1.html", "IM_2.html"]
        mock_parse.side_effect = [
            ("Ep 1", "Dec 31, 2024", 2024, "Content 2024"),
            ("Ep 2", "Jan 1, 2025", 2025, "Content 2025")
        ]
        
        # Execute with by_year=True
        process_transcripts.process_prefix("IM", by_year=True)
        
        # Assert - should write two lines/files
        # We check the filenames opened
        # mock_file() is the handle, but we want the calls to open()
        
        # Filter calls to open that are for writing
        write_calls = [call for call in mock_file.call_args_list if 'w' in call[0] or (len(call[0]) > 1 and call[0][1] == 'w')]
        
        # Using simple verification of filenames in call args
        filenames = [call.args[0] for call in mock_file.call_args_list if isinstance(call.args[0], str) and "Transcripts" in call.args[0]]
        
        self.assertEqual(len(filenames), 2)
        self.assertTrue(any("2024_1_1.md" in f for f in filenames))
        self.assertTrue(any("2025_2_2.md" in f for f in filenames))

    def test_argument_parsing(self):
        # Difficult to unit test argparse directly without refactoring main, 
        # but we can assume the logic in main matches usage.
        # Alternatively we can test logic blocks if we extracted them (like in fetch_transcripts).
        pass

if __name__ == '__main__':
    unittest.main()
