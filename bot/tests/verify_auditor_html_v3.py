
import sys
import unittest
import os
import re

# Add project root to path
sys.path.append(os.getcwd())

from bot.analysis import _clean_telegram_html

class TestAuditorFixesV3(unittest.TestCase):
    def test_empty_tags_removall(self):
        """Test removal of empty tags like <> and </>"""
        input_html = "Text <> with < > empty </ > tags"
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Empty Input]: '{input_html}'")
        print(f"[Empty Output]: '{cleaned}'")
        
        self.assertNotIn("<>", cleaned)
        self.assertNotIn("</>", cleaned)
        self.assertNotIn("&lt;&gt;", cleaned) # Should be removed, not escaped

    def test_allowed_tags_preservation(self):
        """Test that <b>, <i>, <code> are preserved"""
        input_html = "<b>Bold</b> <i>Italic</i> <code>Code</code>"
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Allowed Input]: '{input_html}'")
        print(f"[Allowed Output]: '{cleaned}'")
        
        self.assertIn("<b>Bold</b>", cleaned)
        self.assertIn("<i>Italic</i>", cleaned)
        self.assertIn("<code>Code</code>", cleaned)

    def test_disallowed_tags_stripping(self):
        """Test that <script>, <div>, etc are stripped but content remains (or is handled)"""
        input_html = "<script>alert('xss')</script><div>Div Content</div>"
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Disallowed Input]: '{input_html}'")
        print(f"[Disallowed Output]: '{cleaned}'")
        
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("<div>", cleaned)
        self.assertIn("alert('xss')", cleaned)
        self.assertIn("Div Content", cleaned)

    def test_broken_tags(self):
        """Test malformed tags"""
        input_html = "<b onclick=alert(1)>Bold</b>"
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Broken Input]: '{input_html}'")
        print(f"[Broken Output]: '{cleaned}'")
        
        self.assertIn("<b>Bold</b>", cleaned)

if __name__ == '__main__':
    unittest.main()
