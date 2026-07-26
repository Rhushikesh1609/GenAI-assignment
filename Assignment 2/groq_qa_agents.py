import argparse
import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph


load_dotenv()


def get_api_key() -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to the .env file or environment.")
    return key


class QAAgentState(TypedDict):
    requirement: str
    analysis: str
    test_cases: str
    security_review: str
    review: str


GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
BALANCED_MODEL = os.getenv("BALANCED_MODEL", "llama-3.3-70b-versatile")
REASONING_MODEL = os.getenv("REASONING_MODEL", "openai/gpt-oss-120b")


def build_chain() -> StateGraph:
    balanced_model = ChatGroq(
        model=BALANCED_MODEL,
        temperature=0.2,
        max_tokens=1500,
       # reasoning_format="parsed",
        max_retries=2,
    )
    reasoning_model = ChatGroq(
        model=REASONING_MODEL,
        temperature=0.2,
        max_tokens=1500,
        reasoning_format="parsed",
        max_retries=2,
    )

    def call_specialist(model_client: ChatGroq, system_prompt: str, task: str) -> str:
        response = model_client.invoke([
            ("system", system_prompt),
            ("human", task),
        ])
        return response.content

    def requirements_analyst(state: QAAgentState):
        analysis = call_specialist(
            balanced_model,
            "You are a senior QA requirements analyst. Identify actors, business rules, acceptance criteria, risks, dependencies, and ambiguous requirements. Be concise and do not invent missing facts.",
            f"Analyze this requirement for testing:\n\n{state['requirement']}",
        )
        return {"analysis": analysis}

    def test_designer(state: QAAgentState):
        test_cases = call_specialist(
            balanced_model,
            "You are a senior test designer. Produce a compact Markdown table with ID, scenario, preconditions, steps, expected result, test type, and priority. Cover positive, negative, boundary, security, and failure paths.",
            f"Requirement:\n{state['requirement']}\n\nRequirements analysis:\n{state['analysis']}\n\nDesign executable test cases.",
        )
        return {"test_cases": test_cases}

    def security_reviewer(state: QAAgentState):
        security_review = call_specialist(
            reasoning_model,
            "You are a security reviewer for a product team. Review the requirement for authentication risks, token exposure, email link abuse, replay attacks, and insecure fallback flows. Highlight missing controls and propose mitigation ideas.",
            f"Requirement:\n{state['requirement']}\n\nAnalysis:\n{state['analysis']}\n\nTest cases:\n{state['test_cases']}",
        )
        return {"security_review": security_review}

    def qa_reviewer(state: QAAgentState):
        review = call_specialist(
            reasoning_model,
            "You are a critical QA lead. Review the proposed tests for requirement coverage, missing edge cases, duplication, testability, and business risk. Finish with APPROVE or REVISE and a short reason.",
            f"Requirement:\n{state['requirement']}\n\nAnalysis:\n{state['analysis']}\n\nProposed tests:\n{state['test_cases']}\n\nSecurity review:\n{state['security_review']}",
        )
        return {"review": review}

    builder = StateGraph(QAAgentState)
    builder.add_node("requirements_analyst", requirements_analyst)
    builder.add_node("test_designer", test_designer)
    builder.add_node("security_reviewer", security_reviewer)
    builder.add_node("qa_reviewer", qa_reviewer)
    builder.add_edge(START, "requirements_analyst")
    builder.add_edge("requirements_analyst", "test_designer")
    builder.add_edge("test_designer", "security_reviewer")
    builder.add_edge("security_reviewer", "qa_reviewer")
    builder.add_edge("qa_reviewer", END)
    return builder.compile()


def load_requirements(requirements_file: str | None) -> tuple[str, Path]:
    candidates = []
    if requirements_file:
        candidates.append(Path(requirements_file))
    candidates.extend([
        Path("requirements.md"),
        Path.cwd() / "requirements.md",
        Path("requirements.txt"),
        Path.cwd() / "requirements.txt",
    ])

    selected = next((path for path in candidates if path.exists()), None)
    if selected is None:
        selected = Path(requirements_file or "requirements.md")
        text = "No requirements document found. Please add a requirements file."
    else:
        text = selected.read_text(encoding="utf-8")
    return text, selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Groq-powered multi-agent QA workflow from a requirements document.")
    parser.add_argument("--requirements-file", default=None, help="Path to the requirements document")
    args = parser.parse_args()

    get_api_key()
    requirements_text, requirements_path = load_requirements(args.requirements_file)
    chain = build_chain()

    result = chain.invoke({
        "requirement": requirements_text,
        "analysis": "",
        "test_cases": "",
        "security_review": "",
        "review": "",
    })

    print(f"Loaded requirements from: {requirements_path}")
    print(f"Using balanced model: {BALANCED_MODEL}")
    print(f"Using reasoning model: {REASONING_MODEL}")

    for heading, key in [
        ("REQUIREMENTS ANALYST", "analysis"),
        ("TEST DESIGNER", "test_cases"),
        ("SECURITY REVIEWER", "security_review"),
        ("QA REVIEWER", "review"),
    ]:
        print(f"\n{'=' * 20} {heading} {'=' * 20}\n")
        print(result[key])


if __name__ == "__main__":
    main()
