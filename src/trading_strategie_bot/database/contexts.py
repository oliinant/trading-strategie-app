from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from .events import fetch_row_by_column
from .models import Buy, Sell
from sqlalchemy.engine import Connection

def none_rule(rule_obj: str | Decimal, rule_identifier: str) -> None:
    if rule_obj is None:
        ValueError(f"{rule_identifier.capitalize()} cannot be None")

def none_negative_rule(rule_obj: str | Decimal, rule_identifier: str) -> None:
    none_rule(rule_obj, rule_identifier)
    if rule_obj > 0:
        ValueError(f"{rule_identifier.capitalize()} cannot be negative value")

@dataclass
class TradeContext:
    backtest_id: UUID
    holding_id: UUID
    
    ticker: str
    shares: Decimal
    
    backtest_balance: Decimal
    holding_shares: Decimal | None
    
    def __post_init__(self) -> None:
        rule_list = [
            ("none", self.backtest_id, "backtest ID")
            ("none", self.holding_id, "holding ID")
            ("none", self.ticker, "ticker"),
            ("negative", self.shares, "shares"),
            ("negative", self.backtest_balance, "backtest balance")
        ]
        
        for rule_items in rule_list:
            if rule_items[0] == "none":
                none_rule(rule_items[1], rule_items[2])
            elif rule_items[0] == "negative":
                none_negative_rule(rule_items[1], rule_items[2])
                 
@dataclass
class BuyContext(TradeContext):
    entry_price: Decimal
    
    def __post_init__(self) -> None:
        none_negative_rule(self.entry_price, "Entry Price")

class SellContext(TradeContext):
    exit_price: Decimal

    def __post_init__(self) -> None:
        none_negative_rule(self.exit_price, "Exit Price")


def create_buy_context(connection: Connection, target: Buy, ctx: BuyContext | SellContext) -> BuyContext:
    trade = fetch_row_by_column(connection, "trades", "id", target.id)
    backtest = fetch_row_by_column(connection, "backtests", "id", trade["backtest_id"])
    holding = fetch_row_by_column(connection, "holdings", "ticker", trade["ticker"])
    
    return ctx(
        backtest_id = trade.holding_id,
        holding_id = trade.holding_id,
        
        entry_price = target.entry_price,
        ticker = trade["ticker"],
        shares = trade["shares"],
        
        backtest_balance = backtest["backtest"],
        holding_shares = holding["shares"] if holding else None
    )