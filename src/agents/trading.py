"""Agente para investigar estrategias de trading cripto y ejecutar un backtest rápido."""
from __future__ import annotations

import math
import json
from typing import Dict, Literal, NotRequired

import numpy as np
import pandas as pd
import yfinance as yf
from duckduckgo_search import DDGS
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from langgraph.graph import END, START, MessagesState, StateGraph


class StrategyPlan(BaseModel):
    name: str = Field(..., description="Nombre legible de la estrategia")
    description: str = Field(..., description="Resumen corto")
    ticker: str = Field(..., description="Ticker compatible con yfinance, p.ej. BTC-USD")
    timeframe: Literal["1h", "1d", "1wk"] = Field(
        ...,
        description="Intervalo de velas soportado (1h, 1d, 1wk)",
    )
    strategy_type: Literal["sma_cross", "rsi"] = Field(
        ...,
        description="Tipo de estrategia soportada",
    )
    params: Dict[str, float] = Field(
        default_factory=dict,
        description="Parámetros numéricos (p.ej. fast_window, slow_window, rsi_length, etc.)",
    )
    risk_notes: str | None = Field(
        default=None, description="Notas de gestión de riesgo extraídas de la investigación"
    )


class TradingState(MessagesState):
    user_prompt: str
    search_digest: str
    strategy_plan: NotRequired[StrategyPlan]
    backtest_report: str
    execution_plan: str


research_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0.2)
plan_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0)
execution_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0.2)


# =========================
# Helpers
# =========================

def web_research(prompt: str) -> str:
    query = f"crypto trading strategy {prompt}"
    lines = []
    with DDGS() as ddgs:
        for row in ddgs.text(query, max_results=5):
            lines.append(f"[TEXT] {row.get('title', 'resultado')}: {row.get('body', '')} ({row.get('href', '')})")
        try:
            for row in ddgs.videos(query, max_results=3):
                link = row.get('href') or row.get('content') or row.get('url', '')
                lines.append(f"[VIDEO] {row.get('title', 'video')} ({link}) - {row.get('description', '')}")
        except Exception as exc:
            lines.append(f"[VIDEO] (no disponible: {exc})")
    return "\n".join(lines) if lines else "(no hay resultados web)"


def timeframe_to_period(timeframe: str) -> tuple[str, str]:
    mapping = {
        "1h": ("60d", "1h"),
        "1d": ("2y", "1d"),
        "1wk": ("5y", "1wk"),
    }
    return mapping.get(timeframe, ("1y", "1d"))




def parse_plan_response(content: str) -> StrategyPlan:
    try:
        start = content.index('{')
        end = content.rindex('}') + 1
        snippet = content[start:end]
    except ValueError:
        snippet = content
    data = json.loads(snippet)
    return StrategyPlan(**data)


