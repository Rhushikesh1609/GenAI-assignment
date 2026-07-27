from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
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
                const selectors = [
                    'button',
                    'input:not([type="hidden"])',
                    'select',
                    'textarea',
                    'a[href]',
                    '[role="button"]',
                    '[role="link"]',
                    '[onclick]',
                    '[data-testid]',
                    '[data-test-id]',
                    '[aria-label]',
                    '[placeholder]'
                ];
                const elements = Array.from(document.querySelectorAll(selectors.join(',')));
                const results = [];
                const seen = new Set();

                const getText = (el) => {
                    return (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '').toString().trim();
                };

                const toCssSelector = (el) => {
                    const tag = el.tagName.toLowerCase();
                    const dataTest = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
                    const href = el.getAttribute('href');
                    const ariaLabel = el.getAttribute('aria-label');
                    const placeholder = el.getAttribute('placeholder');
                    if (dataTest) {
                        return `${tag}[data-testid="${dataTest}"]`;
                    }
                    if (el.id) {
                        return `${tag}#${el.id.replace(/\\s+/g, '_')}`;
                    }
                    if (el.getAttribute('name')) {
                        return `${tag}[name="${el.getAttribute('name')}"]`;
                    }
                    if (href) {
                        return `${tag}[href="${href}"]`;
                    }
                    if (ariaLabel) {
                        return `${tag}[aria-label="${ariaLabel}"]`;
                    }
                    if (placeholder) {
                        return `${tag}[placeholder="${placeholder}"]`;
                    }
                    if (el.getAttribute('role')) {
                        return `${tag}[role="${el.getAttribute('role')}"]`;
                    }
                    if (el.getAttribute('type')) {
                        return `${tag}[type="${el.getAttribute('type')}"]`;
                    }
                    const classes = Array.from(el.classList || []).filter(Boolean).slice(0, 2);
                    if (classes.length) {
                        return `${tag}.${classes.join('.')}`;
                    }
                    return tag;
                };

                const toXPath = (el) => {
                    const tag = el.tagName.toLowerCase();
                    let xpath = `//${tag}`;
                    if (el.id) {
                        xpath += `[@id='${el.id}']`;
                    } else if (el.getAttribute('data-testid') || el.getAttribute('data-test-id')) {
                        const testId = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
                        xpath += `[@data-testid='${testId}']`;
                    } else if (el.getAttribute('name')) {
                        xpath += `[@name='${el.getAttribute('name')}']`;
                    } else if (el.getAttribute('href')) {
                        xpath += `[@href='${el.getAttribute('href')}']`;
                    } else if (el.getAttribute('aria-label')) {
                        xpath += `[@aria-label='${el.getAttribute('aria-label')}']`;
                    } else if (el.getAttribute('role')) {
                        xpath += `[@role='${el.getAttribute('role')}']`;
                    } else if (el.getAttribute('type')) {
                        xpath += `[@type='${el.getAttribute('type')}']`;
                    }
                    return xpath;
                };

                for (const element of elements) {
                    const text = getText(element);
                    const css = toCssSelector(element);
                    const xpath = toXPath(element);
                    const key = `${css}:${xpath}`;
                    if (seen.has(key)) {
                        continue;
                    }
                    seen.add(key);
                    results.push({
                        'tag': element.tagName.toLowerCase(),
                        'text': text.slice(0, 120),
                        'css': css,
                        'xpath': xpath,
                        'role': element.getAttribute('role') || '',
                        'type': element.getAttribute('type') || '',
                        'name': element.getAttribute('name') || '',
                        'placeholder': element.getAttribute('placeholder') || '',
                    });
                    if (results.length >= 30) {
                        break;
                    }
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
        "import pytest",
        "from playwright.sync_api import sync_playwright, expect",
        "",
        f"TARGET_URL = '{url}'",
        "LOCATORS = [",
    ]

    for locator in locators:
        locator_json = json.dumps(locator, indent=4)
        lines.extend(["    " + line for line in locator_json.splitlines()])
        lines.append(",")

    lines.extend([
        "]",
        "",
    ])

    lines.extend([
        "def test_page_elements_visible():",
        "    with sync_playwright() as playwright:",
        "        browser = playwright.chromium.launch(headless=True)",
        "        page = browser.new_page()",
        "        page.goto(TARGET_URL, wait_until='domcontentloaded')",
        "        for locator in LOCATORS:",
        "            selector = locator.get('css') or locator.get('xpath') or locator.get('tag') or 'body'",
        "            expect(page.locator(selector).first).to_be_visible()",
        "        browser.close()",
        "",
    ])

    return "\n".join(lines).rstrip() + "\n"


