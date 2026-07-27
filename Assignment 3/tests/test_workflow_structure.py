from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from multi_agent_web_automation import _fallback_test_code


def test_fallback_test_code_uses_single_browser_session():
    locators = [
        {"css": "button.primary", "xpath": "//button[@class='primary']"},
        {"css": "input[name='email']", "xpath": "//input[@name='email']"},
    ]

    code = _fallback_test_code("https://example.com", locators)

    assert "def test_page_elements_visible()" in code
    assert code.count("page.goto(") == 1
    assert "for locator in LOCATORS" in code
