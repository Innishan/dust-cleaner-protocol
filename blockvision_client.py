
import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.blockvision.org/v2/monad"
API_KEY = os.getenv("BLOCKVISION_API_KEY")

CACHE_FILE = "blockvision_cache.json"


def _save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def get_wallet_tokens(wallet: str):
    if not API_KEY:
        raise ValueError("Missing BLOCKVISION_API_KEY in .env")

    url = f"{BASE}/account/tokens"
    headers = {"X-API-KEY": API_KEY}
    params = {"address": wallet}

    # Retry up to 3 times
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=45)
            r.raise_for_status()
            data = r.json()

            # Save successful response to cache
            _save_cache(data)
            return data

        except Exception as e:
            print(f"BlockVision timeout (attempt {attempt+1}/3)")
            time.sleep(2)

    # All attempts failed → fallback to cache
    cached = _load_cache()
    if cached:
        print("⚠️ Using cached BlockVision data")
        return cached

    # Absolute fallback: empty response
    return {"result": {"data": []}}

