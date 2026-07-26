import pytest
from playwright.sync_api import sync_playwright, expect
import json

# Define the target URL and locators
TARGET_URL = "https://example.com"
LOCATORS = json.loads('''
[
  {
    "tag": "a",
    "text": "Learn more",
    "css": "a",
    "xpath": "//a"
  }
]
''')

# Define the test function
def test_page_elements_visible():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(TARGET_URL)

        # Iterate over the locators and add assertions
        for locator in LOCATORS:
            if locator["css"]:
                expect(page.locator(locator["css"])).to_be_visible()
            elif locator["xpath"]:
                expect(page.locator(locator["xpath"])).to_be_visible()
            elif locator["tag"]:
                expect(page.locator(f"{locator['tag']}")).to_be_visible()
            elif locator["text"]:
                expect(page.locator(f"text={locator['text']}")).to_be_visible()

        # Close the browser
        browser.close()