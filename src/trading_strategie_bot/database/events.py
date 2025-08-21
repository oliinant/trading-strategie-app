from sqlalchemy import text
from decimal import Decimal

def fetch_model_obj_by_id(connection, id):
    obj = connection.execute(
        text("SELECT * FROM tests WHERE id=:id"), 
        {"id": id}
    ).fetchone()
    return None if obj is None else obj

def fetch_holding_by_ticker(connection, ticker):
    holding = connection.execute(
        text("SELECT * FROM tests WHERE ticker=:ticker"), 
        {"ticker": ticker}
    ).fetchone()
    return None if holding is None else holding

def require_balance(test):
    balance = test[2]
    if balance is None:
        raise ValueError("Error: Trade must be linked to a valid test balance")
    return balance

def calc_total(shares, price):
    return shares * price

def check_balance_for_entry(target):
    balance = target._test[2]
    if balance < target._total_cost:
        raise ValueError("Error: Insufficent balance")


def update_balance(connection, target, total, sign=1):
    test_id = target._test[0]
    test_balance = target.test[2]
    new_balance = Decimal(test_balance) + (Decimal(total) * sign)
    connection.execute(
        text("UPDATE tests SET balance=:balance WHERE id=:id"),
        {"balance": new_balance, "id": test_id}
    )

def update_holdings(connection, target, holding, sign=1):
    test_id = target._test[0]
    holding_id = holding[0]
    holding_shares = holding[2]
    if holding is None:
        connection.execute(
            text("INSERT INTO holdings (test_id, ticker, shares) VALUES (:test_id, :ticker, :shares)"),
            {"test_id": test_id, "ticker": target.ticker, "shares": target.shares}
        )  
    else:
        new_share_amount = Decimal(holding_shares) + (Decimal(target.quantity) * sign)
        connection.execute(
            text("UPDATE holdings SET shares=:shares WHERE id=:id"),
            {"shares": new_share_amount, "id": holding_id}
        )

def holding_exists(holding):
    if holding is None:
        raise ValueError("Error: No holdings available for sale")

def check_holding_for_exit(target):
    shares = target._holding[2]
    if shares < target.shares:
        raise ValueError("Error: cannot sell more shares then owned")