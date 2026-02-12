import os
import json
from typing import Set
from dotenv import load_dotenv
from web3 import Web3

from token_discovery import discover_token_contracts_incremental
from stage2_public_clean import _quote_token_to_mon
from liquidity_checker import can_swap_simulation

REG_PATH = "public_registry.json"


def load_registry() -> Set[str]:
    if os.path.exists(REG_PATH):
        try:
            data = json.load(open(REG_PATH))
            return set(data)
        except Exception:
            return set()
    return set()


def save_registry(tokens: Set[str]):
    json.dump(sorted(tokens), open(REG_PATH, "w"), indent=2)
    print("Saved", len(tokens), "tokens to", REG_PATH)


def main():
    load_dotenv(dotenv_path=".env", override=True)

    rpc = os.getenv("RPC_URL")
    if not rpc:
        raise RuntimeError("RPC_URL missing in .env")

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        raise RuntimeError("RPC not connected")

    seed_wallets = os.getenv("SEED_WALLETS", "").strip()
    if not seed_wallets:
        raise RuntimeError("Set SEED_WALLETS in .env")

    wallets = [w.strip() for w in seed_wallets.split(",") if w.strip()]
    registry = load_registry()

    print("Starting registry size:", len(registry))

    discovered = set()

    for wallet in wallets:
        wallet = Web3.to_checksum_address(wallet)
        print("Scanning wallet:", wallet)

        try:
            candidates = discover_token_contracts_incremental(
                w3,
                wallet,
                chunk_size=int(os.getenv("DISCOVERY_CHUNK_SIZE", "4000")),
                max_chunks_per_run=int(os.getenv("DISCOVERY_MAX_CHUNKS", "25")),
            )
        except Exception as e:
            print("Discovery error:", e)
            continue

        print("Found", len(candidates), "candidates")

        for ca in candidates:
            try:
                ca = Web3.to_checksum_address(ca)
                discovered.add(ca)
            except Exception:
                continue

    print("Total discovered:", len(discovered))

    added = 0

    for token in discovered:
        if token in registry:
            continue

        try:
            if not can_swap_simulation(w3, token):
                continue

            # test small quote (1e15 wei probe)
            test_amount = 1000000000000000
            out = _quote_token_to_mon(w3, token, test_amount)

            if not out or int(out) <= 0:
                continue

            registry.add(token)
            added += 1

        except Exception:
            continue

    print("Added after filtering:", added)
    save_registry(registry)


if __name__ == "__main__":
    main()

