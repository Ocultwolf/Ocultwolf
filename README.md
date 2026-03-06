# MongoAI Pro

Clean room version of the LangGraph-based agent stack. This repo packages the reusable bits from the previous `curso-agentes-langgraph` project with a predictable environment, reproducible dependencies (via [uv](https://docs.astral.sh/uv)), and a Git-friendly layout.

## Stack

- **Python** 3.12 (managed by `uv venv`)
- **LangGraph / LangChain** for graph-based orchestration
- **FastAPI** service entrypoints (`src/api`)
- **Agent library** in `src/agents` (orchestrator, evaluators, RAG routes, etc.)
- **Docker runtime** (`openclaw-in-docker/`) to spin up OpenClaw sandboxes
- **Notebooks** (`notebooks/`) with the learning path from Platzi's LangGraph course

## Getting Started

```bash
# 1) Clone this repo
cd /root/.openclaw/workspace
# (git remote will be added once credentials are provided)

# 2) Ensure uv is installed
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# 3) Sync dependencies
cd mongoai-pro
uv venv               # already created, re-run if you want a fresh env
uv sync                # installs everything from pyproject + uv.lock

# 4) Activate the environment when you want to run local commands
source .venv/bin/activate
python -m agents.main  # or uv run langgraph dev
```

## Project Layout

## CLI Usage

```
uv run python cli.py agents list
uv run python cli.py agents chat code_review
uv run python cli.py docs search "pregunta" --source langchain
```

Los vectorstores deben existir en `data/vectorstores/` (o el CLI usará las rutas heredadas).

Agentes destacados: `code_review`, `vector_agent`, `trading` (investigación y backtesting cripto).

```
mongoai-pro/
├── src/                # package code (agents + FastAPI)
├── notebooks/          # tutorial + experimentation notebooks
├── init-scripts/       # helper scripts for datasets, env prep, etc.
├── openclaw-in-docker/ # infrastructure for spawning OpenClaw containers
├── scripts/            # CLI helpers (build_openclaw_knowledge.py, etc.)
├── docker-compose.yml  # local stack wiring
├── pyproject.toml      # project metadata + deps
├── uv.lock             # locked dependency graph
└── .venv/              # uv-managed virtual environment (ignored by git)
```

## Next Steps

1. Wire this repo to the remote once Git credentials are available (`git remote add origin ...`).
2. Configure environment secrets (OpenAI, Anthropic, Ollama) via `.env` or the existing `/root/.openclaw/secrets.env`.
3. Hook telecom / OpenClaw runtime by updating `openclaw-in-docker/openclaw-in-docker/.env`.
4. Decide whether to keep FAISS/vectorstore artifacts; currently ignored to keep the repo light.

Feel free to add CONTRIBUTING instructions, CI workflows, or deployment scripts once we know the target hosting surface.

## CRT Strategy (video-based)

Para replicar el flujo simplificado de CRT (diario→4H→1H):

```
uv run python scripts/crt_strategy.py --ticker BTC-USD --days 180
```

Usa `--target daily_high` si prefieres apuntar directamente al máximo del rango diario anterior; por defecto se usa el 50% del rango.
