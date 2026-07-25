"""Load user-recorded buy trades and compute a weighted-average cost basis per ticker."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TRADES_PATH = Path(__file__).resolve().parent.parent.parent / "state" / "trades.json"


@dataclass
class Position:
    quantity: float
    avg_price: float


def load_trades() -> dict:
    if TRADES_PATH.exists():
        return json.loads(TRADES_PATH.read_text(encoding="utf-8"))
    return {}


def compute_position(trades_for_ticker: list[dict]) -> Position | None:
    total_qty = sum(t["quantity"] for t in trades_for_ticker)
    if total_qty <= 0:
        return None
    total_cost = sum(t["price"] * t["quantity"] for t in trades_for_ticker)
    return Position(quantity=total_qty, avg_price=total_cost / total_qty)
