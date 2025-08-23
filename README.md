# My Trading Strategie Bot App

## Phase 1: Create Modules

### Database:
- `models.py`: Accounts, Strategies, Tests, Holdings, Buys, Sells
    - Accounts -> Strategies -> Tests (balance, start - finish tickers)
    - Handle updates to balance with event listeners (`event.py`)
- `crud.py`: add, update, drop, remove tables and data

### Test_database
- `test_crud.py`: test CRUD functions
- `test_events.py`: test events functions