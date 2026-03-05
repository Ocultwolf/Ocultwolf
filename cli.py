"""MongoAI CLI

Herramienta de línea de comandos para interactuar con los agentes LangGraph
(chats) y consultar los vectorstores de documentación.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Dict

import typer
from rich.console import Console
from rich.table import Table
from langchain.chat_models import init_chat_model  # noqa: F401 (para futuras extensiones)
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from agents.simple import agent as simple_agent
from agents.rag import agent as rag_agent
from agents.evaluator import agent as evaluator_agent
from agents.code_review import agent as code_review_agent
from agents.orchestrator import agent as orchestrator_agent
from agents.vector_agent import agent as vector_agent
from agents.trading import agent as trading_agent

console = Console()
app = typer.Typer(no_args_is_help=True, add_completion=False)
agents_app = typer.Typer(help="Operaciones relacionadas con los agentes")
docs_app = typer.Typer(help="Consultas a los vectorstores de documentación")
app.add_typer(agents_app, name="agents")
app.add_typer(docs_app, name="docs")

AGENTS: Dict[str, object] = {
    "simple": simple_agent,
    "rag": rag_agent,
    "evaluator": evaluator_agent,
    "code_review": code_review_agent,
    "orchestrator": orchestrator_agent,
    "vector_agent": vector_agent,
    "trading": trading_agent,
}

VECTORSTORE_SOURCES = {
    "langchain": {
        "friendly": "LangChain/LangGraph docs",
        "candidates": [
            Path("data/vectorstores/langchain"),
            Path("/root/.openclaw/workspace/MongoIA/clon/platzilang/curso-agentes-langgraph/src/agents/support/vectorstore_langchain_langgraph"),
        ],
    },
    "openclaw": {
        "friendly": "OpenClaw docs",
        "candidates": [
            Path("data/vectorstores/openclaw"),
            Path("/root/.openclaw/workspace/MongoIA/clon/platzilang/curso-agentes-langgraph/src/agents/vectorstore_openclaw"),
        ],
    },
}

_embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
_vector_cache: Dict[str, FAISS] = {}


def _load_vectorstore(source: str) -> FAISS:
    if source in _vector_cache:
        return _vector_cache[source]

    config = VECTORSTORE_SOURCES.get(source)
    if not config:
        raise typer.BadParameter(f"Fuente desconocida: {source}")

    for candidate in config["candidates"]:
        if candidate.exists():
            vs = FAISS.load_local(
                str(candidate),
                _embeddings,
                allow_dangerous_deserialization=True,
            )
            _vector_cache[source] = vs
            return vs

    raise RuntimeError(
        f"No encontré el vectorstore '{source}'. Copia los datos a {config['candidates'][0]} o actualiza las rutas."
    )


@agents_app.command("list")
def list_agents() -> None:
    """Mostrar los agentes disponibles."""
    table = Table(title="Agentes disponibles")
    table.add_column("Clave", style="cyan", no_wrap=True)
    table.add_column("Descripción")
    descriptions = {
        "simple": "Agente base con memoria corta",
        "rag": "Agente RAG general",
        "evaluator": "Generador + evaluador",
        "code_review": "Revisor/refactor con LangGraph",
        "orchestrator": "Orquestador multi-node",
        "vector_agent": "Consulta vectorstores",
        "trading": "Investiga y backtestea estrategias cripto"
    }
    for key in AGENTS:
        table.add_row(key, descriptions.get(key, "-"))
    console.print(table)


@agents_app.command("chat")
def chat(
    agent: str = typer.Argument(..., help="Clave del agente"),
    vector_model: str = typer.Option(None, help="Para vector_agent: 'large' o 'small'"),
) -> None:
    """Abrir un chat interactivo con el agente elegido."""
    if agent not in AGENTS:
        raise typer.BadParameter(f"Agente desconocido: {agent}")

    selected_agent = AGENTS[agent]
    console.print(f"[bold green]Usando agente:[/] {agent}\n")
    console.print("Escribe 'exit' para salir o 'change' para elegir otro agente.\n")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = {"messages": []}

    if agent == "vector_agent":
        model_choice = vector_model or typer.prompt("vector_model ('large'/'small')", default="large")
        if model_choice not in {"large", "small"}:
            raise typer.BadParameter("vector_model debe ser 'large' o 'small'")
        state["vector_model"] = model_choice

    while True:
        try:
            user_input = input("Tú: ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nAdiós! 👋")
            raise typer.Exit()

        cmd = user_input.strip().lower()
        if cmd == "exit":
            raise typer.Exit()
        if cmd == "change":
            console.print("Cambiar de agente: vuelve a ejecutar 'mongoai agents chat ...'")
            raise typer.Exit()

        state["messages"].append(HumanMessage(content=user_input))
        result = selected_agent.invoke(state, config=config)
        if "messages" in result:
            state["messages"] = result["messages"]

        if state["messages"]:
            last = state["messages"][-1]
            if isinstance(last, AIMessage):
                console.print(f"\n[bold cyan]Bot:[/] {last.content}\n")
            else:
                console.print("\n[bold cyan]Bot:[/] [respuesta no reconocida]\n")
        else:
            console.print("\n[bold cyan]Bot:[/] [sin respuesta]\n")


@docs_app.command("sources")
def list_sources() -> None:
    """Mostrar los vectorstores disponibles."""
    table = Table(title="Vectorstores disponibles")
    table.add_column("Fuente", style="cyan")
    table.add_column("Descripción")
    table.add_column("Ruta preferida")
    for key, cfg in VECTORSTORE_SOURCES.items():
        preferred = str(cfg["candidates"][0])
        table.add_row(key, cfg["friendly"], preferred)
    console.print(table)


@docs_app.command("search")
def docs_search(
    query: str = typer.Argument(..., help="Pregunta o texto a buscar"),
    source: str = typer.Option("langchain", "--source", "-s", help="langchain u openclaw"),
    top_k: int = typer.Option(5, min=1, max=10, help="Número de fragmentos"),
) -> None:
    """Buscar en los vectorstores de documentación."""
    vs = _load_vectorstore(source)
    docs = vs.similarity_search(query, k=top_k)

    if not docs:
        console.print("No se encontraron resultados.")
        raise typer.Exit()

    for idx, doc in enumerate(docs, start=1):
        console.print(f"\n[bold]#{idx}[/] Score aproximado: {doc.metadata.get('score', 'N/A')}")
        console.print(doc.page_content[:1000])
        if doc.metadata:
            console.print(f"[dim]Metadata:[/] {doc.metadata}")


@app.callback()
def main_callback() -> None:
    """MongoAI CLI"""
    # Simple sanity check para claves necesarias
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[yellow]Aviso:[/] OPENAI_API_KEY no está configurada; algunos comandos fallarán.")


def main() -> None:
    app()


if __name__ == "__main__":
    try:
        main()
    except typer.Exit:
        sys.exit(0)
