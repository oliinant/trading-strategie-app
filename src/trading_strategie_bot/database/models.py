from sqlalchemy import create_engine, Column, UUID, String, DECIMAL, ForeignKey, Integer, JSON, DateTime, UniqueConstraint, event
import uuid
from sqlalchemy.orm import declarative_base, declared_attr, relationship
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from .events import (
    prepare_backtest_for_buy_in,
    prepare_holding_for_buy_in,
    prepare_backtest_for_exit,
    prepare_holding_for_exit,
    update_balance_holding_by_id,
    create_new_holding
    
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
    
    account_id = Column(UUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
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
    backtests = relationship("Backtest", back_populates="strategies")

class Backtest(BaseModel):
    __tablename__ = "backtests"
    
    strategie_id = Column(UUID, ForeignKey("strategies.id"), nullable=False)
    test_name = Column(String, unique=True, nullable=False)
    
    balance = Column(DECIMAL(25, 4), nullable=False)
    time_period = Column(JSON, nullable=False)
    
    strategie = relationship("Strategie", back_populates="backtests")
    holdings = relationship("Holding", back_populates="backtests")
    trades = relationship("Trade", back_populates="backtests")

class Holding(BaseModel):
    __tablename__ = "holdings"
    
    backtest_id = Column(UUID, ForeignKey("backtests.id"), nullable=False)
    ticker = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("backtest_id", "ticker", name="backtest_ticker_uc"),)
    
    shares = Column(DECIMAL(25, 4), nullable=False)
    
    backtest = relationship("Backtest", back_populates="holdings")
    trades = relationship("Trade", back_populates="holdings")

class Trade(BaseModel):
    __tablename__ = "trades"
    
    backtest_id = Column(UUID, ForeignKey("backtests.id"), nullable=False)
    holding_id = Column(UUID, ForeignKey("holdings.id"), nullable=False)
    
    ticker = Column(String)
    shares = Column(DECIMAL(10, 4), nullable=False)
    
    type = Column(String)
    
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "trade",
        "with_polymorphic": "*",
    }
    
    backtest = relationship("Backtest", back_populates="trades")
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
