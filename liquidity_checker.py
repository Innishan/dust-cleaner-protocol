import os
from web3 import Web3
from dotenv import load_dotenv
from lens_abi import LENS_ABI
from erc20_abi import ERC20_ABI

load_dotenv()

LENS = os.getenv("NADFUN_LENS")

def can_swap_simulation(w3, token_in):
    """
    Nad.fun liquidity check:
    Can we SELL token_in -> MON?
    Uses Lens.getAmountOut(token, amountIn, isBuy=False)
    """
    try:
        token_in = Web3.to_checksum_address(token_in)

        # Skip native MON pseudo-address
        if token_in.lower() == "0x0000000000000000000000000000000000000000":
            return False

        lens = w3.eth.contract(address=Web3.to_checksum_address(LENS), abi=LENS_ABI)

        # Probe a tiny amount based on decimals
        erc = w3.eth.contract(address=token_in, abi=ERC20_ABI)
        decimals = erc.functions.decimals().call()

        # Probe = 0.001 token (or 1 unit if decimals < 3)
        amount_in = 10 ** (decimals - 3) if decimals >= 3 else 1

        # SELL => isBuy = False
        router, mon_out = lens.functions.getAmountOut(token_in, amount_in, False).call()
        return int(mon_out) > 0

    except Exception:
        return False

