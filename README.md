# Monad Agent: Micro-Bets + Market Maker (Simulation)

This project is a beginner-built autonomous agent that:
- Connects to Monad RPC
- Scans ERC-20 balances (dust scan)
- Runs agent-to-agent micro-bets (random oracle simulation)
- Tracks persistent memory:
  - ledger.json = bet history
  - scores.json = agent reputation (wins/losses)
- Produces market-maker quotes (buy/sell spread simulation)

## Files
- agent.py — main agent loop
- bets.py — MicroBet class
- market.py — MarketMaker quote logic
- oracle.py — randomness (coin flip)
- ledger.json — saved bet history
- scores.json — win/loss totals

## Setup (Mac)
```bash
cd ~/monad-agent
source venv/bin/activate
pip install -r requirements.txt

