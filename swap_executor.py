import os
import time
from web3 import Web3
from dotenv import load_dotenv
from lens_abi import LENS_ABI
from erc20_abi import ERC20_ABI
from nadfun_router_abi import NADFUN_ROUTER_ABI

import json

SELL_STATE_FILE = "sell_state.json"
SELL_COOLDOWN = int(os.getenv("SELL_COOLDOWN_SECONDS", 600))

load_dotenv()

LENS = os.getenv("NADFUN_LENS")
SAFE_MODE = os.getenv("SAFE_MODE", "true").lower() == "true"
SWAP_FRACTION = float(os.getenv("SWAP_FRACTION", 0.10))
MIN_SWAP_USD = float(os.getenv("MIN_SWAP_USD", 0.01))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", 300))  # 300 = 3%


def execute_safe_swap(w3, account, token):
    """
    Sell dust token -> MON using Nad.fun Lens to choose router.
    SAFE_MODE=True: preview only (NO TX).
    SAFE_MODE=False: sends approve + sell TX.
    """
    now = int(time.time())

    # Always define symbol early (so cooldown prints work)
    symbol = token.get("symbol", "?")

    # Load sell state
    try:
        with open(SELL_STATE_FILE, "r") as f:
            sell_state = json.load(f)
    except Exception:
        sell_state = {}

    last_sold = sell_state.get(token["contract"], 0)
    if now - last_sold < SELL_COOLDOWN:
        print(f"Skipping {symbol} — cooldown active")
        return

    try:
        # --- Stage 2 support: prefer MON-based value + raw balance ---
        raw_bal = token.get("raw_balance", None)
        mon_value = token.get("mon_value", None)

        if raw_bal is not None and mon_value is not None:
            # Minimum swap guard (prevents spam swaps)
            MIN_SWAP_MON = float(os.getenv("MIN_SWAP_MON", "0.02"))
            mon_value = float(mon_value)

            if mon_value < MIN_SWAP_MON:
                print(f"Skipping {symbol} — too small ({mon_value:.6f} MON)")
                return

            # amount_in MUST be raw balance (base units)
            amount_in = int(raw_bal)

        else:
            # --- Legacy USD-based fallback ---
            MIN_SWAP_USD = float(os.getenv("MIN_SWAP_USD", "0.10"))
            usd_value = float(token.get("usd_value", 0) or 0)

            if usd_value < MIN_SWAP_USD:
                print(f"Skipping {symbol} — too small (${usd_value})")
                return

            decimals = int(token.get("decimals", 18))
            amount = float(token.get("amount", 0) or 0)
            amount_in = int(amount * (10 ** decimals))

        if amount_in <= 0:
            print(f"Skipping {symbol} — zero balance")
            return

        token_ca = Web3.to_checksum_address(token["contract"])

        # Skip native MON pseudo-address
        if token_ca.lower() == "0x0000000000000000000000000000000000000000":
            return

        # Build contracts
        lens = w3.eth.contract(address=Web3.to_checksum_address(LENS), abi=LENS_ABI)
        erc = w3.eth.contract(address=token_ca, abi=ERC20_ABI)
        # If Stage2 gave us raw_balance, keep it. Otherwise calculate from balance/decimals.
        if amount_in <= 0:
            bal = erc.functions.balanceOf(account.address).call()
            amount_in = int(bal)

        current_balance = erc.functions.balanceOf(account.address).call()
        amount_in = int(current_balance * SWAP_FRACTION)

        # Safety cap: never exceed current balance
        if amount_in > current_balance:
            amount_in = current_balance

        if amount_in <= 0:
            print(f"Skipping {symbol} — zero amount")
            return

        # Quote SELL token -> MON (isBuy=False)
        router_addr, mon_out = lens.functions.getAmountOut(token_ca, amount_in, False).call()
        mon_out = int(mon_out)

        if mon_out <= 0:
            print(f"Skipping {symbol} — no MON output")
            return

        amount_out_min = mon_out * (10_000 - SLIPPAGE_BPS) // 10_000
        deadline = int(time.time()) + 300  # 5 minutes

        if SAFE_MODE:
            print(f"SAFE MODE: would SELL {symbol} -> MON | amount_in={amount_in} | expected MON out={mon_out} | min_out={amount_out_min}")
            return

        # ---------- REAL TX MODE ----------
        router = w3.eth.contract(address=Web3.to_checksum_address(router_addr), abi=NADFUN_ROUTER_ABI)

        # 1) Approve if needed
        allowance = erc.functions.allowance(account.address, router.address).call()
        nonce = w3.eth.get_transaction_count(account.address)

        if allowance < amount_in:
            approve_tx = erc.functions.approve(router.address, amount_in).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gasPrice": w3.eth.gas_price,
            })
            # estimate gas
            approve_tx["gas"] = w3.eth.estimate_gas(approve_tx)

            signed = account.sign_transaction(approve_tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"Approve sent for {symbol}: {tx_hash.hex()}")

            w3.eth.wait_for_transaction_receipt(tx_hash)
            nonce += 1

        # 2) Sell
        params = (amount_in, amount_out_min, token_ca, account.address, deadline)

        sell_tx = router.functions.sell(params).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gasPrice": w3.eth.gas_price,
        })
        sell_tx["gas"] = w3.eth.estimate_gas(sell_tx)

        signed2 = account.sign_transaction(sell_tx)
        sell_hash = w3.eth.send_raw_transaction(signed2.raw_transaction)
        print(f"SELL sent for {symbol}: {sell_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(sell_hash)
        print(f"SELL confirmed for {symbol}. block={receipt.blockNumber}")
        return True
        sell_state[token["contract"]] = now
        with open(SELL_STATE_FILE, "w") as f:
            json.dump(sell_state, f, indent=2)


    except Exception as e:
        print(f"Sell failed for {token.get('symbol','?')}: {e}")
        return False

