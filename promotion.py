import os
import random
import json
import time
from web3 import Web3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "promotion_state.json"

def _utc_day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def _render(text: str) -> str:
    now = int(time.time())

    # Basic vars
    text = text.replace("{{MINT_URL}}", os.getenv("MINT_URL", ""))
    text = text.replace("{{NFT_CONTRACT}}", os.getenv("NFT_CONTRACT", ""))
    text = text.replace("{{MAX_SUPPLY}}", os.getenv("MAX_SUPPLY", "3333"))
    text = text.replace("{{MINTED}}", os.getenv("MINTED", "?"))

    # Fee banner
    fee_banner = os.getenv(
        "FEE_BANNER",
        "NFT holders earn 33% of Dust Protocol fees on end of every month."
    )
    text = text.replace("{{FEE_BANNER}}", fee_banner)

    # Countdown
    mint_end = os.getenv("MINT_END_TS")
    if mint_end:
        try:
            remaining = int(mint_end) - now
            if remaining > 0:
                days = remaining // 86400
                hours = (remaining % 86400) // 3600
                minutes = (remaining % 3600) // 60
                countdown = f"⏳ Mint ends in {days}d {hours}h {minutes}m"
            else:
                countdown = "⏳ Mint ended"
        except Exception:
            countdown = ""
    else:
        countdown = ""

    text = text.replace("{{COUNTDOWN}}", countdown)

    return text

