
import os
import json
from coingecko_client import get_platform_id_by_chain_id, token_price_usd
from dotenv import load_dotenv
from web3 import Web3
from dust_scanner import scan_dust_verified
from token_discovery import discover_token_contracts_incremental
from tokens import TOKENS  # your known token list (symbol -> contract or list)
from erc20_abi import ERC20_ABI
from lens_abi import LENS_ABI
from liquidity_checker import can_swap_simulation

load_dotenv()

PUBLIC_REGISTRY_FILE = "public_token_registry.json"

def _get_lens_address() -> str:
    """
    Returns Nad.fun Lens contract address from env.
    We reuse the same env key your swap code already uses.
    """
    # Common names people use; keep it flexible
    for key in ("NADFUN_LENS", "NADFUN_LENS_ADDRESS", "LENS_ADDRESS"):
        v = os.getenv(key, "").strip()
        if v:
            return v
    raise RuntimeError("Missing Nad.fun Lens address in .env (set NADFUN_LENS=0x...)")

def _quote_token_to_mon(w3: Web3, token: str, amount_in: int) -> int:
    """
    Quotes token -> MON using Nad.fun Lens getAmountOut(token, amountIn, isBuy).
    IMPORTANT: token->MON is isBuy=False (as verified by manual test).
    Returns amountOut in wei (MON wei). 0 means no quote.
    """
    try:
        lens_addr = os.getenv("NADFUN_LENS", "").strip()
        if not lens_addr:
            return 0

        lens = w3.eth.contract(
            address=Web3.to_checksum_address(lens_addr),
            abi=LENS_ABI,
        )

        token_cs = Web3.to_checksum_address(token)
        amount_in = int(amount_in)

        # Verified correct direction:
        router, out_wei = lens.functions.getAmountOut(token_cs, amount_in, False).call()

        # out_wei is MON wei
        out_wei = int(out_wei) if out_wei else 0
        return out_wei
    except Exception:
        return 0

def _load_public_registry() -> list[str]:
    if not os.path.exists(PUBLIC_REGISTRY_FILE):
        return []
    try:
        with open(PUBLIC_REGISTRY_FILE, "r") as f:
            data = json.load(f)
        tokens = data.get("tokens", [])
        if isinstance(tokens, list):
            return [t for t in tokens if isinstance(t, str) and t.startswith("0x")]
    except Exception:
        pass
    return []

