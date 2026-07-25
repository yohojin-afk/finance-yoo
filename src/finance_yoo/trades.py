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
    """Weighted-average cost basis: a sell reduces quantity but leaves the average
    cost of the remaining shares unchanged, so buys and sells are summed separately.
    """
    buys = [t for t in trades_for_ticker if t.get("type", "buy") == "buy"]
    sells = [t for t in trades_for_ticker if t.get("type") == "sell"]

    bought_qty = sum(t["quantity"] for t in buys)
    if bought_qty <= 0:
        return None
    avg_price = sum(t["price"] * t["quantity"] for t in buys) / bought_qty

    sold_qty = sum(t["quantity"] for t in sells)
    remaining_qty = bought_qty - sold_qty
    if remaining_qty <= 0:
        return None
    return Position(quantity=remaining_qty, avg_price=avg_price)
