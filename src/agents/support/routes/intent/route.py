"""
Intent router — Tier 1 (Ollama, free).
Classifies user intent and routes to the correct node.
Falls back to 'conversation' if model is unavailable or iterations exceeded.
"""
from pydantic import BaseModel, Field
from typing import Literal
from langchain_ollama import ChatOllama
from agents.support.state import State
from agents.support.routes.intent.prompt import SYSTEM_PROMPT
from agents.config import OLLAMA_BASE_URL, INTENT_MODEL, MAX_ITERATIONS


class RouteIntent(BaseModel):
    step: Literal["conversation", "booking"] = Field(
        "conversation",
        description="The next step in the routing process"
    )


# Ollama — free, local, no API cost
_llm = ChatOllama(
    model=INTENT_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    format="json",
)
llm = _llm.with_structured_output(schema=RouteIntent)


def intent_route(state: State) -> Literal["conversation", "booking"]:
    # Anti-loop: if we've iterated too many times, go straight to conversation
    iterations = state.get("iterations", 0)
    if iterations >= MAX_ITERATIONS:
        print(f"[intent_route] MAX_ITERATIONS ({MAX_ITERATIONS}) reached — forcing 'conversation'")
        return "conversation"

    try:
        history = state["messages"]
        schema = llm.invoke([("system", SYSTEM_PROMPT)] + history)
        route = schema.step if schema.step else "conversation"
        print(f"[intent_route] → {route} (iter {iterations + 1})")
        return route
    except Exception as e:
        print(f"[intent_route] Ollama error: {e} — falling back to 'conversation'")
        return "conversation"
