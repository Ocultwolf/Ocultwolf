"""Agente profesional para investigar y backtestear estrategias de trading cripto."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from duckduckgo_search import DDGS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from langgraph.graph import END, START, MessagesState, StateGraph

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RESEARCH_CACHE_PATH = CACHE_DIR / "trading_research.json"

research_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0.2)
plan_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0)
execution_llm = init_chat_model("openai:gpt-4.1-mini", temperature=0)


class StrategyPlan(BaseModel):
    name: str
    description: str
    ticker: str
    timeframe: Literal["1h", "1d", "1wk"]
    data_window_days: int | None = Field(default=365, description="Ventana de lookback")
    strategy_type: Literal["sma_cross", "rsi", "macd", "boll_breakout", "trend_rsi"]
    params: Dict[str, float] = Field(default_factory=dict)
    trend_filter: Dict[str, float] | None = Field(
        default=None, description="Filtro de tendencia opcional (p.ej. {'type':'sma','window':200})"
    )
    risk_notes: str | None = None
    fee_bps: float = Field(default=5.0, description="Comisión por lado en basis points")
    slippage_bps: float = Field(default=5.0, description="Slippage estimado en basis points")
    capital: float = Field(default=10000.0, description="Capital notional para el backtest")
    walkforward_segments: int = Field(default=3, ge=1, le=6)


class ExecutionPlanModel(BaseModel):
    position_sizing: str
    exchanges: List[str]
    order_types: List[str]
    automation_steps: List[str]
    risk_management: str
    checklist: List[str]


class TradingState(MessagesState):
    user_prompt: str
    research_digest: str
    strategy_plan: StrategyPlan
    backtest_report: str
    walkforward_table: str
    trade_samples: str
    execution_plan: str


# =========================
# Cache helpers
# =========================

def _load_research_cache() -> Dict[str, str]:
    if RESEARCH_CACHE_PATH.exists():
        try:
            return json.loads(RESEARCH_CACHE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_research_cache(cache: Dict[str, str]) -> None:
    RESEARCH_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


# =========================
# Research utilities
# =========================

def fetch_youtube_transcripts(urls: List[str], limit: int = 2) -> str:
    transcripts = []
    for url in urls[:limit]:
        video_id = None
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
        if not video_id:
            continue
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["es", "en"])
            snippet = " ".join(seg["text"] for seg in segments[:40])
            transcripts.append(f"[TRANSCRIPT] {url}: {snippet}")
        except (TranscriptsDisabled, NoTranscriptFound, Exception):
            continue
    return "\n".join(transcripts)


def web_research(prompt: str) -> str:
    cache = _load_research_cache()
    cache_key = hashlib.sha1(prompt.encode()).hexdigest()
    if cache_key in cache:
        return cache[cache_key]

    lines: List[str] = []
    video_links: List[str] = []
    with DDGS() as ddgs:
        for row in ddgs.text(f"crypto trading strategy {prompt}", max_results=8):
            lines.append(f"[TEXT] {row.get('title', 'resultado')}: {row.get('body', '')} ({row.get('href', '')})")
        try:
            for row in ddgs.videos(f"crypto trading strategy {prompt}", max_results=4):
                link = row.get("href") or row.get("content") or row.get("url", "")
                video_links.append(link)
                lines.append(f"[VIDEO] {row.get('title', 'video')} ({link}) - {row.get('description', '')}")
        except Exception:
            lines.append("[VIDEO] (no disponible: rate limit)")
    transcript_blob = fetch_youtube_transcripts(video_links)
    if transcript_blob:
        lines.append(transcript_blob)

    digest = "\n".join(lines) if lines else "(sin resultados web)"
    cache[cache_key] = digest
    _save_research_cache(cache)
    return digest


# =========================
# Data + indicators
# =========================

def timeframe_to_period(plan: StrategyPlan) -> tuple[str, str]:
    if plan.data_window_days:
        period = f"{max(plan.data_window_days, 30)}d"
    else:
        period = {"1h": "90d", "1d": "3y", "1wk": "10y"}.get(plan.timeframe, "1y")
    return period, plan.timeframe


def download_prices(plan: StrategyPlan) -> pd.DataFrame:
    period, interval = timeframe_to_period(plan)
    data = yf.download(
        plan.ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if data.empty:
        raise RuntimeError(f"No pude descargar datos para {plan.ticker}")
    return data


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def generate_signal(plan: StrategyPlan, close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    stype = plan.strategy_type
    params = plan.params
    signal = pd.Series(0, index=close.index)

    if stype == "sma_cross":
        fast = int(params.get("fast_window", 20))
        slow = int(params.get("slow_window", 50))
        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()
        signal = (ma_fast > ma_slow).astype(int)
    elif stype == "rsi":
        length = int(params.get("rsi_length", 14))
        overbought = float(params.get("overbought", 70))
        oversold = float(params.get("oversold", 30))
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(length).mean()
        loss = (-delta.clip(upper=0)).rolling(length).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        signal = (rsi < oversold).astype(int)
        signal[rsi > overbought] = 0
    elif stype == "macd":
        fast = int(params.get("fast_ema", 12))
        slow = int(params.get("slow_ema", 26))
        signal_len = int(params.get("signal", 9))
        macd_line = ema(close, fast) - ema(close, slow)
        macd_signal = ema(macd_line, signal_len)
        signal = (macd_line > macd_signal).astype(int)
    elif stype == "boll_breakout":
        window = int(params.get("window", 20))
        mult = float(params.get("std_mult", 2))
        basis = close.rolling(window).mean()
        dev = close.rolling(window).std()
        upper = basis + mult * dev
        signal = (close > upper).astype(int)
        signal[close < basis] = 0
    elif stype == "trend_rsi":
        trend_window = int(params.get("trend_window", 200))
        rsi_len = int(params.get("rsi_length", 14))
        oversold = float(params.get("oversold", 35))
        ma = close.rolling(trend_window).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(rsi_len).mean()
        loss = (-delta.clip(upper=0)).rolling(rsi_len).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        signal = ((close > ma) & (rsi < oversold)).astype(int)
    else:
        raise ValueError(f"Strategy {stype} no soportada")

    if plan.trend_filter and plan.trend_filter.get("type") == "sma":
        window = int(plan.trend_filter.get("window", 100))
        trend_ma = close.rolling(window).mean()
        signal = signal * (close > trend_ma).astype(int)

    signal = signal.fillna(0)
    return signal


def apply_transaction_costs(signal: pd.Series, returns: pd.Series, plan: StrategyPlan) -> pd.Series:
    shifted = signal.shift(1).fillna(0)
    raw = returns * shifted
    transitions = signal.diff().abs().fillna(0)
    cost = (plan.fee_bps + plan.slippage_bps) / 10000
    return raw - transitions * cost


def compute_walkforward_metrics(equity: pd.Series, strategy_returns: pd.Series, plan: StrategyPlan) -> List[Dict[str, float]]:
    segments = max(1, plan.walkforward_segments)
    segment_len = max(1, len(equity) // segments)
    rows = []
    for i in range(segments):
        start = i * segment_len
        end = len(equity) if i == segments - 1 else (i + 1) * segment_len
        seg = equity.iloc[start:end]
        seg_ret = strategy_returns.iloc[start:end]
        if len(seg) < 2:
            continue
        total = float(seg.iloc[-1] / seg.iloc[0] - 1)
        sharpe = 0.0
        if seg_ret.std() > 0:
            sharpe = math.sqrt(252) * seg_ret.mean() / seg_ret.std()
        rows.append({
            "segment": i + 1,
            "return": total,
            "sharpe": sharpe,
        })
    return rows


def format_walkforward_table(rows: List[Dict[str, float]]) -> str:
    if not rows:
        return "(no walk-forward disponible)"
    header = "| Segmento | Retorno | Sharpe |\n|---|---|---|"
    lines = [header]
    for row in rows:
        lines.append(f"| {row['segment']} | {row['return']:.2%} | {row['sharpe']:.2f} |")
    return "\n".join(lines)


def build_trade_log(signal: pd.Series, close: pd.Series) -> List[Dict[str, Any]]:
    entries = []
    position = 0
    entry_price = 0.0
    entry_time = None
    for ts, sig in signal.iteritems():
        if position == 0 and sig == 1:
            position = 1
            entry_price = close.loc[ts]
            entry_time = ts
        elif position == 1 and sig == 0:
            exit_price = close.loc[ts]
            ret = (exit_price / entry_price) - 1
            entries.append({
                "entry": str(entry_time),
                "exit": str(ts),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "return_pct": ret,
            })
            position = 0
    return entries[-5:]


def run_backtest(plan: StrategyPlan) -> Dict[str, Any]:
    data = download_prices(plan)
    close = data["Close"].copy()
    high = data.get("High", close)
    low = data.get("Low", close)
    signal = generate_signal(plan, close, high, low)
    returns = close.pct_change().fillna(0)
    strategy_returns = apply_transaction_costs(signal, returns, plan)

    equity = (1 + strategy_returns).cumprod()
    bh_equity = (1 + returns).cumprod()

    sharpe = 0.0
    sortino = 0.0
    if strategy_returns.std() > 0:
        sharpe = math.sqrt(252) * strategy_returns.mean() / strategy_returns.std()
    downside = strategy_returns[strategy_returns < 0]
    if downside.std() > 0:
        sortino = math.sqrt(252) * strategy_returns.mean() / downside.std()

    drawdown = equity / equity.cummax() - 1
    metrics = {
        "total_return": float(equity.iloc[-1] - 1),
        "buy_hold_return": float(bh_equity.iloc[-1] - 1),
        "annual_return": float(((equity.iloc[-1]) ** (252 / len(equity)) - 1)),
        "volatility": float(strategy_returns.std() * math.sqrt(252)),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((strategy_returns > 0).mean()),
        "avg_trade": float(strategy_returns[strategy_returns != 0].mean()),
        "num_trades": int((signal.diff().fillna(0) == 1).sum()),
    }

    walk_rows = compute_walkforward_metrics(equity, strategy_returns, plan)
    walk_table = format_walkforward_table(walk_rows)
    trades = build_trade_log(signal, close)

    sample = data.tail(5).assign(signal=signal.tail(5).values)

    return {
        "metrics": metrics,
        "walk_table": walk_table,
        "sample": sample.to_markdown(),
        "trade_log": trades,
    }


# =========================
# Nodes
# =========================

def ingest_prompt(state: TradingState):
    last = state["messages"][-1]
    return {
        "user_prompt": last.content,
        "research_digest": "",
        "backtest_report": "",
        "walkforward_table": "",
        "trade_samples": "",
        "execution_plan": "",
    }


def parse_plan_response(content: str) -> StrategyPlan:
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        snippet = content[start:end]
    except ValueError:
        snippet = content
    data = json.loads(snippet)
    return StrategyPlan(**data)


def strategy_research(state: TradingState):
    research_notes = web_research(state["user_prompt"])
    plan_response = plan_llm.invoke(
        [
            (
                "system",
                "Eres un analista cuant especializado en cripto. Selecciona SOLO una estrategia soportada (sma_cross, rsi, macd, boll_breakout, trend_rsi).",
            ),
            (
                "user",
                f"""
