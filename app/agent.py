"""The YouTube QA agent: LLM + tools + memory.

Usage (interactive chat in the terminal):
    python -m app.agent

From code (e.g. the FastAPI endpoint):
    from app.agent import ask
    answer = ask("What is inside a black hole?", thread_id="user-123")
"""

import uuid
from functools import lru_cache

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import CHAT_MODEL, OPENAI_API_KEY, REASONING_EFFORT
from app.memory import get_checkpointer
from app.prompts import SYSTEM_PROMPT
from app.tools import TOOLS


@lru_cache(maxsize=1)
def get_agent():
    """Build the agent once and reuse it."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    # Responses API: required for tool calling + reasoning_effort on gpt-5.x models
    model = ChatOpenAI(model=CHAT_MODEL, reasoning_effort=REASONING_EFFORT, use_responses_api=True)
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=get_checkpointer(),
        name="youtube_qa_agent",
    )


def ask(question: str, thread_id: str) -> str:
    """Send a question in a conversation and return the agent's answer.

    Messages with the same thread_id share memory (one thread = one conversation).
    """
    result = get_agent().invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text


def main() -> None:
    thread_id = str(uuid.uuid4())
    print("YouTube QA agent. Ask about the indexed videos ('quit' to exit).\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit", "q"}:
            break
        if question:
            print(f"\nBot: {ask(question, thread_id)}\n")


if __name__ == "__main__":
    main()
