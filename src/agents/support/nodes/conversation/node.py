"""
Conversation node — Tier 1 (Ollama, free) con fallback a Tier 3 (Claude Sonnet).
"""
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage

from agents.support.state import State
from agents.support.nodes.conversation.tools import tools
from agents.support.nodes.conversation.prompt import prompt_template
from agents.config import OLLAMA_BASE_URL, SIMPLE_MODEL, SMART_MODEL


# Tier 1: Ollama
_ollama = ChatOllama(
    model=SIMPLE_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.7,
)
llm_local = _ollama.bind_tools(tools)

# Tier 3: Claude Sonnet (fallback para tool calls complejos)
from langchain.chat_models import init_chat_model
llm_smart = init_chat_model(SMART_MODEL, temperature=0.7).bind_tools(tools)


def conversation(state: State) -> State:
    new_state: State = {}
    history = state["messages"]
    last_message = history[-1]
    customer_name = state.get("customer_name", "there")
    prompt = prompt_template.format(name=customer_name)

    try:
        ai_message = llm_local.invoke([("system", prompt), ("user", last_message.content)])
        print("[conversation] Ollama OK")
    except Exception as e:
        print(f"[conversation] Ollama failed ({e}), falling back to Claude")
        ai_message = llm_smart.invoke([("system", prompt), ("user", last_message.content)])

    new_state["messages"] = [AIMessage(content=ai_message.content)]
    return new_state