def _load_templates() -> dict:
    path = os.path.join("prompts", "moltbook_templates.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _render_template(text: str) -> str:
    """
    Replace {{VARS}} in templates using .env.
    Safe fallback: if missing, keep it readable.
    """
    minted = _get_minted_count()
    max_supply = os.getenv("MAX_SUPPLY", "3333").strip() or "3333"
    mint_url = os.getenv("MINT_URL", "").strip()
    nft_contract = os.getenv("NFT_CONTRACT", "").strip()
    token_contract = os.getenv("TOKEN_CONTRACT", "").strip()

    fee_banner = os.getenv("FEE_BANNER", "").strip()
    if not fee_banner:
        # optional default
        fee_banner = "Fees are enforced on-chain."

    # If you have a countdown string elsewhere, keep placeholder friendly:
    countdown = os.getenv("COUNTDOWN", "").strip()
    if not countdown:
        countdown = "Mint window: 30 days (see mint page countdown)."

    # Replace placeholders
    out = text
    out = out.replace("{{MINTED}}", minted)
    out = out.replace("{{MAX_SUPPLY}}", max_supply)
    out = out.replace("{{MINT_URL}}", mint_url)
    out = out.replace("{{NFT_CONTRACT}}", nft_contract)
    out = out.replace("{{TOKEN_CONTRACT}}", token_contract)
    out = out.replace("{{FEE_BANNER}}", fee_banner)
    out = out.replace("{{COUNTDOWN}}", countdown)

    return out


def _pick_post(templates: dict) -> tuple[str, str]:
    """
    Returns (title, body) for create_post()
    Uses templates["posts"] which is a list of {id, text}.
    """
    posts = templates.get("posts", [])
    if not posts:
        raise RuntimeError("No posts found in prompts/moltbook_templates.json")

    post = random.choice(posts)  # needs: import random at top
    post_id = str(post.get("id", "update")).strip() or "update"
    text = str(post.get("text", "")).strip()
    if not text:
        raise RuntimeError(f"Post '{post_id}' has empty text")

    title = f"Dust Protocol — {post_id}"
    body = _render_template(text)
    return title, body

def _post_moltbook(moltbook_client, title: str, body: str):
    """
    Your Moltbook SDK requires: create_post(submolt, title, body)
    """
    submolt = os.getenv("MOLTBOOK_SUBMOLT", "").strip()
    if not submolt:
        raise RuntimeError("MOLTBOOK_SUBMOLT is not set in .env")

    # Required signature: (submolt, title, body)
    return moltbook_client.create_post(submolt, title, body)

def _get_minted_count() -> str:
    """
    Reads totalSupply() from the NFT contract.
    Returns a string number, or "?" if RPC fails.
    Uses a short timeout to avoid hanging the agent.
    """
    rpc = os.getenv("RPC_URL", "").strip()
    addr = os.getenv("NFT_CONTRACT", "").strip()
    if not rpc or not addr:
        return "?"

    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            return "?"

        abi = [
            {
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]
        c = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
        supply = c.functions.totalSupply().call()
        return str(supply)

    except Exception:
        return "?"

def _parse_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default

def _parse_keywords() -> list[str]:
    raw = os.getenv("PROMOTE_KEYWORDS", "").strip()
    if not raw:
        return []
    return [x.strip().lower() for x in raw.split(",") if x.strip()]

def _cooldown_ok(state: dict, key: str, cooldown_minutes: int) -> bool:
    last = state.get(key)
    if not last:
        return True
    try:
        last = float(last)
    except Exception:
        return True
    return (time.time() - last) >= (cooldown_minutes * 60)

def maybe_post_update(moltbook_client) -> None:
    """
    Posts at most PROMOTE_MAX_POSTS_PER_DAY per UTC day.
    Uses templates in order: launch -> progress -> stage2 -> (repeat last)
    Requires env POST_TO_MOLTBOOK=true and PROMOTE_NFT=true.
    """
    if os.getenv("PROMOTE_NFT", "false").lower() != "true":
        return
    if os.getenv("POST_TO_MOLTBOOK", "false").lower() != "true":
        return

    max_posts = _parse_int("PROMOTE_MAX_POSTS_PER_DAY", 1)
    cooldown_minutes = _parse_int("PROMOTE_COOLDOWN_MINUTES", 120)

    state = _load_state()
    day = _utc_day_key()

    # reset daily counters
    if state.get("day") != day:
        state["day"] = day
        state["posts_today"] = 0
        state["replies_today"] = 0

    if state.get("posts_today", 0) >= max_posts:
        return

    # cooldown between posts
    if not _cooldown_ok(state, "last_post_ts", cooldown_minutes):
        return

    templates = _load_templates()
    posts = templates.get("posts", [])
    idx = int(state.get("post_index", 0))
    if not posts:
        return
    if idx >= len(posts):
        idx = len(posts) - 1  # keep using last one

    # Build the post body (this is what we will publish)
    post_body = _render(
        "Dust Protocol — Genesis mint is live on Monad.\n"
        "Minted: {{MINTED}}/{{MAX_SUPPLY}}\n"
        "Price: 33 MON • 30-day window\n"
        "\n"
        "NFT Utility: Holders earn 33% share of Dust Protocol revenue on end of every month.\n"
        "\n"
        "Mint: {{MINT_URL}}\n"
        "Contract: {{NFT_CONTRACT}}"
    )

    title = os.getenv("NFT_POST_TITLE", "Dust Protocol — Genesis Mint").strip()
    try:
        _post_moltbook(moltbook_client, title=title, body=post_body)
    except Exception as e:
        print("[promotion] posting skipped (moltbook unreachable):", e)
        return

    text = _render(posts[idx]["text"])

    state["posts_today"] = int(state.get("posts_today", 0)) + 1
    state["post_index"] = idx + 1
    state["last_post_ts"] = time.time()
    _save_state(state)

def maybe_reply_to_comments(moltbook_client, new_comments: list[dict]) -> None:
    """
    Auto-replies to comments that match keywords/intent.
    - new_comments should be a list of dicts with at least:
      { "id": "...", "text": "...", "thread_id": "..."} (or post_id)
    - Enforces daily reply limit + per-thread cooldown
    """
    if os.getenv("PROMOTE_NFT", "false").lower() != "true":
        return
    if os.getenv("POST_TO_MOLTBOOK", "false").lower() != "true":
        return

    max_replies = _parse_int("PROMOTE_MAX_REPLIES_PER_DAY", 15)
    cooldown_minutes = _parse_int("PROMOTE_COOLDOWN_MINUTES", 120)
    keywords = _parse_keywords()

    state = _load_state()
    day = _utc_day_key()
    if state.get("day") != day:
        state["day"] = day
        state["posts_today"] = 0
        state["replies_today"] = 0

    if state.get("replies_today", 0) >= max_replies:
        return

    templates = _load_templates()
    reply_rules = templates.get("replies", [])

    for c in new_comments:
        if state.get("replies_today", 0) >= max_replies:
            break

        text = (c.get("text") or "").strip()
        if not text:
            continue

        lower = text.lower()

        # Optional keyword gate: if PROMOTE_KEYWORDS set, ignore comments that don't contain any keyword
        if keywords and not any(k in lower for k in keywords):
            continue

        # Per-thread cooldown to avoid spam in the same conversation
        thread_id = c.get("thread_id") or c.get("post_id") or "unknown"
        cooldown_key = f"last_reply_ts::{thread_id}"
        if not _cooldown_ok(state, cooldown_key, cooldown_minutes):
            continue

        reply_text = None
        for rule in reply_rules:
            match_list = [m.lower() for m in rule.get("match", [])]
            if any(m in lower for m in match_list):
                reply_text = _render(rule.get("text", ""))
                break

        # fallback if keyword matched but no rule matched
        if not reply_text:
            reply_text = _render("Mint link: {{MINT_URL}} • Contract: {{NFT_CONTRACT}}")

        # IMPORTANT: You must map this to your Moltbook SDK call.
        # Reply (SDKs differ on parameter name; try a few)
        try:
            moltbook_client.reply(comment_id=c["id"], text=reply_text)
        except TypeError:
            try:
                moltbook_client.reply(id=c["id"], text=reply_text)
            except TypeError:
                try:
                    moltbook_client.reply(comment_id=c["id"], content=reply_text)
                except TypeError:
                    try:
                        moltbook_client.reply(comment_id=c["id"], message=reply_text)
                    except TypeError:
                        # fallback: positional
                        moltbook_client.reply(c["id"], reply_text)

        state["replies_today"] = int(state.get("replies_today", 0)) + 1
        state[cooldown_key] = time.time()
        _save_state(state)

