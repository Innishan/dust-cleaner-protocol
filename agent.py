import random
import json
import time
import os

from stage2_public_clean import scan_wallet_dust
from dust_scanner import run_stage2_public_dust_scan
from moltbook_bot import client, fetch_new_comments
from moltbook_bot import fetch_new_comments
from promotion import maybe_post_update, maybe_reply_to_comments
from moltbook_bot import post_marketing_update, reply_if_needed, reply_to_dms
from marketing import build_marketing_post
from swap_executor import execute_safe_swap
from liquidity_checker import can_swap_simulation
from dust_scanner import scan_dust_verified
from moltbook_helper import heartbeat, post_build_log
from bets import MicroBet
from market import MarketMaker
from web3 import Web3
from dotenv import load_dotenv
from erc20_abi import ERC20_ABI
from tokens import TOKENS
from prices import PRICES


def coin_flip():
    return random.choice([True, False])


def save_bet_to_ledger(bet):
    entry = {
        "timestamp": time.time(),
        "question": bet.question,
        "stake": bet.stake,
        "winner": bet.winner
    }

    try:
        with open("ledger.json", "r") as f:
            data = json.load(f)
    except:
        data = []

    data.append(entry)

    with open("ledger.json", "w") as f:
        json.dump(data, f, indent=2)


def update_scores(winner, loser):
    try:
        with open("scores.json", "r") as f:
            scores = json.load(f)
    except:
        scores = {}

    if winner not in scores:
        scores[winner] = {"wins": 0, "losses": 0}
    if loser not in scores:
        scores[loser] = {"wins": 0, "losses": 0}

    scores[winner]["wins"] += 1
    scores[loser]["losses"] += 1

    with open("scores.json", "w") as f:
        json.dump(scores, f, indent=2)
AGENT_PROFILES = {
    "Agent_ALPHA": {"risk": "conservative", "likes": ["gas", "price"]},
    "Agent_BETA": {"risk": "balanced", "likes": ["launch", "price"]},
    "Agent_GAMMA": {"risk": "aggressive", "likes": ["launch", "gas"]},
    "Agent_DELTA": {"risk": "balanced", "likes": ["price"]}
}

def choose_stake(agent_name):
    risk = AGENT_PROFILES.get(agent_name, {}).get("risk", "balanced")
    if risk == "conservative":
        return random.choice([0.5, 1])
    if risk == "aggressive":
        return random.choice([2, 5])
    return random.choice([1, 2])

load_dotenv()

POST_TO_MOLTBOOK = os.getenv("POST_TO_MOLTBOOK", "true").lower() == "true"

DUST_CLEANER_CONTRACT = os.getenv("DUST_CLEANER_CONTRACT")
DUST_PUBLIC_MODE = os.getenv("DUST_PUBLIC_MODE", "false").lower() == "true"
MARKETING_ENABLED = os.getenv("MARKETING_ENABLED", "true").lower() == "true"
MARKETING_EVERY_N_RUNS = int(os.getenv("MARKETING_EVERY_N_RUNS", "6"))
PROMOTION_ENABLED = os.getenv("PROMOTION_ENABLED", "true").lower() == "true"
PROMOTION_EVERY_N_RUNS = int(os.getenv("PROMOTION_EVERY_N_RUNS", "3"))
REPLY_ENABLED = os.getenv("REPLY_ENABLED", "true").lower() == "true"
REPLY_EVERY_N_RUNS = int(os.getenv("REPLY_EVERY_N_RUNS", "2"))
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CHAIN_ID = int(os.getenv("CHAIN_ID", 143))
DUST_THRESHOLD_USD = float(os.getenv("DUST_THRESHOLD_USD", 2))

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 20}))
account = w3.eth.account.from_key(PRIVATE_KEY)
address = account.address

