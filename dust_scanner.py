import json
import os

from blockvision_client import get_wallet_tokens
from web3 import Web3
from erc20_abi import ERC20_ABI
from coingecko_client import (
    get_platform_id_by_chain_id,
    verify_contract_on_platform,
    token_price_usd,
)
from token_discovery import discover_token_contracts_incremental

VERIFY_CACHE_FILE = "verified_contracts.json"

def _load_verified_cache():
    if os.path.exists(VERIFY_CACHE_FILE):
        try:
            with open(VERIFY_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_verified_cache(data):
    with open(VERIFY_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

from blockvision_client import get_wallet_tokens
from coingecko_client import get_platform_id_by_chain_id, verify_contract_on_platform

def scan_dust_verified(w3, wallet, chain_id, dust_threshold_usd):
    """
    Dust detection using wallet token API + cache fallback.
    Rules:
    - verified tokens only
    - USD value < dust_threshold_usd (0.999)
    - MON is never dust
    - stablecoins ARE dust only if < 0.999 (already handled by threshold)
    """

    # Try live API first; if it fails, fall back to cache (blockvision_client already does this)
    resp = get_wallet_tokens(wallet)

    # Support both shapes:
    # 1) {"result":{"data":[...]}}
    # 2) {"data":[...]}
    items = []
    if isinstance(resp, dict):
        if "result" in resp and isinstance(resp["result"], dict):
            items = resp["result"].get("data", []) or []
        else:
            items = resp.get("data", []) or []

    dust = []

    for t in items:
        try:
            symbol = str(t.get("symbol", "")).upper()
            verified = bool(t.get("verified", False))
            scam = bool(t.get("scamFlag", False))

            # Verified only
            if not verified:
                continue
            if scam:
                continue

            # MON is never dust
            if symbol == "MON":
                continue

            usd = float(t.get("usdValue", 0) or 0)
            if usd <= 0:
                continue

            # Dust threshold: includes stablecoins only if < 0.999
            if usd >= dust_threshold_usd:
                continue

            contract = t.get("contractAddress") or t.get("contract")
            if not contract:
                continue

            dust.append({
                "symbol": symbol,
                "contract": contract,
                "amount": t.get("balance"),
                "usd_value": usd,
                "decimals": t.get("decimal", 18),
            })

        except Exception:
            continue

    return dust

def run_stage2_public_dust_scan(wallet: str) -> dict:
    """
    Stage 2 public dust scan for API/UI.
    Source of token candidates: verified_contracts.json (dict keys are addresses).
    Registry optimization:
      - Use registry "symbol" if provided
      - Always fetch decimals from chain (since you want symbol-only registry)
    Read-only: DOES NOT send any transactions.
    """

    import os, json
    from web3 import Web3
    from erc20_abi import ERC20_ABI

    rpc = os.getenv("MONAD_RPC_URL") or os.getenv("RPC_URL")
    if not rpc:
        return {
            "source": "error_missing_rpc",
            "wallet": wallet,
            "dust_count": 0,
            "notes": ["Set MONAD_RPC_URL or RPC_URL in .env"],
            "dust": [],
        }

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        return {
            "source": "error_rpc_not_connected",
            "wallet": wallet,
            "dust_count": 0,
            "notes": [f"Could not connect to RPC: {rpc}"],
            "dust": [],
        }

    # ---- Load registry ----
    notes = []
    registry = {}
    try:
        with open("verified_contracts.json", "r") as f:
            data = json.load(f)

        # Your current format: dict where keys are addresses and values are metadata
        if isinstance(data, dict):
            registry = data
        elif isinstance(data, list):
            # Allow list format too, in case you switch later
            registry = {addr: {} for addr in data if isinstance(addr, str)}
        else:
            registry = {}

    except Exception as e:
        return {
            "source": "error_missing_registry",
            "wallet": wallet,
            "dust_count": 0,
            "notes": [f"Could not load verified_contracts.json: {type(e).__name__}: {e}"],
            "dust": [],
        }

    candidates = [a for a in registry.keys() if isinstance(a, str) and a.startswith("0x") and len(a) == 42]
    candidates.sort()

    max_candidates = int(os.getenv("PUBLIC_SCAN_MAX_CANDIDATES", "200"))
    candidates = candidates[:max_candidates]

    notes.append(f"Public registry candidates: {len(candidates)}")
    if candidates:
        notes.append(f"Candidates sample: {candidates[:3]}")

    wallet_cs = Web3.to_checksum_address(wallet)
    dust = []

    for token in candidates:
        try:
            token_cs = Web3.to_checksum_address(token)
            meta = registry.get(token) or registry.get(token.lower()) or registry.get(token_cs) or {}
            if not isinstance(meta, dict):
                meta = {}

            c = w3.eth.contract(address=token_cs, abi=ERC20_ABI)

            raw_bal = c.functions.balanceOf(wallet_cs).call()
            if raw_bal == 0:
                continue

            # Always fetch decimals from chain (symbol-only registry)
            try:
                dec = c.functions.decimals().call()
            except Exception:
                dec = 18

            # Use registry symbol if available, otherwise fallback to on-chain symbol()
            sym = meta.get("symbol")
            used_registry_symbol = sym is not None

            if sym is None:
                try:
                    sym = c.functions.symbol().call()
                except Exception:
                    sym = "TOKEN"

            try:
                dec_i = int(dec)
            except Exception:
                dec_i = 18

            amount = raw_bal / (10 ** dec_i)

            dust.append({
                "symbol": str(sym),
                "amount": float(amount),
                "mon_value": None,
                "token": token_cs,
            })

            if used_registry_symbol:
                notes.append(f"BALCHECK {token_cs} raw_bal={raw_bal} dec={dec_i} (registry_symbol)")
            else:
                notes.append(f"BALCHECK {token_cs} raw_bal={raw_bal} dec={dec_i} (onchain_symbol)")

        except Exception:
            # Skip tokens that break / are non-ERC20
            continue

    return {
        "source": "public_registry_balanceof_fallback",
        "wallet": wallet,
        "dust_count": len(dust),
        "notes": notes,
        "dust": dust,
    }

