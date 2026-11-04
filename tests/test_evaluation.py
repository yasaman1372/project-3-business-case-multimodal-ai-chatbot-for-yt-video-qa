"""Tests for the evaluation dataset and the rule-based metrics (no API calls).
Run with: pytest tests/test_evaluation.py -v
"""

import pytest

from evaluation.langsmith_eval import load_examples
from evaluation.metrics import citations, expected_video, retrieved_context, tool_use

LINK = "https://www.youtube.com/watch?v=O6_u_SMHtgo&t=42s"
SEARCH_RESULT = {"tool": "search_video_transcripts", "content": f"[1] Picasso @ 0:42 {LINK}\nborn in Malaga in 1881"}
REFERENCE = {"reference_answer": "1881, Malaga", "category": "linked_video", "expected_video_id": "O6_u_SMHtgo",
             "expected_tools": ["add_video_by_url", "search_video_transcripts"],
             "forbidden_tools": ["find_videos_on_topic"]}
INPUTS = {"question": "When was Picasso born? https://youtu.be/O6_u_SMHtgo", "previous_questions": []}


def outputs(answer, tools=("add_video_by_url", "search_video_transcripts"), tool_outputs=(SEARCH_RESULT,)):
    return {"answer": answer, "tools_used": list(tools), "tool_outputs": list(tool_outputs), "seconds": 5.0}


def test_dataset_loads_and_is_consistent():
    examples = load_examples()
    ids = [e["metadata"]["id"] for e in examples]
    assert len(ids) == len(set(ids)) >= 10
    for e in examples:
        assert e["inputs"]["question"] and e["outputs"]["reference_answer"]
        if e["outputs"]["expected_video_id"]:
            assert len(e["outputs"]["expected_video_id"]) == 11
    follow_up = next(e for e in examples if e["metadata"]["category"] == "follow_up")
    assert follow_up["inputs"]["previous_questions"]  # memory test asks an earlier question first


def test_citations_need_a_timestamped_link():
    assert citations(INPUTS, outputs(f"In 1881 [Picasso @ 0:42]({LINK})."), REFERENCE)["score"] == 1
    assert citations(INPUTS, outputs("In 1881."), REFERENCE)["score"] == 0


def test_citations_reject_videos_never_retrieved():
    made_up = "https://www.youtube.com/watch?v=ZZZZZZZZZZZ&t=10s"
    result = citations(INPUTS, outputs(f"In 1881 [x]({made_up})."), REFERENCE)
    assert result["score"] == 0 and "ZZZZZZZZZZZ" in result["comment"]


def test_citations_do_not_apply_to_greetings():
    assert citations({"question": "hi"}, outputs("Hello!"), {**REFERENCE, "category": "conversation"})["score"] is None


def test_expected_video():
    assert expected_video(INPUTS, outputs(f"[Picasso]({LINK})"), REFERENCE)["score"] == 1
    assert expected_video(INPUTS, outputs("no link"), REFERENCE)["score"] == 0
    assert expected_video(INPUTS, outputs("x"), {**REFERENCE, "expected_video_id": ""})["score"] is None


@pytest.mark.parametrize("tools, score", [
    (["add_video_by_url", "search_video_transcripts"], 1),
    (["add_video_by_url"], 0),                                                      # missing a tool
    (["add_video_by_url", "search_video_transcripts", "find_videos_on_topic"], 0),  # forbidden tool
])
def test_tool_use(tools, score):
    assert tool_use(INPUTS, outputs("x", tools=tools), REFERENCE)["score"] == score


def test_retrieved_context_only_uses_transcript_tools():
    other = {"tool": "add_video_by_url", "content": "Added 'Picasso' to this chat."}
    context = retrieved_context(outputs("x", tool_outputs=[other, SEARCH_RESULT]))
    assert "born in Malaga" in context and "Added" not in context
