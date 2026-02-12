import json
import os
from typing import List, Set

from monadscan_discovery import discover_token_contracts_monadscan
from dotenv import load_dotenv
from web3 import Web3

from token_discovery import discover_token_contracts_incremental

REGISTRY_FILE = "public_registry.json"


def _load_registry() -> Set[str]:
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return set([x for x in data if isinstance(x, str) and x.startswith("0x")])
        except Exception:
            pass
    return set()


def _save_registry(addrs: Set[str]) -> None:
    arr = sorted(list(addrs))
    with open(REGISTRY_FILE, "w") as f:
        json.dump(arr, f, indent=2)
    print(f"Saved {len(arr)} tokens to {REGISTRY_FILE}")


def build_universe(seed_wallets: List[str]) -> None:
    load_dotenv(".env", override=True)
    rpc = os.getenv("RPC_URL", "https://rpc.monad.xyz")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))

    if not w3.is_connected():
        raise RuntimeError("RPC not connected. Check RPC_URL in .env")

    registry = _load_registry()
    print("Starting registry size:", len(registry))

    discovered_all: Set[str] = set()

    for wallet in seed_wallets:
        wallet = Web3.to_checksum_address(wallet)
        print("\nScanning wallet:", wallet)

        # ✅ Scan MUCH deeper than before
        candidates = discover_token_contracts_monadscan(wallet, max_pages=10, page_size=200)
        print("Found", len(candidates), "candidates")
        for c in candidates:
            if isinstance(c, str) and c.startswith("0x"):
                discovered_all.add(Web3.to_checksum_address(c))

    print("\nTotal discovered:", len(discovered_all))

    # Add to registry
    before = len(registry)
    registry |= discovered_all
    added = len(registry) - before

    print("Added after filtering:", added)
    _save_registry(registry)


if __name__ == "__main__":
    load_dotenv(".env", override=True)

    # ✅ Put your seed wallets here (you can add more later)
    seeds = [
        os.getenv("PUBLIC_WALLET", ""),  # your agent wallet from .env
    ]
    seeds = [s for s in seeds if s and s.startswith("0x")]

    if not seeds:
        raise RuntimeError("Set PUBLIC_WALLET in .env first")

    build_universe(seeds)