def run_agent_once():
    # Run counter (simple, resets when you restart the script)
    global RUN_COUNT
    try:
        RUN_COUNT += 1
    except NameError:
        RUN_COUNT = 1

    sold_symbols = []
    did_sell = False
    sold_symbols = []

    print("\n=== AGENT STARTED ===")

    print("[env] has MOLTBOOK_API_KEY:", "MOLTBOOK_API_KEY" in os.environ)
    print("[env] MOLTBOOK_API_KEY length:", len(os.getenv("MOLTBOOK_API_KEY","")))
    print("[env] MOLTBOOK_SUBMOLT:", repr(os.getenv("MOLTBOOK_SUBMOLT","")))

    try:
        hb = heartbeat()
        print("Moltbook:", (hb or {}).get("status"))
    except Exception as e:
        print("Moltbook: unreachable (continuing). error:", e)    
    
    print("Agent wallet:", address)
    print("Connected to Monad:", w3.is_connected())
    print("MON balance:", w3.from_wei(w3.eth.get_balance(address), "ether"))

    print("\n--- Dust Analysis (Stage 2 Public) ---")
    try:
        report = run_stage2_public_dust_scan(address)
        dust = report.get("dust", []) or []

        print("source:", report.get("source"))
        print("wallet:", report.get("wallet", address))
        print("dust_count:", len(dust))
        if report.get("notes"):
            print("notes:", report["notes"])

        if not dust:
            print("No actionable dust found (Stage 2)")
        else:
            sold_symbols = []
            did_sell = False

            print("Dust found:")
            for d in dust:
                sym = d.get("symbol", "TOKEN")
                token_ca = d.get("contract")
                mon_value = d.get("mon_value")

                print(f"- {sym} amount={d.get('amount')} mon_value={mon_value} {token_ca}")

                # Safety: skip if missing contract
                if not token_ca:
                    continue

                # Skip stablecoin if you want (optional)
                if str(sym).upper() == "USDC":
                    print("Skipping USDC — stablecoin")
                    continue

                # Liquidity check
                if not can_swap_simulation(w3, token_ca):
                    print(f"Skipping {sym} — no liquidity")
                    continue

                # Execute the same swap path you already use
                sold = execute_safe_swap(w3, account, {
                    "symbol": sym,
                    "contract": token_ca,
                    "amount": d.get("amount"),
                    "decimals": d.get("decimals", 18),
                    "raw_balance": d.get("raw_balance"),
                    "mon_value": mon_value,
                })

                if sold:
                    did_sell = True
                    sold_symbols.append(sym)

    except Exception as e:
        print("[stage2] error:", e)

    # --- Moltbook promotion posts (templates) ---
    try:
        PROMOTION_ENABLED = os.getenv("PROMOTION_ENABLED", "true").lower() == "true"
        PROMOTION_EVERY_N_RUNS = int(os.getenv("PROMOTION_EVERY_N_RUNS", "1"))
        REPLY_ENABLED = os.getenv("REPLY_ENABLED", "true").lower() == "true"
        REPLY_EVERY_N_RUNS = int(os.getenv("REPLY_EVERY_N_RUNS", "1"))
    except Exception:
        PROMOTION_ENABLED, PROMOTION_EVERY_N_RUNS = True, 1
        REPLY_ENABLED, REPLY_EVERY_N_RUNS = True, 1

    # Posts your launch/progress/stage2 updates from prompts/moltbook_templates.json
    if PROMOTION_ENABLED and POST_TO_MOLTBOOK and (RUN_COUNT % PROMOTION_EVERY_N_RUNS == 0):
        try:
            maybe_post_update(client)
            print("[promotion] template post sent ✅")
        except Exception as e:
            print("[promotion] skipped:", e)

    # Replies to comments using prompts/moltbook_templates.json -> replies[]
    if REPLY_ENABLED and POST_TO_MOLTBOOK and (RUN_COUNT % REPLY_EVERY_N_RUNS == 0):
        try:
            new_comments = fetch_new_comments(limit=20)
            if new_comments:
                maybe_reply_to_comments(client, new_comments)
                print("[promotion] replied to comments ✅")
            else:
                print("[promotion] no new comments")
        except Exception as e:
            print("[promotion] reply skipped:", e)
   
    print("\n--- Micro-Bet Simulation ---")
    agents = ["Agent_ALPHA", "Agent_BETA", "Agent_GAMMA", "Agent_DELTA"]

    agent_a, agent_b = random.sample(agents, 2)
    markets = [
        {"q": "Will MON price be above $1?", "tag": "price"},
        {"q": "Will gas fees stay low today?", "tag": "gas"},
        {"q": "Will a new token launch today?", "tag": "launch"},
        {"q": "Will Agent_ALPHA win the next bet?", "tag": "price"}
    ]

    profile = AGENT_PROFILES.get(agent_a, {"likes": ["price", "gas", "launch"]})
    liked_tags = profile["likes"]
    
    preferred = [m for m in markets if m["tag"] in liked_tags]
    picked = random.choice(preferred if preferred else markets)

    question = picked["q"]
    stake = choose_stake(agent_a)
    bet = MicroBet(
        question=question,
        stake=stake,
        agent_a=agent_a,
        agent_b=agent_b
    )

    print("Bet created:")
    print("Question:", bet.question)
    print("Stake:", bet.stake)
    print("Agents:", bet.agent_a, "vs", bet.agent_b)

    outcome = coin_flip()
    bet.resolve(outcome)
    save_bet_to_ledger(bet)
    loser = bet.agent_b if bet.winner == bet.agent_a else bet.agent_a
    update_scores(bet.winner, loser)

    print("Bet resolved via oracle")
    print("Winner:", bet.winner, "| Stake:", bet.stake)

    print("\n--- Agent-to-Agent Market Simulation ---")
    mm = MarketMaker("TEST", "USDC", spread=0.03)
    fair_price = PRICES.get("TEST", 0.05)

    print("Fair price:", fair_price)
    print("Agent quotes BUY at:", mm.quote_buy(fair_price))
    print("Agent quotes SELL at:", mm.quote_sell(fair_price))
    
    # Marketing post (only sometimes, only if a real sell happened)
    if MARKETING_ENABLED and POST_TO_MOLTBOOK and did_sell and (RUN_COUNT % MARKETING_EVERY_N_RUNS == 0):
        try:
            msg = build_marketing_post(
                agent_name="DustCleanerBot",
                contract_addr="",
                tokens_sold=sold_symbols
            )
            post_build_log("🧹 Dust Cleaner Update", msg)
            print("Marketing post sent ✅")
        except Exception as e:
            print("Marketing skipped:", e)    

    title = "Monad Agent Run: bet + market quote"
    content = (
        f"Wallet: {address}\n"
        f"MON balance: {w3.from_wei(w3.eth.get_balance(address), 'ether')}\n\n"
        f"Winner: {bet.winner} | Stake: {bet.stake}\n"
        f"Question: {bet.question}\n\n"
        f"TEST/USDC fair: {fair_price}\n"
        f"BUY: {mm.quote_buy(fair_price)} | SELL: {mm.quote_sell(fair_price)}\n"
    )

    if did_sell and POST_TO_MOLTBOOK:
        try:
            post_build_log(title, content)
            print("Posted to Moltbook ✅")
        except Exception as e:
            print("Moltbook post skipped:", e)
    else:
        print("Moltbook post skipped (no sell or disabled)")

    # --- Moltbook: marketing post (safe) ---
    if sold_symbols and POST_TO_MOLTBOOK:
        try:
            post_marketing_update(sold_symbols)
        except Exception as e:
            print("Moltbook marketing skipped:", e)

    # --- Moltbook: keyword-based replies (safe) ---
    if POST_TO_MOLTBOOK:
        try:
            reply_if_needed()
        except Exception as e:
            print("Moltbook reply skipped:", e)

        try:
            reply_to_dms()
        except Exception as e:
            print("Moltbook DM reply skipped:", e)

    # --- Moltbook: template autopost + autoreply (safe) ---
    # IMPORTANT: only call maybe_post_update ONCE (it can sleep for rate limits)
    if POST_TO_MOLTBOOK:
        try:
            maybe_post_update(client)

            new_comments = fetch_new_comments(limit=20)
            if new_comments:
                maybe_reply_to_comments(client, new_comments)

        except Exception as e:
            print("[promotion] skipped:", e)
    # --- end Moltbook ---
    
    print("\n=== AGENT FINISHED ===")
    
if __name__ == "__main__":
    while True:
        print("[worker] tick — agent loop running")
        run_agent_once()
        time.sleep(60)
       
        # --- Stage 2: public dust scan (wallet from .env) ---
        try:
            report = scan_wallet_dust(address)
            dust = report.get("dust", [])
            print("\n--- Stage 2 Public Dust Scan ---")
            print("source:", report.get("source"))
            print("wallet:", report.get("wallet"))
            print("dust_count:", len(dust))

            for d in dust:
                print(
                    f"- {d.get('symbol')} "
                    f"amount={d.get('amount')} "
                    f"mon_value={d.get('mon_value')} "
                    f"{d.get('contract')}"
                )

        except Exception as e:
            print("[stage2] error:", e)
        # --- end Stage 2 ---

        run_agent_once()
        time.sleep(60)
