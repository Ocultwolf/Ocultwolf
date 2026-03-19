"""
OpenClaw Bridge — OpenAI-compatible /v1/chat/completions endpoint.
OpenClaw talks to this as if it were a normal LLM.
Internally routes through LangGraph (Ollama for simple, Claude for complex).
"""
import time
import uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agents.support.agent import make_graph
from langgraph.checkpoint.memory import MemorySaver

router = APIRouter()

# In-memory checkpointer (no PostgreSQL needed for the bridge)
_memory = MemorySaver()


# ── OpenAI-compatible schemas ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "langgraph-router"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    # OpenClaw passes user as thread_id for memory continuity
    user: Optional[str] = "default"


def _to_lc_messages(messages: list[ChatMessage]):
    """Convert OpenAI message format → LangChain messages."""
    result = []
    for m in messages:
        if m.role == "user":
            result.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            result.append(AIMessage(content=m.content))
        elif m.role == "system":
            result.append(SystemMessage(content=m.content))
    return result


def _make_openai_response(content: str, model: str = "langgraph-router") -> dict:
    """Wrap response in OpenAI-compatible format."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": "langgraph-router", "object": "model", "owned_by": "local"}]
    }


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    thread_id = req.user or "default"
    lc_messages = _to_lc_messages(req.messages)

    # Only pass the last user message as new input; history is in checkpointer
    last_user = next(
        (m for m in reversed(lc_messages) if isinstance(m, HumanMessage)), None
    )
    if not last_user:
        return _make_openai_response("No user message found.")

    config = {"configurable": {"thread_id": thread_id}}
    agent = make_graph(config={"checkpointer": _memory})

    if req.stream:
        async def event_stream():
            import json
            for chunk, _ in agent.stream(
                {"messages": [last_user]}, config, stream_mode="messages"
            ):
                if hasattr(chunk, "content") and chunk.content:
                    data = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": req.model,
                        "choices": [{
                            "delta": {"role": "assistant", "content": chunk.content},
                            "index": 0,
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    try:
        response = agent.invoke({"messages": [last_user]}, config)
        last = response["messages"][-1]
        content = last.content if hasattr(last, "content") else str(last)
    except Exception as e:
        content = f"[Router error: {e}]"

    return _make_openai_response(content, req.model)
