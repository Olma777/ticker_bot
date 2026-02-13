
import sys
import unittest
import os
import re

# Add project root to path
sys.path.append(os.getcwd())

from bot.analysis import _clean_telegram_html

class TestAuditorFixesV2(unittest.TestCase):
    def test_ordered_list_conversion(self):
        """Test <ol> -> 1. 2. 3. conversion"""
        input_html = """
        Analysis:
        <ol>
            <li><strong>Trend:</strong> Up</li>
            <li><strong>RSI:</strong> 60</li>
        </ol>
        """
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[OL Input]:\n{input_html}")
        print(f"[OL Output]:\n{cleaned}")
        
        self.assertIn("1. <b>Trend:</b> Up", cleaned)
        self.assertIn("2. <b>RSI:</b> 60", cleaned)
        self.assertNotIn("<ol>", cleaned)
        self.assertNotIn("<li>", cleaned)

    def test_unordered_list_conversion(self):
        """Test <ul> -> • conversion"""
        input_html = """
        <ul>
            <li>Support at 2000</li>
            <li>Resistance at 2100</li>
        </ul>
        """
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[UL Input]:\n{input_html}")
        print(f"[UL Output]:\n{cleaned}")
        
        self.assertIn("• Support at 2000", cleaned)
        self.assertIn("• Resistance at 2100", cleaned)

    def test_mixed_content_and_headers(self):
        """Test headers and headings"""
        input_html = "<h1>Title</h1><p>Paragraph</p>"
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Mixed Input]:\n{input_html}")
        print(f"[Mixed Output]:\n{cleaned}")
        
        self.assertIn("<b>Title</b>", cleaned)
        self.assertNotIn("<h1>", cleaned)
        self.assertNotIn("<p>", cleaned)

    def test_injection_safety(self):
        """Test script injection with new logic"""
        input_html = '<script>alert(1)</script> <b>Bold</b>'
        cleaned = _clean_telegram_html(input_html)
        print(f"\n[Injection Input]:\n{input_html}")
        print(f"[Injection Output]:\n{cleaned}")
        
        self.assertIn("&lt;script&gt;", cleaned)
        self.assertIn("<b>Bold</b>", cleaned)

if __name__ == '__main__':
    unittest.main()
