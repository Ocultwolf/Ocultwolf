"""
Extractor node — Tier 2 (Claude Haiku, cheap Anthropic).
Extracts structured contact info from conversation.
Skips extraction if data already present (avoids redundant API calls).
"""
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from agents.support.state import State
from agents.support.nodes.extractor.prompt import prompt_template
from agents.config import CHEAP_MODEL


class ContactInfo(BaseModel):
    """Contact information for a person."""
    name: str = Field(description="The name of the person", default="unknown")
    email: str = Field(description="The email address of the person", default="unknown")
    phone: str = Field(description="The phone number of the person", default="unknown")
    age: str = Field(description="The age of the person", default="unknown")


llm = init_chat_model(CHEAP_MODEL, temperature=0).with_structured_output(schema=ContactInfo)


def extractor(state: State) -> State:
    new_state: State = {}

    # Increment iteration counter
    new_state["iterations"] = state.get("iterations", 0) + 1

    # Skip if already extracted
    if state.get("customer_name"):
        return new_state

    try:
        history = state["messages"]
        prompt = prompt_template.format()
        schema = llm.invoke([("system", prompt)] + history)
        new_state["customer_name"] = schema.name
        new_state["phone"] = schema.phone
        new_state["my_age"] = schema.age
        print(f"[extractor] Extracted: name={schema.name}, phone={schema.phone}")
    except Exception as e:
        print(f"[extractor] Error: {e} — skipping extraction")

    return new_state
