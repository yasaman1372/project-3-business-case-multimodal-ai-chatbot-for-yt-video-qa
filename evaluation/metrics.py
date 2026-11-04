"""Evaluation metrics for the YouTube QA agent.

Each metric is a LangSmith-style evaluator: it gets the example's `inputs`, the
agent's `outputs` and the expected `reference_outputs`, and returns
{"key", "score", "comment"}. A score of None means "doesn't apply to this example".

    correctness    LLM judge: does the answer match the reference answer?        (0/1)
    groundedness   LLM judge: is every claim supported by the retrieved passages? (0/1)
    citations      answer links video moments, and only videos it actually read  (0/1)
    expected_video answer cites the video the question is about                   (0/1)
    tool_use       expected tools called, forbidden ones not                      (0/1)
    latency        seconds to answer                                              (number)

outputs:            {"answer", "tools_used": [...], "tool_outputs": [{"tool", "content"}], "seconds"}
reference_outputs:  {"reference_answer", "category", "expected_video_id",
                     "expected_tools": [...], "forbidden_tools": [...]}
"""

import re
from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import EVAL_JUDGE_MODEL

VIDEO_LINK = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})")
VIDEO_ID_MENTION = re.compile(r"video_id: ([\w-]{11})")  # how tools name videos
TIMESTAMP_LINK = re.compile(r"youtube\.com/watch\?v=[\w-]{11}[^)\s]*[?&]t=\d+")
CONTEXT_TOOLS = {"search_video_transcripts", "get_video_transcript"}  # tools that return transcript text
CITATION_CATEGORIES = {"linked_video", "topic", "follow_up"}  # answers that must cite video moments
MAX_CONTEXT_CHARS = 40_000  # keep the judge prompt a reasonable size


# ---------- LLM judge ----------

class Verdict(BaseModel):
    reasoning: str = Field(description="One or two sentences explaining the decision")
    passed: bool = Field(description="True if the answer meets the criterion")


@lru_cache(maxsize=1)
def get_judge():
    model = ChatOpenAI(model=EVAL_JUDGE_MODEL, reasoning_effort="low", use_responses_api=True)
    return model.with_structured_output(Verdict)


CORRECTNESS_PROMPT = """You are grading a chatbot that answers questions from YouTube video transcripts.

Question: {question}

Reference answer (what a correct answer must convey): {reference}

Chatbot answer: {answer}

Is the chatbot answer correct? It passes if it conveys the key facts of the reference answer \
and contradicts none of them. Extra correct detail, different wording and citation links are \
fine; it does not need every minor detail. If the reference says the information is not \
covered, the answer passes only if it says so instead of inventing an answer."""

GROUNDEDNESS_PROMPT = """You are checking a chatbot for hallucinations. It must answer only from \
the transcript passages its tools retrieved.

Retrieved passages:
{context}

Chatbot answer: {answer}

Is every factual claim in the answer supported by the passages? Ignore citation links, \
greetings and statements that something isn't covered. Obvious corrections of misheard \
words in auto-generated transcripts (e.g. a misspelled name) count as supported. Fail it \
if it states facts that are not in the passages."""


def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    verdict = get_judge().invoke(CORRECTNESS_PROMPT.format(
        question=inputs["question"], reference=reference_outputs["reference_answer"], answer=outputs["answer"]))
    return {"key": "correctness", "score": int(verdict.passed), "comment": verdict.reasoning}


def groundedness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    context = retrieved_context(outputs)
    if not context:
        return {"key": "groundedness", "score": None, "comment": "No passages were retrieved."}
    verdict = get_judge().invoke(GROUNDEDNESS_PROMPT.format(context=context, answer=outputs["answer"]))
    return {"key": "groundedness", "score": int(verdict.passed), "comment": verdict.reasoning}


# ---------- Rule-based metrics ----------

def retrieved_context(outputs: dict) -> str:
    """The transcript text the agent's tools returned for this question."""
    texts = [o["content"] for o in outputs.get("tool_outputs", []) if o["tool"] in CONTEXT_TOOLS]
    return "\n\n---\n\n".join(texts)[:MAX_CONTEXT_CHARS]


def cited_video_ids(answer: str) -> set[str]:
    return set(VIDEO_LINK.findall(answer))


def citations(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs["category"] not in CITATION_CATEGORIES:
        return {"key": "citations", "score": None, "comment": "No citations expected for this kind of question."}
    answer = outputs["answer"]
    if not TIMESTAMP_LINK.search(answer):
        return {"key": "citations", "score": 0, "comment": "No timestamped video link in the answer."}
    # Every cited video must come from the question or the tool results, not be made up
    seen_text = " ".join([inputs["question"], *(o["content"] for o in outputs.get("tool_outputs", []))])
    seen = set(VIDEO_LINK.findall(seen_text)) | set(VIDEO_ID_MENTION.findall(seen_text))
    invented = cited_video_ids(answer) - seen
    if invented:
        return {"key": "citations", "score": 0, "comment": f"Cites videos it never retrieved: {sorted(invented)}"}
    return {"key": "citations", "score": 1, "comment": f"Cites {sorted(cited_video_ids(answer))}"}


def expected_video(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    video_id = reference_outputs.get("expected_video_id")
    if not video_id:
        return {"key": "expected_video", "score": None, "comment": "No specific video expected."}
    found = video_id in cited_video_ids(outputs["answer"])
    return {"key": "expected_video", "score": int(found),
            "comment": f"{'Cites' if found else 'Does not cite'} {video_id}"}


def tool_use(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    used = outputs.get("tools_used", [])
    missing = [t for t in reference_outputs.get("expected_tools", []) if t not in used]
    forbidden = [t for t in reference_outputs.get("forbidden_tools", []) if t in used]
    problems = ([f"missing {missing}"] if missing else []) + ([f"should not call {forbidden}"] if forbidden else [])
    return {"key": "tool_use", "score": int(not problems),
            "comment": "; ".join(problems) or f"Called {used or 'no tools'}"}


def latency(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "latency_seconds", "score": outputs.get("seconds")}


RULE_EVALUATORS = [citations, expected_video, tool_use, latency]
JUDGE_EVALUATORS = [correctness, groundedness]
ALL_EVALUATORS = JUDGE_EVALUATORS + RULE_EVALUATORS
