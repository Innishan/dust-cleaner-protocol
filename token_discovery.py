import json
from web3 import Web3

TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()

REGISTRY_FILE = "known_tokens.json"
STATE_FILE = "scan_state.json"

def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def discover_token_contracts_incremental(
    w3: Web3,
    wallet: str,
    chunk_size: int = 8000,
    max_chunks_per_run: int = 100,
):
    """
    Scans Transfer(to=wallet) logs incrementally and stores discovered token
    contract addresses in known_tokens.json so we don't re-scan forever.

    Each run scans only a limited number of chunks to avoid freezing.
    """
    wallet = Web3.to_checksum_address(wallet)
    latest = w3.eth.block_number

    # Load what we already know
    known = _load_json(REGISTRY_FILE, [])
    known_set = set(known)

    state = _load_json(STATE_FILE, {"last_scanned_block": latest})
    last = int(state.get("last_scanned_block", latest))

    # We scan backwards from `last` downwards in chunks
    start_block = max(0, last - chunk_size * max_chunks_per_run)

    topic_to = "0x" + wallet.lower().replace("0x", "").rjust(64, "0")

    current_to = last
    chunks_scanned = 0

    while current_to > start_block and chunks_scanned < max_chunks_per_run:
        current_from = max(start_block, current_to - chunk_size)

        try:
            logs = w3.eth.get_logs({
                "fromBlock": current_from,
                "toBlock": current_to,
                "topics": [TRANSFER_TOPIC, None, topic_to],
            })
        except Exception as e:
            # If range too big, reduce chunk size dynamically
            current_to = current_from - 1
            continue
        
        for log in logs:
            addr = log.get("address")
            if addr and addr not in known_set:
                known_set.add(addr)
                known.append(addr)

        current_to = current_from - 1
        chunks_scanned += 1

    # Save updated registry
    _save_json(REGISTRY_FILE, known)

    # Update state so next run continues where we left off
    state["last_scanned_block"] = max(0, current_to)
    _save_json(STATE_FILE, state)

    return known