def tester_node(state: WorkflowState) -> dict:
    locators = state["locators"]
    prompt = f"""
You are a QA engineer. Create a complete, valid pytest test file using playwright.sync_api.
The target URL is: {state['url']}
The interactive element locators are provided as JSON:
{json.dumps(locators, indent=2)}

Requirements:
- Use sync_playwright()
- Open the page once, navigate to the URL once, and then validate every locator in a loop
- Define a single pytest test function named test_page_elements_visible()
- For each locator, add an assertion: expect(page.locator(...).first).to_be_visible()
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


def _format_report_table(report: dict) -> str:
    headers = ["Test Case", "Status", "Selector", "Details"]
    rows = []
    for test in report["tests"]:
        rows.append([test["name"], test["status"], test.get("selector", ""), test.get("message", "") or "visible check"])

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(str(value)))

    def format_row(values: list[str]) -> str:
        return " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(values))

    divider = "-+-".join("-" * width for width in widths)
    lines = [format_row(headers), divider]
    for row in rows:
        lines.append(format_row(row))
    return "\n".join(lines)


def _write_tabular_xml(report: dict, output_path: Path) -> None:
    root = ET.Element("test_report")
    summary = ET.SubElement(root, "summary")
    summary.set("passed", str(report["summary"]["passed"]))
    summary.set("failed", str(report["summary"]["failed"]))
    summary.set("skipped", str(report["summary"]["skipped"]))
    summary.set("url", str(report.get("url", "")))
    summary.set("locator_count", str(report.get("locator_count", 0)))

    tests_element = ET.SubElement(root, "tests")
    for test in report["tests"]:
        testcase = ET.SubElement(tests_element, "testcase")
        testcase.set("name", test["name"])
        testcase.set("status", test["status"])
        testcase.set("selector", test.get("selector", ""))
        testcase.set("details", test.get("message", "") or "visible check")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _check_locators(url: str, locators: list[dict]) -> list[dict]:
    tests = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")

        for index, locator in enumerate(locators):
            selector = locator.get("css") or locator.get("xpath") or locator.get("tag") or "body"
            try:
                locator_obj = page.locator(selector)
                visible = locator_obj.count() > 0 and locator_obj.first.is_visible()
                status = "passed" if visible else "failed"
                message = "visible" if visible else f"selector '{selector}' was not visible"
            except Exception as exc:
                status = "failed"
                message = str(exc)

            tests.append(
                {
                    "name": f"locator_{index}",
                    "status": status,
                    "selector": selector,
                    "message": message,
                    "description": locator.get("text", "") or locator.get("role", "") or locator.get("type", "") or "interactive element",
                }
            )

        browser.close()

    return tests


def _build_structured_report(output_path: Path, url: str, locators: list[dict]) -> dict:
    tests = _check_locators(url, locators)
    summary = {"passed": sum(1 for case in tests if case["status"] == "passed"), "failed": sum(1 for case in tests if case["status"] == "failed"), "skipped": 0}
    return {
        "generated_test_file": str(output_path),
        "summary": summary,
        "tests": tests,
        "url": url,
        "locator_count": len(locators),
    }


def run_workflow(sample_url: str = "https://demoblaze.com") -> dict:
    initial_state: WorkflowState = {"url": sample_url, "locators": [], "test_code": ""}
    result = app.invoke(initial_state)

    output_dir = Path(__file__).resolve().parent / "tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_generated.py"
    output_path.write_text(result["test_code"], encoding="utf-8")

    report = _build_structured_report(output_path, sample_url, result.get("locators", []))
    _write_tabular_xml(report, output_dir / "results.xml")
    print("Structured test report")
    print(_format_report_table(report))
    print("\nJSON summary")
    print(json.dumps({key: report[key] for key in ["url", "locator_count", "summary"]}, indent=2))
    return report


if __name__ == "__main__":
    run_workflow()
