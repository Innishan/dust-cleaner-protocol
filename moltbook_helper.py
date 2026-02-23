import os
from moltbook import MoltbookClient


def get_client() -> MoltbookClient:
    """
    Render (and any server) provides env vars, not a local .env file.
    So we MUST read from os.getenv.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOLTBOOK_API_KEY is missing in environment")
    return MoltbookClient(api_key=api_key)


def heartbeat():
    mb = get_client()
    return mb.status()


def post_build_log(title: str, content: str):
    mb = get_client()
    submolt = os.getenv("MOLTBOOK_SUBMOLT", "trading").strip() or "trading"
    # SDK expects: create_post(submolt, title, content)
    return mb.create_post(submolt, title, content)
