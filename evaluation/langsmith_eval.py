"""Evaluate the YouTube QA agent on evaluation/eval_questions.csv.

Each question runs in a fresh chat (questions in `previous_questions` are asked
first, to test memory), then the answer is scored with evaluation/metrics.py.
The chat's videos are deleted afterwards. Linked videos come from the shared
video cache, so they cost no transcript credits; topic questions may download new ones.

Usage:
    python -m evaluation.langsmith_eval                    # LangSmith experiment (needs LANGSMITH_API_KEY)
    python -m evaluation.langsmith_eval --local            # run here only, save evaluation/results/<time>.csv
    python -m evaluation.langsmith_eval --only link-picasso-born chat-greeting
    python -m evaluation.langsmith_eval --no-judge         # skip the LLM-judge metrics (cheaper)

In LangSmith the CSV becomes the dataset "yt-video-qa-eval" (updated when the CSV
changes) and every run becomes an experiment you can compare with earlier ones.
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

from app.agent import chat_with_details
from app.config import CHAT_MODEL, EVAL_DATASET_NAME, EVAL_JUDGE_MODEL, RETRIEVAL_K
from evaluation.metrics import ALL_EVALUATORS, RULE_EVALUATORS
from ingestion.vector_store import chat_namespace, delete_namespace, new_thread_id

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "eval_questions.csv"
RESULTS_DIR = EVAL_DIR / "results"
METRICS = ["correctness", "groundedness", "citations", "expected_video", "tool_use", "latency_seconds"]


def _split(value: str, separator: str = ";") -> list[str]:
    return [part.strip() for part in value.split(separator) if part.strip()]


def load_examples(path: Path = QUESTIONS_FILE) -> list[dict]:
    """Read the CSV into LangSmith-style examples: {"inputs", "outputs", "metadata"}."""
    with path.open(newline="") as f:
        return [{
            "inputs": {"question": row["question"],
                       "previous_questions": _split(row["previous_questions"], "||")},
            "outputs": {"reference_answer": row["reference_answer"],
                        "category": row["category"],
                        "expected_video_id": row["expected_video_id"],
                        "expected_tools": _split(row["expected_tools"]),
                        "forbidden_tools": _split(row["forbidden_tools"])},
            "metadata": {"id": row["id"], "category": row["category"]},
        } for row in csv.DictReader(f)]


def run_agent(inputs: dict) -> dict:
    """The system under test: answer one question in a fresh chat, then delete the chat's videos."""
    thread_id = new_thread_id()
    try:
        for question in inputs.get("previous_questions", []):
            chat_with_details(question, thread_id)
        start = time.perf_counter()
        result = chat_with_details(inputs["question"], thread_id)
        return {**result, "seconds": round(time.perf_counter() - start, 2)}
    finally:
        delete_namespace(chat_namespace(thread_id))


# ---------- Local run ----------

def run_locally(examples: list[dict], evaluators: list) -> list[dict]:
    rows = []
    for n, example in enumerate(examples, 1):
        example_id = example["metadata"]["id"]
        print(f"[{n}/{len(examples)}] {example_id} ...", flush=True)
        outputs = run_agent(example["inputs"])
        row = {"id": example_id, "category": example["metadata"]["category"],
               "question": example["inputs"]["question"], "answer": outputs["answer"],
               "tools_used": ";".join(outputs["tools_used"])}
        for evaluator in evaluators:
            result = evaluator(example["inputs"], outputs, example["outputs"])
            row[result["key"]] = result["score"]
            if result.get("comment") and result["score"] == 0:
                row.setdefault("problems", []).append(f"{result['key']}: {result['comment']}")
        row["problems"] = " | ".join(row.get("problems", []))
        rows.append(row)
    return rows