Resumen del usuario: {state['user_prompt']}
Resultados web:
{research_notes}

Responde con un JSON que tenga las llaves: name, description, ticker (formato XXX-USD), timeframe (1h/1d/1wk), data_window_days, strategy_type, params (objeto con números), trend_filter (objeto o null), risk_notes, fee_bps, slippage_bps, capital, walkforward_segments.
""",
            ),
        ]
    )
    plan = parse_plan_response(plan_response.content)

    summary = research_llm.invoke(
        [
            (
                "system",
                "Resume los hallazgos y cita fuentes si es posible.",
            ),
            (
                "user",
                f"Plan elegido: {plan.model_dump_json()}\nResultados web:\n{research_notes}",
            ),
        ]
    )

    return {
        "research_digest": summary.content,
        "strategy_plan": plan,
    }


def backtest_node(state: TradingState):
    plan = state["strategy_plan"]
    try:
        result = run_backtest(plan)
        metrics = result["metrics"]
        summary = (
            f"Retorno total: {metrics['total_return']:.2%} vs buy&hold {metrics['buy_hold_return']:.2%}\n"
            f"Retorno anualizado: {metrics['annual_return']:.2%}\n"
            f"Sharpe: {metrics['sharpe']:.2f} | Sortino: {metrics['sortino']:.2f}\n"
            f"Max DD: {metrics['max_drawdown']:.2%} | Operaciones: {metrics['num_trades']}\n"
            f"Win rate: {metrics['win_rate']:.2%} | Promedio trade: {metrics['avg_trade']:.4f}\n"
            f"\nMuestras recientes:\n{result['sample']}"
        )
        trade_samples = json.dumps(result["trade_log"], ensure_ascii=False, indent=2)
        walk_table = result["walk_table"]
    except Exception as exc:  # pragma: no cover
        summary = f"Backtest falló: {exc}"
        trade_samples = "[]"
        walk_table = "(sin datos)"
    return {
        "backtest_report": summary,
        "walkforward_table": walk_table,
        "trade_samples": trade_samples,
    }


def execution_plan_node(state: TradingState):
    plan = state["strategy_plan"]
    backtest = state.get("backtest_report", "")
    walk = state.get("walkforward_table", "")
    response = execution_llm.invoke(
        [
            (
                "system",
                "Eres un portfolio manager. Responde SOLO con JSON válido para ExecutionPlanModel.",
            ),
            (
                "user",
                f"""
