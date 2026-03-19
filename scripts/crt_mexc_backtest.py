"""Backtest CRT multi-activo usando velas 15m desde MEXC (public API)."""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import requests
import numpy as np

MEXC_BASE_URL = "https://api.mexc.com"

TOP10 = [
    "BTC",
    "ETH",
    "BNB",
    "XRP",
    "SOL",
    "ADA",
    "DOGE",
    "TRX",
    "LTC",
    "BCH",
]


@dataclass
class CRTConfig:
    symbol: str
    days: int = 30
    interval: str = "15m"
    fee_bps: float = 12.0
    slippage_bps: float = 8.0
    target_method: Literal["mid_daily", "daily_high"] = "mid_daily"
    stop_buffer_pct: float = 0.0005


def fetch_mexc_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - days * 24 * 60 * 60 * 1000
    frames: list[pd.DataFrame] = []
    limit = 1000
    current = start_ts

    while current < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": current,
            "endTime": min(current + limit * 15 * 60 * 1000, end_ts),
        }
        resp = requests.get(f"{MEXC_BASE_URL}/api/v3/klines", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.set_index("open_time")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        frames.append(df[["open", "high", "low", "close"]])
        current = int(df.index[-1].timestamp() * 1000) + 1
        if len(data) < limit:
            break
        time.sleep(0.2)

    if not frames:
        raise RuntimeError(f"Sin datos para {symbol}")
    full = pd.concat(frames)
    full = full[~full.index.duplicated(keep="last")]  # dedupe
    return full.sort_index()


def resample_ranges(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    sampled = df.resample(freq).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    }).dropna()
    sampled["prev_high"] = sampled["high"].shift(1)
    sampled["prev_low"] = sampled["low"].shift(1)
    sampled["long_ready"] = (
        (sampled["low"] < sampled["prev_low"]) &
        (sampled["close"] > sampled["prev_low"]) &
        (sampled["close"] < sampled["prev_high"])
    )
    sampled["short_ready"] = (
        (sampled["high"] > sampled["prev_high"]) &
        (sampled["close"] < sampled["prev_high"]) &
        (sampled["close"] > sampled["prev_low"])
    )
    return sampled


def align_flags(base: pd.DataFrame, sampled: pd.DataFrame, suffix: str) -> pd.DataFrame:
    aligned = sampled[["long_ready", "short_ready", "prev_high", "prev_low"]].reindex(base.index, method="ffill")
    return aligned.rename(columns=lambda c: f"{c}_{suffix}")


def prepare_base(df: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()
    base["prev_high_base"] = base["high"].shift(1)
    base["prev_low_base"] = base["low"].shift(1)
    return base.dropna()


def run_crt(df: pd.DataFrame, cfg: CRTConfig) -> dict:
    df = prepare_base(df)
    daily = resample_ranges(df, "1d")
    h4 = resample_ranges(df, "4h")
    h1 = resample_ranges(df, "1h")

    daily_aligned = align_flags(df, daily, "daily")
    h4_aligned = align_flags(df, h4, "h4")
    h1_aligned = align_flags(df, h1, "h1")

    base = pd.concat([df, daily_aligned, h4_aligned, h1_aligned], axis=1).dropna()

    cost = (cfg.fee_bps + cfg.slippage_bps) / 10000
    strat_returns: list[float] = []
    bh_returns: list[float] = []
    trades: list[dict] = []

    position = None
    prev_close = base["close"].iloc[0]
    pending_entry = None
    entry_price = None
    entry_time = None
    stop_price = None
    tp_price = None

    idx_list = base.index.to_list()

    for idx, ts in enumerate(idx_list):
        row = base.iloc[idx]
        close = row["close"]
        last = prev_close if prev_close else close
        bh_ret = close / last - 1
        bh_returns.append(bh_ret)

        if pending_entry is not None and ts >= pending_entry["timestamp"]:
            position = "long"
            entry_price = pending_entry["price"]
            entry_time = pending_entry["timestamp"]
            stop_price = pending_entry["stop"]
            tp_price = pending_entry["tp"]
            prev_close = entry_price
            pending_entry = None

        strat_ret = 0.0
        if position == "long":
            exit_price = close
            exit_reason = None
            if row["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
            elif row["high"] >= tp_price:
                exit_price = tp_price
                exit_reason = "target"
            strat_ret = exit_price / prev_close - 1
            if exit_reason:
                strat_ret -= cost
                trades.append({
                    "entry": entry_time,
                    "exit": ts,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return": (exit_price / entry_price) - 1,
                    "reason": exit_reason,
                })
                position = None
                entry_time = None
                entry_price = None
                stop_price = None
                tp_price = None
                prev_close = close
            else:
                prev_close = close
        else:
            strat_ret = 0.0
            prev_close = close

        strat_returns.append(strat_ret)

        if position is None and idx + 1 < len(base):
            daily_ready = bool(row.get("long_ready_daily"))
            h4_ready = bool(row.get("long_ready_h4"))
            h1_ready = bool(row.get("long_ready_h1"))
            base_ready = (
                (row["low"] < row["prev_low_base"]) and
                (row["close"] > row["prev_low_base"]) and
                (row["close"] < row["prev_high_base"])
            )
            if daily_ready and h4_ready and h1_ready and base_ready:
                next_open = base.iloc[idx + 1]["open"]
                day_low = row.get("prev_low_daily")
                day_high = row.get("prev_high_daily")
                if cfg.target_method == "daily_high" and pd.notna(day_high):
                    target_price = day_high
                elif pd.notna(day_low) and pd.notna(day_high):
                    target_price = day_low + 0.5 * (day_high - day_low)
                else:
                    target_price = row.get("prev_high_h4")
                stop_candidate = row["low"] * (1 - cfg.stop_buffer_pct)
                if pd.notna(next_open) and pd.notna(target_price):
                    pending_entry = {
                        "timestamp": idx_list[idx + 1],
                        "price": next_open,
                        "stop": stop_candidate,
                        "tp": target_price,
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
    }


def main():
    parser = argparse.ArgumentParser(description="CRT backtest con datos 15m de MEXC")
    parser.add_argument("--symbols", nargs="*", default=TOP10, help="Lista de tickers base (USDt)")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--target", choices=["mid_daily", "daily_high"], default="mid_daily")
    args = parser.parse_args()

    rows = []
    for base_symbol in args.symbols:
        pair = base_symbol.upper() + "USDT"
        cfg = CRTConfig(symbol=pair, days=args.days, target_method=args.target)
        try:
            data = fetch_mexc_klines(pair, cfg.interval, cfg.days)
            results = run_crt(data, cfg)
            rows.append({
                "symbol": base_symbol.upper(),
                **results,
            })
        except Exception as exc:
            rows.append({
                "symbol": base_symbol.upper(),
                "error": str(exc),
            })
            continue

    df = pd.DataFrame(rows)
    print(df)


if __name__ == "__main__":
    main()
