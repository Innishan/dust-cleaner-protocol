import os
import time
from typing import Optional

from fastapi.responses import JSONResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from web3 import Web3

from erc20_abi import ERC20_ABI
from nadfun_router_abi import NADFUN_ROUTER_ABI
from lens_abi import LENS_ABI

load_dotenv()

app = FastAPI(title="Dust Cleaner Protocol API")

# ---------- CORS ----------
cors_origins = os.getenv("CORS_ORIGINS", "")
allowed = [o.strip() for o in cors_origins.split(",") if o.strip()]

# fallback defaults (works if env var not set)
if not allowed:
    allowed = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://dust-cleaner-protocol.vercel.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------- Models ----------
class AnalyzeReq(BaseModel):
    wallet: str

class PrepareSellReq(BaseModel):
    wallet: str
    token: str  # token contract address

# ---------- Helpers ----------
DEADLINE_SECONDS = int(os.getenv("SELL_DEADLINE_SECONDS", "300"))  # 5 minutes

def _get_rpc_url() -> Optional[str]:
    # you already had both keys in .env earlier
    return os.getenv("RPC_URL") or os.getenv("MONAD_RPC_URL")

def _get_router_address() -> Optional[str]:
    # You MUST set this in Render + local .env
    # NADFUN_ROUTER_ADDRESS=0x....
    return os.getenv("NADFUN_ROUTER_ADDRESS")

def _w3():
    rpc = _get_rpc_url()
    if not rpc:
        return None, "error_missing_rpc"
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        return None, "error_rpc_not_connected"
    return w3, None

