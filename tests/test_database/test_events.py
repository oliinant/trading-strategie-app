import pytest
from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import declarative_base
from uuid import uuid4
from decimal import Decimal
from dotenv import load_dotenv
import os

from trading_strategie_bot.database.models import Backtest, Holding, Account, Strategie, Base
from trading_strategie_bot.database.events import (
    fetch_backtest_obj_by_id,
    fetch_holding_by_ticker,
    require_balance,
    calc_total,
    has_required_items_for_trade,
    calc_new_balance_shares,
    update_balance_holding_by_id,
    create_new_holding,
    check_holding_exists
)

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

AccountTable = Account.__table__
StrategieTable = Strategie.__table__
BacktestTable = Backtest.__table__
HoldingTable = Holding.__table__

def create_test_object(connection, Table: object, test_data: dict):
    connection.execute(Table.insert(), test_data)

@pytest.fixture
def account_data():
    return {
        "id": uuid4(),
        "username": "tester1"
    }

@pytest.fixture
def strategie_data(account_data):
    return {
        "id": uuid4(),
        "account_id": account_data["id"],
        "strategie_name": "Test Startegie",
        
        "short_ma_period": 50,
        "long_ma_period": 200
    }

@pytest.fixture
def backtest_data(strategie_data):
    return {
        "id": uuid4(),
        "strategie_id": strategie_data["id"],
        "test_name": "Test1",
        
        "balance": Decimal(10000.0),
        "time_period": {"start": "01-01-2020", "end": "01-01-2025"}
    }
    
@pytest.fixture
def holding_data(backtest_data):
    return {
        "id": uuid4(),
        "backtest_id": backtest_data["id"],
        "ticker": "AAPL",

        "shares": Decimal(0.5),
    }
    

@pytest.fixture
def connection(account_data, strategie_data, backtest_data, holding_data):
    engine = create_engine(f"{TEST_DATABASE_URL}?options=-csearch_path=test_schema")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    conn = engine.connect()
    
    trans = conn.begin()
    
    create_test_object(conn, AccountTable, account_data)
    create_test_object(conn, StrategieTable, strategie_data)
    create_test_object(conn, BacktestTable, backtest_data)
    create_test_object(conn, HoldingTable, holding_data)
    
    yield conn
    
    trans.rollback()
    conn.close()
    engine.dispose()
    

def test_fetch_model_backtest_by_id(connection, backtest_data):
    backtest = fetch_backtest_obj_by_id(connection, backtest_data["id"])

    assert backtest is not None
    assert backtest == backtest_data

def test_fetch_holding_by_ticker(connection, holding_data):
    holding = fetch_holding_by_ticker(connection, holding_data["ticker"])
    
    assert holding is not None
    assert holding == holding_data

def test_require_balance():
    with pytest.raises(ValueError):
        require_balance(None)

def test_calc_total():
    assert calc_total(Decimal(0.5), Decimal(10000)) == Decimal(5000)

@pytest.mark.parametrize("balance, total_cost, error_descriptor, should_raise", [
    (Decimal(10000), Decimal(5000), "balance", False),
    (Decimal(10000), Decimal(10001), "balance", True),
    (Decimal(0.5), Decimal(1), "shares", True),
    (Decimal(1), Decimal(0.5), "shares", False)
])
def test_has_required_items_for_trade(balance, total_cost, error_descriptor, should_raise):
    if should_raise: 
        with pytest.raises(ValueError):
            has_required_items_for_trade(balance, total_cost, error_descriptor)
    else:
        assert has_required_items_for_trade(balance, total_cost, error_descriptor) is None

@pytest.mark.parametrize("backtest_balance, total, sign, expected", [
    (Decimal(10000), Decimal(5000), -1, Decimal(5000)),
    (Decimal(10000), Decimal(5000), 1, Decimal(15000)),
    (Decimal(0.5), Decimal(1), 1, Decimal(1.5))
])
def test_calc_new_balance(backtest_balance, total, sign, expected):
    assert calc_new_balance_shares(backtest_balance, total, sign) == Decimal(expected)

def test_update_balance(connection, backtest_data):
    backtest = fetch_backtest_obj_by_id(connection, backtest_data["id"])
    updated_balance = Decimal(15000)
    update_balance_holding_by_id(connection, "backtests", "balance", updated_balance, backtest_data["id"])
    
    backtest = fetch_backtest_obj_by_id(connection, backtest_data["id"])
    assert backtest["balance"] == updated_balance

def test_update_holding(connection, holding_data):
    holding = fetch_holding_by_ticker(connection, holding_data["ticker"])
    updated_shares = Decimal(1.5)
    update_balance_holding_by_id(connection, "holdings", "shares", updated_shares, holding_data["id"])
    
    holding = fetch_holding_by_ticker(connection, holding_data["ticker"])
    assert holding["shares"] == updated_shares

def test_create_new_holding(connection, backtest_data):
    ticker = "TSLA"
    shares = Decimal(0.5)
    create_new_holding(connection, backtest_data["id"], ticker, shares)
    
    holding = fetch_holding_by_ticker(connection, "TSLA")
    assert holding is not None
    assert holding["backtest_id"] == backtest_data["id"]
    assert holding["ticker"] == ticker
    assert holding["shares"] == shares

@pytest.mark.parametrize("holding_input, expected", [
    (None, False),
    ("placeholder_holding", True)
])
def test_check_holding_exists(holding_input, expected, connection, holding_data,):
    if holding_input == "placeholder_holding":
        holding_input = fetch_holding_by_ticker(connection, holding_data["ticker"])
        
    assert check_holding_exists(holding_input) == expected




    