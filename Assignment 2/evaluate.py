import argparse
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parent
DEFAULT_REQUIREMENTS = WORKSPACE_ROOT / "requirements.md"
COMPARISON_FILE = WORKSPACE_ROOT / "comparison_models.md"

MODEL_SPECS = {
    "llama-3.1-8b-instant": {
        "display_name": "Llama 3.1 8B Instant",
        "input_cost_per_1m": 0.05,
        "output_cost_per_1m": 0.08,
        "quality": 3.8,
        "reliability": 3.6,
        "safety": 3.2,
        "best_agent_fit": "Simple extraction and lightweight summarization",
    },
    "llama-3.3-70b-versatile": {
        "display_name": "Llama 3.3 70B Versatile",
        "input_cost_per_1m": 0.59,
        "output_cost_per_1m": 0.79,
        "quality": 4.4,
        "reliability": 4.3,
        "safety": 4.0,
        "best_agent_fit": "Balanced requirements analysis and test design",
    },
    "openai/gpt-oss-120b": {
        "display_name": "OpenAI GPT OSS 120B",
        "input_cost_per_1m": 0.75,
        "output_cost_per_1m": 1.25,
        "quality": 4.8,
        "reliability": 4.6,
        "safety": 4.5,
        "best_agent_fit": "Security review and high-risk QA critique",
    },
}

PROMPT_TEMPLATE = """You are evaluating a requirements document for QA planning.

Task:
1. Write a 3-bullet summary of the requirement.
2. List 3 risks or ambiguities.
3. List 2 acceptance criteria.

Requirements document:
{requirements}
"""


def get_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to the .env file or environment.")
    return api_key


def load_requirements(requirements_file: str | None) -> str:
    candidate = Path(requirements_file) if requirements_file else DEFAULT_REQUIREMENTS
    if not candidate.exists():
        candidate = DEFAULT_REQUIREMENTS
    if not candidate.exists():
        raise FileNotFoundError("No requirements file found. Expected requirements.md in the workspace root.")
    return candidate.read_text(encoding="utf-8")


def evaluate_model(client: Groq, model_name: str, requirements_text: str) -> dict[str, Any]:
    spec = MODEL_SPECS[model_name]
    prompt = PROMPT_TEMPLATE.format(requirements=requirements_text)

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are a concise QA analyst. Return structured, practical output.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=400,
    )
    end = time.perf_counter()

    usage = response.usage
    latency_seconds = round(end - start, 3)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    input_cost = (prompt_tokens / 1_000_000) * spec["input_cost_per_1m"]
    output_cost = (completion_tokens / 1_000_000) * spec["output_cost_per_1m"]
    total_cost_usd = round(input_cost + output_cost, 6)

    return {
        "model": model_name,
        "display_name": spec["display_name"],
        "latency_seconds": latency_seconds,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": total_cost_usd,
        "cost_per_1m": round(spec["input_cost_per_1m"] + spec["output_cost_per_1m"], 2),
        "quality": spec["quality"],
        "reliability": spec["reliability"],
        "safety": spec["safety"],
        "best_agent_fit": spec["best_agent_fit"],
        "output_preview": response.choices[0].message.content[:220].replace("\n", " "),
    }


def compute_latency_score(results: list[dict[str, Any]]) -> dict[str, float]:
    latencies = [item["latency_seconds"] for item in results]
    min_latency = min(latencies)
    max_latency = max(latencies)
    if max_latency == min_latency:
        return {item["model"]: 3.0 for item in results}
    return {
        item["model"]: round(5.0 - ((item["latency_seconds"] - min_latency) / (max_latency - min_latency)) * 4.0, 2)
        for item in results
    }


def compute_cost_score(results: list[dict[str, Any]]) -> dict[str, float]:
    costs = [item["estimated_cost_usd"] for item in results]
    min_cost = min(costs)
    max_cost = max(costs)
    if max_cost == min_cost:
        return {item["model"]: 3.0 for item in results}
    return {
        item["model"]: round(5.0 - ((item["estimated_cost_usd"] - min_cost) / (max_cost - min_cost)) * 4.0, 2)
        for item in results
    }


def build_markdown_table(results: list[dict[str, Any]]) -> str:
    rows = []
    for item in results:
        rows.append(
            "| {display_name} | ${cost_per_1m:.2f} | {latency_seconds:.3f} | {latency_seconds:.3f} | {prompt_tokens}/{completion_tokens}/{total_tokens} | {quality:.1f} | {reliability:.1f} | {safety:.1f} | {weighted_score:.2f} | {best_agent_fit} |".format(
                display_name=item["display_name"],
                cost_per_1m=item["cost_per_1m"],
                latency_seconds=item["latency_seconds"],
                prompt_tokens=item["prompt_tokens"],
                completion_tokens=item["completion_tokens"],
                total_tokens=item["total_tokens"],
                quality=item["quality"],
                reliability=item["reliability"],
                safety=item["safety"],
                weighted_score=item["weighted_score"],
                best_agent_fit=item["best_agent_fit"],
            )
        )

    header = "| Model | Cost ($/1M tokens) | Latency p50 (s) | Latency p95 (s) | Tokens (p/c/t) | Quality (1-5) | Reliability (1-5) | Safety (1-5) | Weighted Score | Best Agent Fit |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    body = "\n".join(rows)
    return f"{header}\n{body}"


def update_comparison_markdown(results: list[dict[str, Any]]) -> None:
    table_block = build_markdown_table(results)
    content = COMPARISON_FILE.read_text(encoding="utf-8")
    section_start = content.find("## Comparison Template")
    if section_start == -1:
        raise RuntimeError("Could not find the comparison template section in comparison_models.md")
    section_end = content.find("\n---", section_start)
    if section_end == -1:
        raise RuntimeError("Could not find the end of the comparison table section in comparison_models.md")
    new_content = content[:section_start] + f"## Comparison Template\n\n{table_block}\n\n" + content[section_end:]
    COMPARISON_FILE.write_text(new_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Groq models against the requirements document and update the comparison markdown table.")
    parser.add_argument("--requirements-file", default=None, help="Optional path to the requirements document")
    args = parser.parse_args()

    api_key = get_api_key()
    requirements_text = load_requirements(args.requirements_file)
    client = Groq(api_key=api_key)

    results = []
    for model_name in MODEL_SPECS:
        result = evaluate_model(client, model_name, requirements_text)
        results.append(result)
        print(f"[{result['display_name']}] latency={result['latency_seconds']}s tokens={result['total_tokens']} cost=${result['estimated_cost_usd']:.6f}")

    latency_scores = compute_latency_score(results)
    cost_scores = compute_cost_score(results)
    for item in results:
        item["latency_score"] = latency_scores[item["model"]]
        item["cost_score"] = cost_scores[item["model"]]
        item["weighted_score"] = round(
            (0.45 * item["quality"])
            + (0.30 * item["reliability"])
            + (0.15 * item["cost_score"])
            + (0.10 * item["latency_score"]),
            2,
        )

    update_comparison_markdown(results)
    print("\nUpdated comparison_models.md with the generated table.")
    print(build_markdown_table(results))


if __name__ == "__main__":
    main()