Plan estructurado:
{plan.model_dump_json()}

Resumen del backtest:
{backtest}

Walk-forward:
{walk}

Incluye exchanges sugeridos, tipo de órdenes, sizing, pasos de automatización y controles de riesgo.
""",
            ),
        ]
    )
    try:
        exec_plan = json.loads(response.content)
        execution_text = ExecutionPlanModel(**exec_plan).model_dump_json(indent=2, ensure_ascii=False)
    except Exception:
        execution_text = response.content
    return {"execution_plan": execution_text}


def final_response(state: TradingState):
    plan = state.get("strategy_plan")
    if plan is None:
        content = "No se pudo construir un plan de trading."
    else:
        content = f"""### Estrategia propuesta: {plan.name}

**Resumen de investigación:**
{state.get('research_digest', '(sin resumen)')}

**Plan estructurado:**
- Ticker: {plan.ticker}
- Timeframe: {plan.timeframe}
- Ventana datos: {plan.data_window_days} días
- Tipo: {plan.strategy_type}
- Parámetros: {plan.params}
- Filtro de tendencia: {plan.trend_filter or '(ninguno)'}
- Costos asumidos: fee {plan.fee_bps} bps | slippage {plan.slippage_bps} bps
- Notas de riesgo: {plan.risk_notes or '(no registradas)'}

**Backtest agregado:**
{state.get('backtest_report', '(no disponible)')}

**Walk-forward:**
{state.get('walkforward_table', '(sin datos)')}

**Muestras de trades:**
{state.get('trade_samples', '[]')}

**Plan de ejecución (JSON):**
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
