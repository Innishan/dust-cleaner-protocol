import os
import json
from typing import List, Dict, Any, Tuple

from web3 import Web3
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

from erc20_abi import ERC20_ABI
from lens_abi import LENS_ABI

# -----------------------
# Helpers
# -----------------------

def _to_checksum(w3: Web3, addr: str) -> str:
    return Web3.to_checksum_address(addr)

def _read_erc20_balance(w3: Web3, token: str, wallet: str) -> Tuple[int, int]:
    c = w3.eth.contract(address=_to_checksum(w3, token), abi=ERC20_ABI)
    bal = c.functions.balanceOf(_to_checksum(w3, wallet)).call()
    dec = c.functions.decimals().call()
    return int(bal), int(dec)

def _read_symbol(w3: Web3, token: str) -> str:
    try:
        c = w3.eth.contract(address=_to_checksum(w3, token), abi=ERC20_ABI)
        return str(c.functions.symbol().call()).upper()
    except Exception:
        return "TOKEN"

def _quote_token_to_mon(w3: Web3, token: str, amount_in: int) -> int:
    """
    Quotes token -> MON (wei) using Nad.fun Lens getAmountOut(token, amountIn, isBuy).
    IMPORTANT: token->MON is isBuy=False.
    """
    try:
        lens_addr = os.getenv("NADFUN_LENS", "").strip()
        if not lens_addr:
            return 0

        lens = w3.eth.contract(address=_to_checksum(w3, lens_addr), abi=LENS_ABI)
        token_cs = _to_checksum(w3, token)
        amount_in = int(amount_in)

        _router, out_wei = lens.functions.getAmountOut(token_cs, amount_in, False).call()
        return int(out_wei) if out_wei else 0
    except Exception:
        return 0

def _load_candidates() -> List[str]:
    """
    Candidate token contracts:
    1) PUBLIC_TOKEN_REGISTRY_FILE (json array of addresses)
    2) PUBLIC_TOKEN_INCLUDE (comma-separated addresses) optional
    """
    candidates: List[str] = []

    reg_file = os.getenv("PUBLIC_TOKEN_REGISTRY_FILE", "public_tokens.json").strip()
    if reg_file and os.path.exists(reg_file):
        try:
            with open(reg_file, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    candidates.extend([str(x) for x in data])
        except Exception:
            pass

    manual = os.getenv("PUBLIC_TOKEN_INCLUDE", "").strip()
    if manual:
        parts = [p.strip() for p in manual.split(",") if p.strip()]
        candidates.extend(parts)

    # de-dupe
    seen = set()
    out = []
    for a in candidates:
        low = a.lower()
        if low not in seen and low.startswith("0x") and len(low) == 42:
            seen.add(low)
            out.append(a)
    return out

# -----------------------
# Main scan
# -----------------------

def scan_wallet_dust(wallet: str) -> Dict[str, Any]:
    """
    Returns a report:
    - dust: list of tokens where mon_value < DUST_THRESHOLD_MON
    - notes: helpful debug info
    """

    rpc = os.getenv("RPC_URL", "https://rpc.monad.xyz")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))

    report: Dict[str, Any] = {
        "source": "public_registry_balanceof_quote",
        "wallet": wallet,
        "rpc": rpc,
        "dust": [],
        "notes": [],
    }

    if not w3.is_connected():
        report["notes"].append("RPC not connected")
        return report

    candidates = _load_candidates()
    report["notes"].append(f"Candidates: {len(candidates)}")

    threshold_mon = float(os.getenv("DUST_THRESHOLD_MON", "0.1"))
    report["notes"].append(f"DUST_THRESHOLD_MON={threshold_mon}")

    dust: List[Dict[str, Any]] = []

    for addr in candidates:
        try:
            raw_bal, dec = _read_erc20_balance(w3, addr, wallet)
            if raw_bal <= 0:
                continue

            amount = raw_bal / (10 ** dec)
            sym = _read_symbol(w3, addr)

            # never treat MON as token
            if sym == "MON":
                continue

            out_wei = _quote_token_to_mon(w3, addr, raw_bal)
            if out_wei <= 0:
                continue

            mon_value = float(w3.from_wei(out_wei, "ether"))

            if mon_value >= threshold_mon:
                continue

            dust.append({
                "symbol": sym,
                "contract": addr,
                "amount": amount,
                "mon_value": mon_value,
                "raw_balance": str(raw_bal),
                "decimals": dec,
            })
        except Exception:
            continue

    report["dust"] = dust
    report["dust_count"] = len(dust)
    if not dust:
        report["notes"].append("No dust found for given threshold.")
    return report

if __name__ == "__main__":
    wallet = os.getenv("PUBLIC_WALLET", "").strip()
    if not wallet:
        print("Set PUBLIC_WALLET in .env (or export it) then run again.")
        raise SystemExit(1)

    rep = scan_wallet_dust(wallet)
    print("source:", rep["source"])
    print("wallet:", rep["wallet"])
    print("dust_count:", rep.get("dust_count", 0))
    print("notes:", rep["notes"])
    for d in rep["dust"]:
        print(f"- {d['symbol']} amount={d['amount']} mon_value={d['mon_value']} {d['contract']}")

