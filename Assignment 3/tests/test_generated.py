import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://demoblaze.com")
        yield page
        browser.close()

def test_page_elements_visible(page):
    locators = [
        {"tag": "button", "text": "\u00d7", "css": "button[aria-label=\"Close\"]", "xpath": "//button[@aria-label='Close']"},
        {"tag": "input", "text": "", "css": "input#recipient-email", "xpath": "//input[@id='recipient-email']"},
        {"tag": "input", "text": "", "css": "input#recipient-name", "xpath": "//input[@id='recipient-name']"},
        {"tag": "textarea", "text": "", "css": "textarea#message-text", "xpath": "//textarea[@id='message-text']"},
        {"tag": "button", "text": "Close", "css": "button[type=\"button\"]", "xpath": "//button[@type='button']"},
        {"tag": "input", "text": "", "css": "input#sign-username", "xpath": "//input[@id='sign-username']"},
        {"tag": "input", "text": "", "css": "input#sign-password", "xpath": "//input[@id='sign-password']"},
        {"tag": "input", "text": "", "css": "input#loginusername", "xpath": "//input[@id='loginusername']"},
        {"tag": "input", "text": "", "css": "input#loginpassword", "xpath": "//input[@id='loginpassword']"},
        {"tag": "button", "text": "", "css": "button[aria-label=\"Toggle navigation\"]", "xpath": "//button[@aria-label='Toggle navigation']"},
        {"tag": "a", "text": "PRODUCT STORE", "css": "a#nava", "xpath": "//a[@id='nava']"},
        {"tag": "a", "text": "Home\n(current)", "css": "a[href=\"index.html\"]", "xpath": "//a[@href='index.html']"},
        {"tag": "a", "text": "Contact", "css": "a[href=\"#\"]", "xpath": "//a[@href='#']"},
        {"tag": "a", "text": "Cart", "css": "a#cartur", "xpath": "//a[@id='cartur']"},
        {"tag": "a", "text": "Log in", "css": "a#login2", "xpath": "//a[@id='login2']"},
        {"tag": "a", "text": "Log out", "css": "a#logout2", "xpath": "//a[@id='logout2']"},
        {"tag": "a", "text": "", "css": "a#nameofuser", "xpath": "//a[@id='nameofuser']"},
        {"tag": "a", "text": "Sign up", "css": "a#signin2", "xpath": "//a[@id='signin2']"},
        {"tag": "a", "text": "Previous", "css": "a[href=\"#carouselExampleIndicators\"]", "xpath": "//a[@href='#carouselExampleIndicators']"},
        {"tag": "a", "text": "CATEGORIES", "css": "a#cat", "xpath": "//a[@id='cat']"},
        {"tag": "a", "text": "Phones", "css": "a#itemc", "xpath": "//a[@id='itemc']"},
        {"tag": "button", "text": "Previous", "css": "button#prev2", "xpath": "//button[@id='prev2']"},
        {"tag": "button", "text": "Next", "css": "button#next2", "xpath": "//button[@id='next2']"},
    ]

    for locator in locators:
        if locator['css']:
            try:
                page.locator(locator['css']).first.wait_for(state='visible')
                assert page.locator(locator['css']).first.is_visible()
            except:
                try:
                    page.locator(locator['xpath']).first.wait_for(state='visible')
                    assert page.locator(locator['xpath']).first.is_visible()
                except:
                    pytest.fail(f"Locator {locator['css']} or {locator['xpath']} not found or not visible")
        else:
            try:
                page.locator(locator['xpath']).first.wait_for(state='visible')
                assert page.locator(locator['xpath']).first.is_visible()
            except:
                pytest.fail(f"Locator {locator['xpath']} not found or not visible")