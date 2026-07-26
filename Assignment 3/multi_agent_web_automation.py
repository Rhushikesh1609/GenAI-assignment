from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TypedDict

from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from playwright.sync_api import sync_playwright


class WorkflowState(TypedDict):
    url: str
    locators: list[dict]
    test_code: str


def build_llm() -> ChatGroq | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=api_key,
    )


llm: ChatGroq | None = None


def get_llm() -> ChatGroq | None:
    global llm
    if llm is None:
        llm = build_llm()
    return llm


def scraper_node(state: WorkflowState) -> dict:
    url = state["url"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")

        locator_payload = page.evaluate(
            """
            () => {
                const selector = 'button, input:not([type="hidden"]), select, textarea, a[href]';
                const elements = Array.from(document.querySelectorAll(selector));
                const results = [];
                const seen = new Set();

                const toCssSelector = (el) => {
                    const tag = el.tagName.toLowerCase();
                    let selector = tag;
                    if (el.id) {
                        selector += '#' + el.id.replace(/\\s+/g, '_');
                    }
                    if (el.name) {
                        selector += `[name="${el.name}"]`;
                    }
                    if (el.getAttribute('type')) {
                        selector += `[type="${el.getAttribute('type')}"]`;
                    }
                    return selector;
                };

                const toXPath = (el) => {
                    const tag = el.tagName.toLowerCase();
                    let xpath = `//${tag}`;
                    if (el.id) {
                        xpath += `[@id='${el.id}']`;
                    }
                    if (el.name) {
                        xpath += `[@name='${el.name}']`;
                    }
                    if (el.getAttribute('type')) {
                        xpath += `[@type='${el.getAttribute('type')}']`;
                    }
                    return xpath;
                };

                for (const element of elements.slice(0, 10)) {
                    const text = (element.innerText || element.textContent || element.getAttribute('aria-label') || '').toString().trim();
                    const css = toCssSelector(element);
                    const xpath = toXPath(element);
                    const key = `${css}:${xpath}`;
                    if (seen.has(key)) {
                        continue;
                    }
                    seen.add(key);
                    results.push({
                        'tag': element.tagName.toLowerCase(),
                        'text': text.slice(0, 80),
                        'css': css,
                        'xpath': xpath,
                    });
                }
                return results;
            }
            """
        )

        browser.close()

    return {"locators": locator_payload}


def _extract_python_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def _fallback_test_code(url: str, locators: list[dict]) -> str:
    lines = [
        "from playwright.sync_api import sync_playwright, expect",
        "",
        "",
        "def test_page_elements_visible():",
        "    with sync_playwright() as playwright:",
        f"        browser = playwright.chromium.launch(headless=True)",
        "        page = browser.new_page()",
        f"        page.goto('{url}', wait_until='domcontentloaded')",
    ]

    for locator in locators:
        selector = locator.get("css") or locator.get("xpath")
        lines.append(f"        expect(page.locator('{selector}')).to_be_visible()")

    lines.extend(["        browser.close()"])
    return "\n".join(lines)


def tester_node(state: WorkflowState) -> dict:
    locators = state["locators"]
    prompt = f"""
You are a QA engineer. Create a complete, valid pytest test file using playwright.sync_api.
The target URL is: {state['url']}
The interactive element locators are provided as JSON:
{json.dumps(locators, indent=2)}

Requirements:
- Use sync_playwright()
- Navigate to the URL
- Define a single test function named test_page_elements_visible()
- For each provided locator, add a basic assertion: expect(page.locator(...)).to_be_visible()
- Use CSS selectors where possible and XPath as a fallback
- Return only Python code inside triple backticks
"""

    try:
        llm_client = get_llm()
        if llm_client is None:
            raise RuntimeError("GROQ_API_KEY environment variable is required")
        response = llm_client.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        test_code = _extract_python_code(content)
    except Exception as exc:  # pragma: no cover - defensive fallback
        test_code = _fallback_test_code(state["url"], locators)
        test_code = test_code + f"\n# Fallback due to: {exc}"

    if not test_code.strip():
        test_code = _fallback_test_code(state["url"], locators)

    return {"test_code": test_code}


workflow = StateGraph(WorkflowState)
workflow.add_node("scraper_node", scraper_node)
workflow.add_node("tester_node", tester_node)
workflow.set_entry_point("scraper_node")
workflow.add_edge("scraper_node", "tester_node")
workflow.add_edge("tester_node", END)
app = workflow.compile()


def run_workflow(sample_url: str = "https://example.com") -> str:
    initial_state: WorkflowState = {"url": sample_url, "locators": [], "test_code": ""}
    result = app.invoke(initial_state)

    output_dir = Path(__file__).resolve().parent / "tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_generated.py"
    output_path.write_text(result["test_code"], encoding="utf-8")
    return str(output_path)


if __name__ == "__main__":
    output_path = run_workflow()
    print(f"Generated test file at {output_path}")
