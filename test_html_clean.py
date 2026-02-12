from bot.analysis import _clean_telegram_html

def test_cleaning():
    # Test 1: Supported tags
    text = "<b>Bold</b> <i>Italic</i> <code>Code</code>"
    cleaned = _clean_telegram_html(text)
    assert cleaned == text, f"Failed supported tags: {cleaned}"
    print("✅ Supported tags passed")

    # Test 2: Unsupported ordered list
    text = """
    <ol>
        <li>Item 1</li>
        <li>Item 2</li>
    </ol>
    """
    expected = "  • Item 1\n  • Item 2"
    cleaned = _clean_telegram_html(text).strip()
    # Normalize whitespace for comparison
    cleaned = "\n".join([line.strip() for line in cleaned.split('\n') if line.strip()])
    expected = "\n".join([line.strip() for line in expected.split('\n') if line.strip()])
    assert cleaned == expected, f"Failed list cleaning:\nExpected:\n{expected}\nGot:\n{cleaned}"
    print("✅ List cleaning passed")

    # Test 3: Unsupported other tags
    text = "<h1>Header</h1> <p>Paragraph</p> <br>"
    cleaned = _clean_telegram_html(text)
    # Expect only content, no tags
    assert "<h1>" not in cleaned and "<p>" not in cleaned, f"Failed unsupported tags: {cleaned}"
    print("✅ Unsupported tags removal passed")
    
    # Test 4: Mixed
    text = "<b>Key:</b> <ol><li>Value</li></ol>"
    cleaned = _clean_telegram_html(text)
    assert "<b>Key:</b>" in cleaned and "• Value" in cleaned, f"Failed mixed content: {cleaned}"
    print("✅ Mixed content passed")

if __name__ == "__main__":
    try:
        test_cleaning()
        print("🎉 ALL HTML CLEANING TESTS PASSED")
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"❌ RUNTIME ERROR: {e}")
