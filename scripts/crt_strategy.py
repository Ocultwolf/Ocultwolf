"""Backtest simplificado de Candle Range Theory (CRT).

Para mantenerlo reproducible con datos públicos, usamos velas de 1h como marco base
(daily -> 4h -> 1h). Si se dispone de un feed más granular, basta con cambiar
BASE_INTERVAL y rehacer la lógica del último paso.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf


BASE_INTERVAL = "1h"  # vela base donde buscamos la confirmación final (video usa 15m)


@dataclass
class CRTParams:
    ticker: str = "BTC-USD"
    lookback_days: int = 240
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    target_method: Literal["mid_daily", "daily_high"] = "mid_daily"
    stop_buffer_pct: float = 0.0005


def download_prices(params: CRTParams) -> pd.DataFrame:
    period = f"{params.lookback_days}d"
    data = yf.download(params.ticker, period=period, interval=BASE_INTERVAL, auto_adjust=True, progress=False)
    if data.empty:
        raise RuntimeError("No se pudieron descargar datos")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
    data = data.dropna()
    data.index = pd.to_datetime(data.index)
    return data


def resample_ranges(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    sampled = df.resample(freq, label="right", closed="right").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }).dropna()
    sampled["prev_high"] = sampled["High"].shift(1)
    sampled["prev_low"] = sampled["Low"].shift(1)
    sampled["long_ready"] = (
        (sampled["Low"] < sampled["prev_low"]) &
        (sampled["Close"] > sampled["prev_low"]) &
        (sampled["Close"] < sampled["prev_high"])
    )
    sampled["short_ready"] = (
        (sampled["High"] > sampled["prev_high"]) &
        (sampled["Close"] < sampled["prev_high"]) &
        (sampled["Close"] > sampled["prev_low"])
    )
    return sampled


def align_flags(base: pd.DataFrame, sampled: pd.DataFrame, suffix: str) -> pd.DataFrame:
    aligned = sampled[["long_ready", "short_ready", "prev_high", "prev_low"]].reindex(base.index, method="ffill")
    aligned = aligned.rename(columns=lambda c: f"{c}_{suffix}")
    return aligned


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["prev_high_1h"] = df["High"].shift(1)
    df["prev_low_1h"] = df["Low"].shift(1)
    return df.dropna()


def run_backtest(df: pd.DataFrame, params: CRTParams) -> dict:
    cost = (params.fee_bps + params.slippage_bps) / 10000
    df = prepare_dataframe(df)

    daily = resample_ranges(df, "1d")
    h4 = resample_ranges(df, "4h")
    aligned_daily = align_flags(df, daily, "daily")
    aligned_h4 = align_flags(df, h4, "h4")

    base = pd.concat([df, aligned_daily, aligned_h4], axis=1).dropna()

    bh_returns: list[float] = []
    strat_returns: list[float] = []
    trades: list[dict] = []

    position = None
    prev_close = base["Close"].iloc[0]

    pending_entry = None
    stop_price = None
    tp_price = None
    entry_time = None
    entry_price = None

    for idx in range(len(base)):
        row = base.iloc[idx]
        close = row["Close"]
        last = prev_close
        if last == 0:
            last = close
        bh_ret = close / last - 1
        bh_returns.append(bh_ret)

        # Activate pending entry at the open of this candle
        if pending_entry is not None and row.name >= pending_entry["timestamp"]:
            position = "long"
            entry_price = pending_entry["price"]
            prev_close = entry_price
            stop_price = pending_entry["stop"]
            tp_price = pending_entry["tp"]
            entry_time = pending_entry["timestamp"]
            pending_entry = None

        strat_ret = 0.0
        if position == "long":
            # check exits
            exit_reason = None
            exit_price = close
            if row["Low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
            elif row["High"] >= tp_price:
                exit_price = tp_price
                exit_reason = "target"

            strat_ret = exit_price / prev_close - 1
            if exit_reason:
                strat_ret -= cost
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row.name,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return": (exit_price / entry_price) - 1,
                    "reason": exit_reason,
                })
                position = None
                entry_price = None
                stop_price = None
                tp_price = None
                entry_time = None
            else:
                prev_close = close
        else:
            strat_ret = 0.0
            prev_close = close

        strat_returns.append(strat_ret)

        # Signal for next candle (only longs per video)
        if position is None and idx + 1 < len(base):
            daily_ready = bool(row.get("long_ready_daily", False))
            h4_ready = bool(row.get("long_ready_h4", False))
            h1_ready = (
                (row["Low"] < row["prev_low_1h"]) and
                (row["Close"] > row["prev_low_1h"]) and
                (row["Close"] < row["prev_high_1h"])
            )

            if daily_ready and h4_ready and h1_ready:
                next_open = base.iloc[idx + 1]["Open"]
                stop_candidate = row["Low"] * (1 - params.stop_buffer_pct)
                if params.target_method == "mid_daily":
                    day_low = row.get("prev_low_daily")
                    day_high = row.get("prev_high_daily")
                    if pd.notna(day_low) and pd.notna(day_high):
                        tp_candidate = day_low + 0.5 * (day_high - day_low)
                    else:
                        tp_candidate = row.get("prev_high_h4")
                else:
                    tp_candidate = row.get("prev_high_daily")

                if pd.notna(next_open) and pd.notna(stop_candidate) and pd.notna(tp_candidate):
                    pending_entry = {
                        "timestamp": base.index[idx + 1],
                        "price": next_open,
                        "stop": stop_candidate,
                        "tp": tp_candidate,
                    }

    strat_series = pd.Series(strat_returns, index=base.index)
    bh_series = pd.Series(bh_returns, index=base.index)

    total_return = float(np.prod(1 + strat_series) - 1)
    buy_hold_return = float(np.prod(1 + bh_series) - 1)
    sharpe = float((strat_series.mean() / strat_series.std()) * np.sqrt(252)) if strat_series.std() > 0 else 0.0
    max_dd = float((strat_series.add(1).cumprod() / strat_series.add(1).cumprod().cummax() - 1).min())

    return {
        "total_return": total_return,
        "buy_hold_return": buy_hold_return,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "num_trades": len(trades),
        "trades": trades,
        "strat_series": strat_series,
        "bh_series": bh_series,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest rápido de CRT (Daily->4H->1H)")
    parser.add_argument("--ticker", default="BTC-USD")
    parser.add_argument("--days", type=int, default=240)
    parser.add_argument("--target", choices=["mid_daily", "daily_high"], default="mid_daily")
    args = parser.parse_args()

    params = CRTParams(ticker=args.ticker, lookback_days=args.days, target_method=args.target)
    df = download_prices(params)
    results = run_backtest(df, params)

    print(f"Ticker: {params.ticker} | Intervalo base: {BASE_INTERVAL} | Lookback: {params.lookback_days}d")
    print(f"Total return: {results['total_return']:.2%}")
    print(f"Buy&Hold return: {results['buy_hold_return']:.2%}")
    print(f"Sharpe (aprox): {results['sharpe']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2%}")
    print(f"Trades ejecutados: {results['num_trades']}")
    if results['trades']:
        print("Últimos 5 trades:")
        for trade in results['trades'][-5:]:
            print(trade)


if __name__ == "__main__":
    main()
