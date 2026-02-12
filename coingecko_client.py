import requests
import time


BASE = "https://api.coingecko.com/api/v3"


def _get(url, params=None, timeout=10, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)

            # Fail fast if rate-limited (do NOT sleep for minutes)
            if r.status_code == 429:
                return None, 429

            if r.status_code == 200:
                return r.json(), 200

            return None, r.status_code

        except Exception:
            time.sleep(0.5 + i)

    return None, None


def get_platform_id_by_chain_id(chain_id: int):
    # For our project: Monad EVM chain id is 143
    if chain_id == 143:
        return "monad"
    return None


def verify_contract_on_platform(platform_id: str, contract_address: str):
    # /coins/{platform}/contract/{address}
    data, code = _get(f"{BASE}/coins/{platform_id}/contract/{contract_address}", timeout=10, retries=2)
    return (code == 200), data


def token_price_usd(platform_id: str, contract_address: str):
    # /simple/token_price/{platform}
    params = {
        "contract_addresses": contract_address,
        "vs_currencies": "usd",
    }
    data, code = _get(f"{BASE}/simple/token_price/{platform_id}", params=params, timeout=10, retries=2)
    if code != 200 or not isinstance(data, dict):
        return None
    return data.get(contract_address.lower(), {}).get("usd")

