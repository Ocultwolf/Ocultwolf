from langgraph.graph import StateGraph, END, START
from typing import TypedDict
import subprocess
import hashlib
from pathlib import Path
from langchain.chat_models import init_chat_model
from duckduckgo_search import DDGS

llm = init_chat_model("openai:gpt-4.1-mini")

# =========================
# State del subgrafo
# =========================

class ExecutorState(TypedDict):
    code: str
    requirements: list[str]
    docker_workdir: str
    execution_success: bool
    execution_error: str | None
    execution_stdout: str | None
    iteration: int


# =========================
# Nodo 1: Inferir dependencias
# =========================

def infer_dependencies(state: ExecutorState):
    response = llm.invoke([
        ("system", "You extract Python dependencies."),
        ("user", f"""
From the following Python code, output ONLY a pip-compatible
requirements list. Exclude standard library modules.

CODE:
{state['code']}
""")
    ])

    requirements = [
        line.strip()
        for line in response.text.splitlines()
        if line.strip()
    ]

    return {
        "requirements": requirements,
        "iteration": state.get("iteration", 0) + 1
    }


# =========================
# Nodo 2: Crear contexto Docker
# =========================

def build_docker_context(state: ExecutorState):
    code = state["code"]
    reqs = state["requirements"]

    project_id = hashlib.sha256(code.encode()).hexdigest()[:10]
    workdir = Path(f"./docker_runtime/{project_id}")
    workdir.mkdir(parents=True, exist_ok=True)

    (workdir / "main.py").write_text(code)
    (workdir / "requirements.txt").write_text("\n".join(reqs))

    dockerfile = """
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
"""
    (workdir / "Dockerfile").write_text(dockerfile.strip())

    return {"docker_workdir": str(workdir)}


# =========================
# Nodo 3: Ejecutar Docker
# =========================

def run_docker(state: ExecutorState):
    image = "agent_executor_img"
    workdir = state["docker_workdir"]

    try:
        subprocess.run(
            ["docker", "build", "-t", image, workdir],
            capture_output=True,
            text=True,
            timeout=120,
            check=True
        )

        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", image],
            capture_output=True,
            text=True,
            timeout=60
        )

        success = result.returncode == 0

        return {
            "execution_success": success,
            "execution_error": None if success else result.stderr,
            "execution_stdout": result.stdout,
        }

    except subprocess.CalledProcessError as exc:
        return {
            "execution_success": False,
            "execution_error": f"Build failed: {exc.stderr}
---
{exc.stdout}",
            "execution_stdout": exc.stdout,
        }

    except subprocess.TimeoutExpired:
        return {
            "execution_success": False,
            "execution_error": "Execution timed out",
            "execution_stdout": None,
        }


# =========================
# Nodo 4: Fallback Web Search + Fix
# =========================


def _web_search_snippets(query: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            rows = ddgs.text(query, max_results=max_results)
        lines = [f"- {row['title']} ({row['href']}): {row['body']}" for row in rows]
        return "\n".join(lines) if lines else "(no search results)"
    except Exception as exc:  # pragma: no cover
        return f"(web search failed: {exc})"

def error_fixer_with_web(state: ExecutorState):
    if state["execution_success"]:
        return {}

    stderr = state.get("execution_error") or "(no stderr captured)"
    stdout = state.get("execution_stdout") or "(no stdout captured)"
    query_seed = stderr.strip().splitlines()[0] if stderr.strip() else "python runtime error fix"
    search_results = _web_search_snippets(query_seed)

    response = llm.invoke([
        ("system", "You fix Python code using error logs and the provided web hints."),
        ("user", f"""
The following code failed to execute.

STDERR:
{stderr}

STDOUT:
{stdout}

Helpful web results:
{search_results}

CODE:
{state['code']}

Fix the code OR adjust dependencies.
Return ONLY the corrected code.
""")
    ])

    return {"code": response.text}


# =========================
# Condición de loop
# =========================

def should_retry(state: ExecutorState):
    if state["execution_success"]:
        return "done"
    if state["iteration"] >= 3:
        return "done"
    return "retry"


# =========================
# Construcción del subgrafo
# =========================

def build_executor_subgraph():
    builder = StateGraph(ExecutorState)

    builder.add_node("infer_dependencies", infer_dependencies)
    builder.add_node("build_docker", build_docker_context)
    builder.add_node("run_docker", run_docker)
    builder.add_node("error_fixer", error_fixer_with_web)

    builder.add_edge(START, "infer_dependencies") 
    builder.add_edge("infer_dependencies", "build_docker")
    builder.add_edge("build_docker", "run_docker")
    builder.add_edge("run_docker", "error_fixer")

    builder.add_conditional_edges(
        "error_fixer",
        should_retry,
        {
            "retry": "infer_dependencies",
            "done": END
        }
    )

    return builder.compile()