def run_backtest(plan: StrategyPlan) -> dict:
    period, interval = timeframe_to_period(plan.timeframe)
    data = yf.download(
        plan.ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if data.empty:
        raise RuntimeError(f"No pude descargar datos para {plan.ticker}")

    close = data["Close"].copy()
    returns = close.pct_change().fillna(0.0)

    if plan.strategy_type == "sma_cross":
        fast = int(plan.params.get("fast_window", 10))
        slow = int(plan.params.get("slow_window", 40))
        if fast >= slow:
            slow = fast * 2
        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()
        signal = (ma_fast > ma_slow).astype(int)
    elif plan.strategy_type == "rsi":
        length = int(plan.params.get("rsi_length", 14))
        overbought = float(plan.params.get("overbought", 70))
        oversold = float(plan.params.get("oversold", 30))
        delta = close.diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(length).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(length).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        signal = (rsi < oversold).astype(int)
        # Flat when overbought
        signal[rsi > overbought] = 0
    else:
        raise ValueError(f"Strategy {plan.strategy_type} no soportada")

    signal = signal.fillna(0)
    shifted_signal = signal.shift(1).fillna(0)
    strategy_returns = returns * shifted_signal

    equity_curve = (1 + strategy_returns).cumprod()
    buy_hold_curve = (1 + returns).cumprod()

    sharpe = 0.0
    if strategy_returns.std() > 0:
        sharpe = math.sqrt(252) * strategy_returns.mean() / strategy_returns.std()

    drawdown = equity_curve / equity_curve.cummax() - 1

    trades = (signal.diff().fillna(0) == 1).sum()

    metrics = {
        "strategy_cagr": float((equity_curve.iloc[-1] ** (252 / len(equity_curve)) - 1)),
        "buy_hold_cagr": float((buy_hold_curve.iloc[-1] ** (252 / len(buy_hold_curve)) - 1)),
        "total_return": float(equity_curve.iloc[-1] - 1),
        "buy_hold_return": float(buy_hold_curve.iloc[-1] - 1),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "num_trades": int(trades),
    }

    tail = data.tail(5).assign(signal=signal.tail(5).values)
    sample = tail.to_markdown()

    return {
        "metrics": metrics,
        "sample": sample,
        "equity_final": float(equity_curve.iloc[-1]),
    }


# =========================
# Nodes
# =========================

def ingest_prompt(state: TradingState):
    last = state["messages"][-1]
    return {
        "user_prompt": last.content,
        "search_digest": "",
        "backtest_report": "",
        "execution_plan": "",
    }


def strategy_research(state: TradingState):
    research_notes = web_research(state["user_prompt"])
    plan_response = plan_llm.invoke(
        [
            (
                "system",
                "Eres un analista cuant enfocado en cripto. Elige una estrategia soportada (sma_cross o rsi) y define parámetros realistas.",
            ),
            (
                "user",
                f"""
Resumen del usuario: {state['user_prompt']}
Resultados web:
{research_notes}

Devuelve SOLO un JSON con las llaves: name, description, ticker (formato XXX-USD), timeframe (1h/1d/1wk), strategy_type (sma_cross o rsi), params (objeto) y risk_notes.
""",
            ),
        ]
    )
    plan = parse_plan_response(plan_response.content)

    summary = research_llm.invoke(
        [
            (
                "system",
                "Resume los hallazgos en bullet points concisos",
            ),
            (
                "user",
                f"Plan elegido: {plan.model_dump_json()}\nResultados web:\n{research_notes}",
            ),
        ]
    )

    return {
        "search_digest": summary.content,
        "strategy_plan": plan,
    }


def backtest_node(state: TradingState):
    plan = state["strategy_plan"]
    try:
        result = run_backtest(plan)
        metrics = result["metrics"]
        summary = f"Retorno: {metrics['total_return']:.2%} vs buy&hold {metrics['buy_hold_return']:.2%}\nSharpe: {metrics['sharpe']:.2f} | MDD: {metrics['max_drawdown']:.2%}\nTrades ejecutados: {metrics['num_trades']}\n\nMuestras:\n{result['sample']}"
    except Exception as exc:  # pragma: no cover
        summary = f"Backtest falló: {exc}"
    return {"backtest_report": summary}


def execution_plan_node(state: TradingState):
    plan = state["strategy_plan"]
    backtest = state.get("backtest_report", "")
    response = execution_llm.invoke(
        [
            (
                "system",
                "Diseña un plan de ejecución para un trader discrecional/algorítmico. Incluye sizing y riesgos.",
            ),
            (
                "user",
                f"""
Plan estructurado:
{plan.model_dump_json()}

Resumen del backtest:
{backtest}

Entrega un plan accionable (checklist + métricas de riesgo).
""",
            ),
        ]
    )
    return {"execution_plan": response.content}


def final_response(state: TradingState):
    plan = state.get('strategy_plan')
    if plan is None:
        content = "No se pudo construir un plan de trading. Revisa los logs previos."
    else:
        content = f"""### Estrategia propuesta: {plan.name}

**Resumen de investigación:**
{state.get('search_digest', '(sin resumen)')}

**Plan estructurado:**
Ticker: {plan.ticker}
Timeframe: {plan.timeframe}
Tipo: {plan.strategy_type}
Parámetros: {plan.params}
Notas de riesgo: {plan.risk_notes or '(no registradas)'}

**Backtest:**
{state.get('backtest_report', '(no disponible)')}

**Ejecución recomendada:**
{state.get('execution_plan', '(no disponible)')}
"""
    return {"messages": [AIMessage(content=content)]}


# =========================
# Graph
# =========================
builder = StateGraph(TradingState)
builder.add_node("ingest_prompt", ingest_prompt)
builder.add_node("research", strategy_research)
builder.add_node("backtest", backtest_node)
builder.add_node("execution", execution_plan_node)
builder.add_node("final", final_response)

builder.add_edge(START, "ingest_prompt")
builder.add_edge("ingest_prompt", "research")
builder.add_edge("research", "backtest")
builder.add_edge("backtest", "execution")
builder.add_edge("execution", "final")
builder.add_edge("final", END)

agent = builder.compile()
