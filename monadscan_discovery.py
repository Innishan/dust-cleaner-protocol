import os
import requests
from typing import List, Set, Optional, Dict, Any
from dotenv import load_dotenv

def _get_base() -> str:
    load_dotenv(dotenv_path=".env", override=True)
    base = (os.getenv("MONADSCAN_API_URL", "") or "").strip()
    if not base:
        raise RuntimeError("MONADSCAN_API_URL is not set in .env")
    return base.rstrip("/")

def discover_token_contracts_monadscan(wallet: str, max_pages: int = 5, page_size: int = 200) -> List[str]:
    """
    Discover ERC-20 token contracts from MonadScan.

    Strategy:
    1) Try Blockscout-style v2 API (usually NO API KEY needed)
    2) If MONADSCAN_API_KEY is set, also try Etherscan-style API as fallback
    """
    wallet = wallet.strip()
    base = _get_base()
    found: Set[str] = set()

    # ----------------------------
    # 1) Blockscout v2 API (best)
    # ----------------------------
    # Typical endpoint:
    #   /api/v2/addresses/{addr}/token-transfers?type=ERC-20
    try:
        url = f"{base}/api/v2/addresses/{wallet}/token-transfers"
        params: Dict[str, Any] = {"type": "ERC-20"}
        # Some blockscout instances use pagination via "next_page_params"
        pages = 0

        while pages < max_pages:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            items = data.get("items", [])
            if not isinstance(items, list) or len(items) == 0:
                break

            for row in items:
                token = row.get("token") or {}
                ca = (token.get("address") or token.get("address_hash") or "").strip()
                if ca.startswith("0x") and len(ca) == 42:
                    found.add(ca)

            npp = data.get("next_page_params")
            if not npp:
                break

            # Merge next_page_params into params for the next request
            if isinstance(npp, dict):
                params = {**params, **npp}
            pages += 1

        if found:
            return sorted(found)

    except Exception:
        # If v2 isn't supported, we'll try etherscan-style next (if key exists)
        pass

    # ---------------------------------------
    # 2) Etherscan-style API (needs API key)
    # ---------------------------------------
    key = (os.getenv("MONADSCAN_API_KEY", "") or "").strip()
    if not key:
        # No key and v2 failed => return empty rather than crash
        return sorted(found)

    # Etherscan-style base is usually ".../api"
    try:
        url = f"{base}/api"
        for page in range(1, max_pages + 1):
            params = {
                "module": "account",
                "action": "tokentx",
                "address": wallet,
                "page": page,
                "offset": page_size,
                "sort": "desc",
                "apikey": key,
            }
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            status = str(data.get("status", "")).strip()
            result = data.get("result", [])

            if status != "1" or not isinstance(result, list) or len(result) == 0:
                break

            for row in result:
                ca = (row.get("contractAddress") or "").strip()
                if ca.startswith("0x") and len(ca) == 42:
                    found.add(ca)

    except Exception:
        pass

    return sorted(found)