def prepare_sell_calldata_via_lens(wallet: str, token: str):
    """
    Returns calldata for:
      1) ERC20 approve(router, amount_in)
      2) router.sell((amount_in, min_out, token, wallet, deadline))
    Uses NADFUN_LENS to get router + quote.
    """
    import time
    from web3 import Web3

    w3, err = _w3()
    if err or w3 is None:
        return {
            "source": err or "error_unknown",
            "wallet": wallet,
            "token": token,
            "notes": ["RPC not available"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    lens_addr = os.getenv("NADFUN_LENS")
    if not lens_addr:
        return {
            "source": "error_missing_lens",
            "wallet": wallet,
            "token": token,
            "notes": ["NADFUN_LENS is not set in .env / Render env vars"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    # config
    slippage_bps = int(os.getenv("SLIPPAGE_BPS", "200"))  # 2%
    deadline_seconds = int(os.getenv("SELL_DEADLINE_SECONDS", "300"))  # 5 min

    wallet_cs = Web3.to_checksum_address(wallet)
    token_cs = Web3.to_checksum_address(token)
    lens_cs = Web3.to_checksum_address(lens_addr)

    # ABIs from your repo
    from lens_abi import LENS_ABI
    from erc20_abi import ERC20_ABI
    from nadfun_router_abi import NADFUN_ROUTER_ABI

    lens = w3.eth.contract(address=lens_cs, abi=LENS_ABI)
    erc = w3.eth.contract(address=token_cs, abi=ERC20_ABI)

    # token metadata
    try:
        decimals = int(erc.functions.decimals().call())
    except Exception:
        decimals = 18

    try:
        symbol = erc.functions.symbol().call()
    except Exception:
        symbol = "UNKNOWN"

    # balance
    bal = int(erc.functions.balanceOf(wallet_cs).call())
    if bal <= 0:
        return {
            "source": "prepare_sell_no_balance",
            "wallet": wallet,
            "token": token,
            "symbol": symbol,
            "decimals": decimals,
            "amount_raw": str(bal),
            "amount_display": 0,
            "notes": ["No balance found for token in this wallet"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    # quote SELL token -> MON (isBuy=False)
    router_addr, mon_out = lens.functions.getAmountOut(token_cs, bal, False).call()
    router_cs = Web3.to_checksum_address(router_addr)
    mon_out = int(mon_out)

    min_out = mon_out * (10_000 - slippage_bps) // 10_000
    deadline = int(time.time()) + deadline_seconds

    # calldata approve + sell
    approve_data = erc.functions.approve(router_cs, bal)._encode_transaction_data()

    router = w3.eth.contract(address=router_cs, abi=NADFUN_ROUTER_ABI)
    params = (bal, min_out, token_cs, wallet_cs, deadline)
    sell_data = router.functions.sell(params)._encode_transaction_data()

    return {
        "source": "prepare_sell_calldata_via_lens",
        "wallet": wallet,
        "token": token,
        "symbol": symbol,
        "decimals": decimals,
        "amount_raw": str(bal),
        "amount_display": float(bal) / (10 ** decimals),
        "router": router_cs,
        "quote_mon_out_raw": str(mon_out),
        "min_out_raw": str(min_out),
        "approve": {"to": token_cs, "data": approve_data, "value": "0x0"},
        "sell": {"to": router_cs, "data": sell_data, "value": "0x0"},
        "notes": [],
    }

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze")
def analyze(req: AnalyzeReq):
    """
    Calls your existing dust scan logic and returns JSON.
    """
    from dust_scanner import run_stage2_public_dust_scan
    report = run_stage2_public_dust_scan(req.wallet)
    return report

@app.post("/prepare-sell")
def prepare_sell(req: PrepareSellReq):
    try:
        # your existing logic that builds approve + sell calldata
        out = prepare_sell_calldata_via_lens(req.wallet, req.token)  # <- keep your real function name
        return out

    except Exception as e:
        # IMPORTANT: return JSON instead of crashing (no 500)
        return JSONResponse(
            status_code=200,
            content={
                "source": "error_prepare_sell",
                "wallet": req.wallet,
                "token": req.token,
                "notes": [str(e)],
                "approve": {"to": req.token, "data": "0x", "value": "0x0"},
                "sell": {"to": "", "data": "0x", "value": "0x0"},
            },
        )

    lens_addr = os.getenv("NADFUN_LENS")
    if not lens_addr:
        return {
            "source": "error_missing_lens",
            "wallet": req.wallet,
            "token": req.token,
            "notes": ["NADFUN_LENS is not set in .env / Render env vars"],
            "approve": {"to": req.token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "200"))  # 2%
    SWAP_FRACTION = float(os.getenv("SWAP_FRACTION", "1.0"))  # 1.0 = sell full balance
    deadline = int(time.time()) + DEADLINE_SECONDS

    wallet = Web3.to_checksum_address(req.wallet)
    token = Web3.to_checksum_address(req.token)
    lens = w3.eth.contract(address=Web3.to_checksum_address(lens_addr), abi=LENS_ABI)

    erc = w3.eth.contract(address=token, abi=ERC20_ABI)

    notes = []

    # display fields (best effort)
    try:
        symbol = erc.functions.symbol().call()
        if isinstance(symbol, bytes):
            symbol = symbol.decode("utf-8", errors="ignore")
    except Exception:
        symbol = "TOKEN"
        notes.append("symbol() failed, using TOKEN")

    try:
        decimals = int(erc.functions.decimals().call())
    except Exception:
        decimals = 18
        notes.append("decimals() failed, default 18")

    # amount_in = balance * fraction
    bal = int(erc.functions.balanceOf(wallet).call())
    if bal <= 0:
        return {
            "source": "error_zero_balance",
            "wallet": wallet,
            "token": token,
            "symbol": symbol,
            "decimals": decimals,
            "amount_raw": "0",
            "amount_display": 0.0,
            "notes": ["Token balance is 0"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    amount_in = int(bal * SWAP_FRACTION)
    if amount_in > bal:
        amount_in = bal
    if amount_in <= 0:
        return {
            "source": "error_zero_amount_in",
            "wallet": wallet,
            "token": token,
            "symbol": symbol,
            "decimals": decimals,
            "amount_raw": str(bal),
            "amount_display": float(bal / (10 ** decimals)),
            "notes": ["Computed amount_in is 0"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    # Quote: token -> MON (isBuy=False)
    router_addr, mon_out = lens.functions.getAmountOut(token, amount_in, False).call()
    mon_out = int(mon_out)

    if mon_out <= 0:
        return {
            "source": "error_no_mon_output",
            "wallet": wallet,
            "token": token,
            "symbol": symbol,
            "decimals": decimals,
            "amount_raw": str(amount_in),
            "amount_display": float(amount_in / (10 ** decimals)),
            "notes": ["No MON output from quote"],
            "approve": {"to": token, "data": "0x", "value": "0x0"},
            "sell": {"to": "", "data": "0x", "value": "0x0"},
        }

    amount_out_min = mon_out * (10_000 - SLIPPAGE_BPS) // 10_000

    router = Web3.to_checksum_address(router_addr)
    router_c = w3.eth.contract(address=router, abi=NADFUN_ROUTER_ABI)

    # Build calldata (no signing) — compatible with older Web3.py
    approve_data = erc.functions.approve(router, amount_in)._encode_transaction_data()
    params = (amount_in, amount_out_min, token, wallet, deadline)
    sell_data = router_c.functions.sell(params)._encode_transaction_data()
    
    amount_display = amount_in / (10 ** decimals) if decimals else float(amount_in)

    return {
        "source": "prepare_sell_calldata_via_lens",
        "wallet": wallet,
        "token": token,
        "symbol": symbol,
        "decimals": decimals,
        "amount_raw": str(amount_in),
        "amount_display": float(amount_display),
        "router": router,
        "quote_mon_out_raw": str(mon_out),
        "min_out_raw": str(amount_out_min),
        "approve": {"to": token, "data": approve_data, "value": "0x0"},
        "sell": {"to": router, "data": sell_data, "value": "0x0"},
        "notes": notes,
    }
