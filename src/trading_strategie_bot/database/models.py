from sqlalchemy import create_engine, Column, UUID, String, DECIMAL, ForeignKey, Integer, JSON, DateTime, UniqueConstraint, event
import uuid
from sqlalchemy.orm import declarative_base, declared_attr, relationship
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from .events import (
    fetch_model_obj_by_id, 
    fetch_holding_by_ticker, 
    require_balance, 
    calc_total, 
    check_balance_for_entry, 
    update_balance, 
    update_holdings, 
    holding_exists, 
    check_holding_for_exit
)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=True)
Base = declarative_base()


class BaseModel(Base):
    __abstract__ = True
    
    @declared_attr
    def id(cls):
        return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class Account(BaseModel):
    __tablename__ = "accounts"
    
    username = Column(String, unique=True, nullable=False)

    strategies = relationship("Strategie", back_populates="accounts")
    
class Strategie(BaseModel):
    __tablename__ = "strategies"
    
    user_id = Column(UUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    strategie_name = Column(String, unique=True, nullable=False)
    description = Column(String)
    
    short_ma_period = Column(Integer, nullable=False)
    long_ma_period = Column(Integer, nullable=False)
    rsi_period = Column(Integer)
    entry_threshold = Column(DECIMAL(10, 4))
    exit_threshold = Column(DECIMAL(10, 4))
    stop_loss = Column(DECIMAL(10, 4))
    take_profit = Column(DECIMAL(10, 4))
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    account = relationship("Account", back_populates="strategies")
    tests = relationship("Test", back_populates="strategies")

class Test(BaseModel):
    __tablename__ = "tests"
    
    strategie_id = Column(UUID, ForeignKey("strategies.id"), nullable=False)
    test_name = Column(String, unique=True, nullable=False)
    
    balance = Column(DECIMAL(25, 4), nullable=False)
    time_period = Column(JSON, nullable=False)
    
    strategie = relationship("Strategie", back_populates="tests")
    holdings = relationship("Holding", back_populates="tests")
    trades = relationship("Trade", back_populates="tests")

class Holding(BaseModel):
    __tablename__ = "holdings"
    
    test_id = Column(UUID, ForeignKey("tests.id"), nullable=False)
    ticker = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("test_id", "ticker", name="test_ticker_uc"),)
    
    shares = Column(DECIMAL(25, 4), nullable=False)
    
    test = relationship("Test", back_populates="holdings")
    trades = relationship("Trade", back_populates="holdings")

class Trade(BaseModel):
    __tablename__ = "trades"
    
    test_id = Column(UUID, ForeignKey("tests.id"), nullable=False)
    holding_id = Column(UUID, ForeignKey("holdings.id"), nullable=False)
    
    ticker = Column(String)
    shares = Column(DECIMAL(10, 4), nullable=False)
    
    type = Column(String)
    
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "trade",
        "with_polymorphic": "*",
    }
    
    test = relationship("Test", back_populates="trades")
    holding = relationship("Holding", back_populates="trades")
    
class Buy(Trade):
    __tablename__ = "buys"
    
    id = Column(UUID, ForeignKey("trades.id"), primary_key=True)
    
    entry_price = Column(DECIMAL(10, 4), nullable=False)
    bought_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __mapper_args__ = {
        "polymorphic_identity": "buy"
    }

class Sell(Trade):
    __tablename__ = "sells"
    
    id = Column(UUID, ForeignKey("trades.id"), primary_key=True)  
    
    exit_price = Column(DECIMAL(10, 4), nullable=False)
    sell_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __mapper_args__ = {
        "polymorphic_identity": "sell"
    }


@event.listens_for(Buy, "before_insert")
def validate_buy_in(mapper, connection, target):
    target._test = fetch_model_obj_by_id(connection, target.test_id)
    target._total_cost = calc_total(target.shares, target.entry_price)
    
    require_balance(target._test)
    check_balance_for_entry(target)
    
@event.listens_for(Buy, "after_insert")
def update_data_buy(mapper, connection, target):
    holding = fetch_holding_by_ticker(connection, target.ticker)
    
    update_balance(connection, target, target._total_cost, -1)
    update_holdings(connection, target, holding)


@event.listens_for(Sell, "before_insert")
def validate_exit(mapper, connection, target):
    target._test = fetch_model_obj_by_id(connection, target.test_id)
    target._holding = fetch_holding_by_ticker(connection, target.ticker)
    
    require_balance(target._test)
    holding_exists(target._holding)
    check_holding_for_exit(target)
    
@event.listens_for(Sell, "after_insert")
def update_data_sell(mapper, connection, target):
    total_earnings = calc_total(target.shares, target.exit_price)
    
    update_balance(connection, target, total_earnings)
    update_holdings(connection, target, target._holding -1)
