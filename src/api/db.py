"""
DB / checkpointer setup.
Uses PostgreSQL if available, falls back to in-memory (MemorySaver).
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from typing import Annotated, Any
from langgraph.checkpoint.memory import MemorySaver

DB_URI = os.getenv("DB_URI", "postgresql://postgres:postgres@localhost:5432/my_course_agent")

_checkpointer: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        with PostgresSaver.from_conn_string(DB_URI) as pg_checkpointer:
            pg_checkpointer.setup()
            _checkpointer = pg_checkpointer
            print("[db] PostgreSQL checkpointer OK")
            yield
    except Exception as e:
        print(f"[db] PostgreSQL not available ({e}) — using in-memory checkpointer")
        _checkpointer = MemorySaver()
        yield


def get_checkpointer() -> Any:
    if _checkpointer is None:
        return MemorySaver()
    return _checkpointer


CheckpointerDep = Annotated[Any, Depends(get_checkpointer)]
