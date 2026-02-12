import os
import time
from typing import Dict, Any, List

from dotenv import load_dotenv
from web3 import Web3

from erc20_abi import ERC20_ABI
from token_discovery import discover_token_contracts_incremental
from liquidity_checker import can_swap_simulation
from stage2_public_clean import _quote_token_to_mon  # reuse your working quote helper
from swap_executor import execute_safe_swap


def _to_checksum(addr: str) -> str:
    return Web3.to_checksum_address(addr)


def _read_balance_and_decimals(w3: Web3, token: str, wallet: str):
    c = w3.eth.contract(address=_to_checksum(token), abi=ERC20_ABI)
    bal = c.functions.balanceOf(_to_checksum(wallet)).call()
    dec = c.functions.decimals().call()
    return int(bal), int(dec)


def _read_symbol(w3: Web3, token: str) -> str:
    try:
        c = w3.eth.contract(address=_to_checksum(token), abi=ERC20_ABI)
        return str(c.functions.symbol().call()).upper()
    except Exception:
        return "TOKEN"


def scan_wallet_dust(w3: Web3, wallet: str) -> Dict[str, Any]:
    """
    Production Stage2:
    - Discover tokens via Transfer(to=wallet) logs (incremental, cached by token_discovery.py)
    - For each token, check balanceOf
    - Quote token -> MON using Lens (must be liquid)
    - Consider dust if mon_value < DUST_THRESHOLD_MON
    """
    report: Dict[str, Any] = {"source": "stage2_engine", "wallet": wallet, "dust": [], "notes": []}

    wallet = _to_checksum(wallet)

    # -------- Settings --------
    threshold_mon = float(os.getenv("DUST_THRESHOLD_MON", "2.0"))  # default small
    max_candidates = int(os.getenv("PUBLIC_MAX_TOKENS", "250"))
    min_swap_mon = float(os.getenv("MIN_SWAP_MON", "0.02"))
    max_swaps_per_run = int(os.getenv("MAX_SWAPS_PER_RUN", "2"))

    report["notes"].append(f"DUST_THRESHOLD_MON={threshold_mon}")
    report["notes"].append(f"MIN_SWAP_MON={min_swap_mon}")
    report["notes"].append(f"PUBLIC_MAX_TOKENS={max_candidates}")

    # -------- Discover tokens (incremental, cached) --------
    try:
        candidates = discover_token_contracts_incremental(
            w3=w3,
            wallet=wallet,
            chunk_size=int(os.getenv("DISCOVERY_CHUNK_SIZE", "2000")),
            max_chunks_per_run=int(os.getenv("DISCOVERY_MAX_CHUNKS", "10")),
        )
    except Exception as e:
        report["notes"].append(f"Discovery failed: {e}")
        candidates = []

    # Keep it bounded per run (prevents RPC spam)
    candidates = list(dict.fromkeys(candidates))[:max_candidates]
    report["notes"].append(f"Candidates={len(candidates)}")

    dust: List[Dict[str, Any]] = []
    for token in candidates:
        try:
            token = _to_checksum(token)

            raw_bal, dec = _read_balance_and_decimals(w3, token, wallet)
            if raw_bal <= 0:
                continue

            sym = _read_symbol(w3, token)
            if sym == "MON":
                continue

            # Must be swappable (liquidity check)
            if not can_swap_simulation(w3, token):
                continue

            # Quote token -> MON (sell direction)
            mon_out_wei = _quote_token_to_mon(w3, token, raw_bal)
            if not mon_out_wei or int(mon_out_wei) <= 0:
                continue

            mon_value = float(w3.from_wei(int(mon_out_wei), "ether"))

            # Enforce minimum meaningful swap (prevents spam swaps)
            if mon_value < min_swap_mon:
                continue

            # Dust decision
            if mon_value >= threshold_mon:
                continue

            amount = raw_bal / (10 ** dec)

            dust.append({
                "symbol": sym,
                "contract": token,
                "amount": float(amount),
                "decimals": dec,
                "raw_balance": int(raw_bal),
                "mon_value": float(mon_value),
            })
        except Exception:
            continue

    report["dust"] = dust
    return report


def run_stage2_cleaning(w3: Web3, account, wallet: str) -> Dict[str, Any]:
    """
    - Scans wallet
    - Executes swaps for dust tokens (bounded by MAX_SWAPS_PER_RUN)
    """
    rep = scan_wallet_dust(w3, wallet)

    swaps_done = 0
    for t in rep.get("dust", []):
        if swaps_done >= int(os.getenv("MAX_SWAPS_PER_RUN", "2")):
            break

        try:
            # execute_safe_swap expects token dict; we provide raw_balance + mon_value
            execute_safe_swap(w3, account, t)
            swaps_done += 1

            # cooldown between swaps
            time.sleep(int(os.getenv("SWAP_COOLDOWN_SEC", "10")))
        except Exception as e:
            rep.setdefault("notes", []).append(f"Swap failed {t.get('symbol')}: {e}")

    rep["swaps_done"] = swaps_done
    return rep


if __name__ == "__main__":
    load_dotenv(dotenv_path=".env", override=True)
    rpc = os.getenv("RPC_URL", "")
    wallet = os.getenv("PUBLIC_WALLET", "")

    if not rpc or not wallet:
        print("Set RPC_URL and PUBLIC_WALLET in .env then run again.")
        raise SystemExit(1)

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    rep = scan_wallet_dust(w3, wallet)

    print("--- Stage 2 Engine Scan ---")
    print("source:", rep["source"])
    print("wallet:", rep["wallet"])
    print("dust_count:", len(rep["dust"]))
    for n in rep.get("notes", []):
        print("note:", n)

    for d in rep["dust"]:
        print(f"- {d['symbol']} amount={d['amount']} mon_value={d['mon_value']} {d['contract']}")

