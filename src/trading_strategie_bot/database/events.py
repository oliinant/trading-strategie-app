from sqlalchemy import text, event
from decimal import Decimal
from .models import Buy, Sell

def fetch_row_by_column(connection, table, column_name, value):
    row = connection.execute(
        text(f"SELECT * FROM {table} WHERE {column_name}=:{column_name}"), 
        {column_name: value}
    ).mappings().fetchone()
    return None if row is None else row

def require_balance(balance):
    if balance is None:
        raise ValueError("Error: Trade must be linked to a valid backtest balance")

def calc_total(shares, price):
    return shares * price

def has_required_items_for_trade(value, cost, error_descriptor):
    if value < cost:
        raise ValueError(f"Error: Insufficent {error_descriptor}")

def calc_new_balance_shares(old_value, value_to_add, sign):
    return Decimal(old_value) + (Decimal(value_to_add) * sign)

def update_balance_holding_by_id(connection, table, value_to_update, new_value, id):
    connection.execute(
        text(f"UPDATE {table} SET {value_to_update}=:{value_to_update} WHERE id=:id"),
        {value_to_update: new_value, "id": id}
    )

def create_new_holding(connection, backtest_id, ticker, bought_shares):
        connection.execute(
            text("INSERT INTO holdings (backtest_id, ticker, shares) VALUES (:backtest_id, :ticker, :shares)"),
            {"backtest_id": backtest_id, "ticker": ticker, "shares": bought_shares}
        )  

def check_holding_exists(holding):
    if holding is None:
        return False
    else:
        return True


def prepare_backtest_for_buy_in(connection, target):
    target._backtest = fetch_row_by_column(connection, "tests", "id", target.backtest_id)
    require_balance(target._backtest)
    
    total_cost = calc_total(target.shares, target.entry_price)
    has_required_items_for_trade(target.backtest["balance"], total_cost, "balance")
    
    return calc_new_balance_shares(target._backtest["balance"], total_cost, -1)

def prepare_holding_for_buy_in(connection, target):
    target._holding = fetch_row_by_column(connection, "holdings", "ticker", target.ticker)
    
    if check_holding_exists(target._holding):
        return calc_new_balance_shares(target._holding["shares"], target.shares, 1)
    return None


def prepare_backtest_for_exit(connection, target):
    target._backtest = fetch_row_by_column(connection, "tests", "id", target.backtest_id)
    require_balance(target._backtest["balance"])
    
    total_profit = calc_total(target.shares, target.exit_price)
    
    return calc_new_balance_shares(target._backtest["balance"], total_profit, 1)

def prepare_holding_for_exit(connection, target):
    target._holding = fetch_row_by_column(connection, "holdings", "ticker", target.ticker)
    if check_holding_exists(target._holding):
        raise ValueError("Error: Share does not exist on backtest")
    
    has_required_items_for_trade(target.holding["shares"], target.shares, "shares")
    
    return calc_new_balance_shares(target._holding["shares"], target.shares, -1)


@event.listens_for(Buy, "before_insert")
def validate_buy_in(mapper, connection, target):
    target._updated_balance = prepare_backtest_for_buy_in
    target._updated_shares = prepare_holding_for_buy_in
    
@event.listens_for(Buy, "after_insert")
def update_backtest_buy(mapper, connection, target):
    update_balance_holding_by_id(connection, "backtests", target._backtest["balance"], target._updated_balance, target.backtest["id"])
    
    if target._updated_shares:
        update_balance_holding_by_id(connection, "holdings", target._holding["shares"], target._updated_shares, target.holding["id"])
    else:
        create_new_holding(connection, target._backtest["id"], target.ticker, target.shares)


@event.listens_for(Sell, "before_insert")
def validate_exit(mapper, connection, target):
    target._updated_balance = prepare_backtest_for_exit()
    target._updated_shares = prepare_holding_for_exit()
    
@event.listens_for(Sell, "after_insert")
def update_data_sell(mapper, connection, target):
    update_balance_holding_by_id(connection, "backtests", "balance", target._updated_balance, target._backtest["id"])
    update_balance_holding_by_id(connection, "holdings", "shares", target._updated_shares, target._holding["id"])