def add_token_to_public_registry(token_addr: str) -> bool:
    """
    Adds token contract to public registry file so fallback can find balances
    WITHOUT get_logs and WITHOUT BlockVision.
    """
    token_addr = token_addr.strip()
    if not token_addr.startswith("0x"):
        return False

    data = {"chain_id": 143, "tokens": []}
    if os.path.exists(PUBLIC_REGISTRY_FILE):
        try:
            with open(PUBLIC_REGISTRY_FILE, "r") as f:
                data = json.load(f) or data
        except Exception:
            pass

    tokens = data.get("tokens", [])
    if not isinstance(tokens, list):
        tokens = []
    if token_addr not in tokens:
        tokens.append(token_addr)

    data["tokens"] = tokens
    with open(PUBLIC_REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return True


def _to_checksum(w3: Web3, addr: str) -> str:
    return w3.to_checksum_address(addr)

def _as_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _as_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _read_erc20_balance(w3: Web3, token_addr: str, wallet: str) -> tuple[int, int]:
    """
    Returns (raw_balance, decimals)
    """
    c = w3.eth.contract(address=_to_checksum(w3, token_addr), abi=ERC20_ABI)
    bal = c.functions.balanceOf(_to_checksum(w3, wallet)).call()
    dec = c.functions.decimals().call()
    return int(bal), int(dec)

def analyze_wallet_dust_public(w3: Web3, wallet: str, chain_id: int, dust_threshold_usd: float) -> dict:
    """
    Stage 2 public mode:
    - Read-only dust analysis for ANY wallet
    - Never swaps
    - Uses BlockVision/cache first
    - Falls back to on-chain balanceOf checks for known TOKENS if needed
    """
    wallet = _to_checksum(w3, wallet)

    report = {
        "wallet": wallet,
        "chain_id": chain_id,
        "threshold_usd": dust_threshold_usd,
        "source": None,
        "dust": [],
        "notes": [],
    }
    platform_id = None
    try:
        platform_id = get_platform_id_by_chain_id(chain_id)
    except Exception:
        platform_id = None

    # 1) Primary: BlockVision + cache (your existing pipeline)
    try:
        dust = scan_dust_verified(w3, wallet, chain_id, dust_threshold_usd)
        if dust:
            report["source"] = "blockvision_or_cache"
            report["dust"] = dust
            return report
    except Exception as e:
        report["notes"].append(f"BlockVision/cache failed: {e}")

    # 2) Fallback: discover token contracts → then on-chain balanceOf (reliable, slower)
    fallback_dust = []

    # How many token contracts to try in public mode
    max_tokens = _as_int(os.getenv("PUBLIC_MAX_TOKENS", "200"), 200)

    # 2) Fallback: public registry token list (no get_logs, no indexer)
    candidates = _load_public_registry()
    report["notes"].append(f"Public registry candidates: {len(candidates)}")
    # DEBUG: show the actual candidate addresses
    report["notes"].append(f"Candidates sample: {candidates[:5]}")

    max_tokens = _as_int(os.getenv("PUBLIC_MAX_TOKENS", "200"), 200)
    candidates = candidates[:max_tokens]

    # If discovery fails, fall back to static TOKENS list (your project currently has only 2)
    if not candidates:
        token_items = []
        if isinstance(TOKENS, dict):
            token_items = list(TOKENS.items())
        elif isinstance(TOKENS, list):
            for t in TOKENS:
                sym = t.get("symbol") or t.get("name") or "TOKEN"
                addr = t.get("address") or t.get("contract")
                if addr:
                    token_items.append((sym, addr))
        candidates = [addr for _, addr in token_items][:max_tokens]
        report["notes"].append(f"Using static TOKENS fallback: {len(candidates)} candidates")

    checked = 0
    for addr in candidates:
        try:
            raw_bal, dec = _read_erc20_balance(w3, addr, wallet)

            # DEBUG: show balance reads
            report["notes"].append(f"BALCHECK {addr} raw_bal={raw_bal} dec={dec}")

            if raw_bal <= 0:
                continue

            # -------------------------
            # Pricing + dust evaluation
            # -------------------------
            
            amount = raw_bal / (10 ** dec)

            mon_value = None
            if os.getenv("PUBLIC_PRICE_MODE", "none").lower() == "quote_mon":
                try:
                    if can_swap_simulation(w3, addr):
                        mon_out_wei = _quote_token_to_mon(w3, addr, raw_bal)

                        # Fallback: quote smaller sample if full balance returns 0
                        if not mon_out_wei or mon_out_wei == 0:
                            sample_raw = 10 ** int(dec)
                            if raw_bal < sample_raw:
                                sample_raw = raw_bal

                            sample_out = _quote_token_to_mon(w3, addr, sample_raw)
                            if sample_out and sample_out > 0 and sample_raw > 0:
                                mon_out_wei = int((sample_out * raw_bal) / sample_raw)

                        if mon_out_wei and mon_out_wei > 0:
                            mon_value = float(w3.from_wei(mon_out_wei, "ether"))
                except Exception:
                    mon_value = None

            # Read token symbol
            sym = "TOKEN"
            try:
                c = w3.eth.contract(address=_to_checksum(w3, addr), abi=ERC20_ABI)
                sym = str(c.functions.symbol().call()).upper()
            except Exception:
                pass

            # Skip native MON
            if sym == "MON":
                continue

            threshold_mon = float(os.getenv("DUST_THRESHOLD_MON", "0.1"))

            # --- NEW: allow stablecoins even if Nad.fun can't quote them ---
            STABLES = {"USDC", "USDT", "USDT0", "AUSD", "DAI", "USD1"}
            stable_usd_threshold = float(os.getenv("DUST_THRESHOLD_USD_STABLE", "2.0"))

            # Optional: stable token address allowlist (most reliable)
            stable_addrs = set()
            env_addrs = os.getenv("STABLE_TOKEN_ADDRESSES", "")
            for x in env_addrs.split(","):
                x = x.strip()
                if x.startswith("0x"):
                    stable_addrs.add(x.lower())

            if mon_value is None:
                looks_like_stable = (sym in STABLES) or (addr.lower() in stable_addrs) or (dec == 6)

                if looks_like_stable and amount > 0 and amount < stable_usd_threshold:
                    fallback_dust.append({
                        "symbol": sym,
                        "contract": addr,
                        "token": addr,
                        "amount": amount,
                        "mon_value": None,
                        "decimals": dec,
                        "raw_balance": str(raw_bal),
                        "usd_value": float(amount),
                        "notes": ["stablecoin_included_without_mon_quote"],
                    })
                else:
                    report["notes"].append(f"No MON quote for {sym} ({addr}) amount={amount}")
                continue

            # Not dust if >= MON threshold (for Nad.fun priced tokens)
            if mon_value >= threshold_mon:
                continue

            # Not dust if >= threshold
            if mon_value >= threshold_mon:
                continue

            fallback_dust.append({
                "symbol": sym,
                "contract": addr,
                "token": addr,
                "amount": amount,
                "mon_value": mon_value,
                "decimals": dec,
                "raw_balance": str(raw_bal),
            })

        except Exception:
            continue

    report["source"] = "public_registry_balanceof_fallback"
    report["dust"] = fallback_dust

    if not fallback_dust:
        report["notes"].append("No dust found via discovery+balanceOf fallback.")
    return report