def save_rows(rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"eval_{datetime.now():%Y%m%d_%H%M%S}.csv"
    columns = ["id", "category", *[m for m in METRICS if any(m in r for r in rows)],
               "tools_used", "problems", "question", "answer"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------- LangSmith run ----------

def sync_dataset(client, examples: list[dict]):
    """Create the LangSmith dataset, or replace its examples if the CSV changed."""
    def key(e):
        return (e["metadata"]["id"], repr(e["inputs"]), repr(e["outputs"]))

    if client.has_dataset(dataset_name=EVAL_DATASET_NAME):
        dataset = client.read_dataset(dataset_name=EVAL_DATASET_NAME)
        existing = list(client.list_examples(dataset_id=dataset.id))
        current = [{"inputs": e.inputs, "outputs": e.outputs, "metadata": e.metadata} for e in existing]
        if sorted(map(key, current)) == sorted(map(key, examples)):
            return dataset
        client.delete_examples([e.id for e in existing])
        print(f"Updating LangSmith dataset '{EVAL_DATASET_NAME}' from {QUESTIONS_FILE.name}")
    else:
        dataset = client.create_dataset(EVAL_DATASET_NAME,
                                        description="Questions about YouTube videos with reference answers")
        print(f"Created LangSmith dataset '{EVAL_DATASET_NAME}'")
    client.create_examples(dataset_id=dataset.id, examples=examples)
    return dataset


def run_in_langsmith(examples: list[dict], evaluators: list, only: set[str]) -> list[dict]:
    from langsmith import Client, evaluate

    client = Client()
    dataset = sync_dataset(client, examples)
    data = [e for e in client.list_examples(dataset_id=dataset.id) if not only or e.metadata.get("id") in only]
    results = evaluate(
        run_agent,
        data=data,
        evaluators=evaluators,
        experiment_prefix=f"agent-{CHAT_MODEL}",
        metadata={"chat_model": CHAT_MODEL, "judge_model": EVAL_JUDGE_MODEL, "retrieval_k": RETRIEVAL_K},
        max_concurrency=1,  # Supadata free plan: 1 request/second
    )

    rows = []
    for result in results:
        example, outputs = result["example"], result["run"].outputs or {}
        row = {"id": example.metadata.get("id"), "category": example.metadata.get("category"),
               "question": example.inputs["question"], "answer": outputs.get("answer", "(error)"),
               "tools_used": ";".join(outputs.get("tools_used", []))}
        row.update({r.key: r.score for r in result["evaluation_results"]["results"]})
        rows.append(row)
    print(f"\nLangSmith experiment: {results.experiment_name}")
    return rows


# ---------- Summary ----------

def print_summary(rows: list[dict]) -> None:
    print(f"\n{'id':<28} " + " ".join(f"{m[:12]:>12}" for m in METRICS))
    for row in rows:
        cells = [row.get(m) for m in METRICS]
        print(f"{row['id']:<28} " + " ".join(f"{'-' if c is None else c:>12}" for c in cells))

    print("\nAverages (examples where the metric applies):")
    for metric in METRICS:
        scores = [r[metric] for r in rows if r.get(metric) is not None]
        if scores:
            average = sum(scores) / len(scores)
            shown = f"{average:.1f}s" if metric == "latency_seconds" else f"{average:.0%}"
            print(f"  {metric:<16} {shown:>6}   (n={len(scores)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the YouTube QA agent.")
    parser.add_argument("--local", action="store_true", help="Run without LangSmith and save a CSV")
    parser.add_argument("--only", nargs="+", default=[], metavar="ID", help="Only these question ids")
    parser.add_argument("--no-judge", action="store_true", help="Skip correctness/groundedness (no judge LLM calls)")
    args = parser.parse_args()

    examples = load_examples()
    only = set(args.only)
    unknown = only - {e["metadata"]["id"] for e in examples}
    if unknown:
        parser.error(f"unknown question ids: {sorted(unknown)}")
    evaluators = RULE_EVALUATORS if args.no_judge else ALL_EVALUATORS

    if args.local:
        rows = run_locally([e for e in examples if not only or e["metadata"]["id"] in only], evaluators)
        print_summary(rows)
        print(f"\nSaved {save_rows(rows).relative_to(EVAL_DIR.parent)}")
    else:
        print_summary(run_in_langsmith(examples, evaluators, only))


if __name__ == "__main__":
    main()
