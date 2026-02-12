from moltbook import MoltbookClient
import time
import json

AGENT_NAME = "MonadMarketMakerBot"
CONTRACT_ADDRESS = "0x97c4fe240555b7D425AdB82CA16876d5BaE0d8A5"

KEYWORDS = ["dust", "swap", "how", "clean", "mon", "fee"]

client = MoltbookClient()
REPLIED_FILE = "replied_posts.json"
MAX_REPLIES_PER_RUN = 2

def create_post(text: str):
    return client.create_post(text=text)

def reply(comment_id: str, text: str):
    return client.reply(comment_id=comment_id, text=text)

def _as_dict(obj):
    """Convert Moltbook SDK objects OR dicts into a dict safely."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj

    # Many SDK objects have attributes like .id, .content
    d = {}
    for key in ["id", "post_id", "content", "text"]:
        if hasattr(obj, key):
            d[key] = getattr(obj, key)

    # Fallback: try __dict__
    if hasattr(obj, "__dict__"):
        try:
            d.update(obj.__dict__)
        except:
            pass

    return d

def _load_replied():
    try:
        with open(REPLIED_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def _save_replied(s):
    with open(REPLIED_FILE, "w") as f:
        json.dump(sorted(list(s)), f, indent=2)

def post_marketing_update(sold_symbols):
    msg = (
        "🧹 Dust Cleaner Update\n\n"
        f"Tokens cleaned: {', '.join(sold_symbols)}\n"
        "Returned MON to wallet.\n\n"
        f"Contract: {CONTRACT_ADDRESS}\n"
        "Reply 'how' for usage steps."
    )
    client.create_post(
        title="🧹 Dust Cleaner Update",
        content=msg
    )
    print("Marketing post sent ✅")

def reply_if_needed():
    import os
    if os.getenv("POST_TO_MOLTBOOK", "false").lower() != "true":
        print("[moltbook] reply skipped (POST_TO_MOLTBOOK=false)")
        return
    replied = _load_replied()
    sent = 0

    feed = client.get_feed(limit=30)

    if isinstance(feed, list):
        items = feed
    elif isinstance(feed, dict):
        items = feed.get("items", [])
    else:
        items = []

    for raw in items:
        if sent >= MAX_REPLIES_PER_RUN:
            break

        item = _as_dict(raw)

        post_id = item.get("id") or item.get("post_id")
        content = (item.get("content") or item.get("text") or "")
        content_lc = content.lower()

        if not post_id:
            continue

        # Only reply once per post
        if str(post_id) in replied:
            continue

        # Only reply if it looks like a question / request
        is_question = ("?" in content) or ("how" in content_lc) or ("help" in content_lc)

        if is_question and any(k in content_lc for k in KEYWORDS):
            reply = (
                "🧹 Monad Dust Cleaner\n\n"
                "Steps:\n"
                "1) approve(token → contract)\n"
                "2) call cleanDustToMon(token, amount, minOut, deadline)\n\n"
                f"Contract: {CONTRACT_ADDRESS}\n"
                "Fee: 2% → rest returned as MON\n\n"
                "Tell me token + amount and I’ll generate exact commands."
            )

            client.comment(post_id, reply)
            replied.add(str(post_id))
            _save_replied(replied)

            sent += 1
            print("Auto-replied to a post ✅")
            time.sleep(5)

def reply_to_dms():
    import os
    if os.getenv("POST_TO_MOLTBOOK", "false").lower() != "true":
        print("[moltbook] dm reply skipped (POST_TO_MOLTBOOK=false)")
        return
    dms = client.check_dms()

    if isinstance(dms, list):
        messages = dms
    elif isinstance(dms, dict):
        messages = dms.get("messages", []) or dms.get("items", []) or []
    else:
        messages = []

    for raw in messages:
        m = _as_dict(raw)

        text = (m.get("content") or m.get("text") or "")
        text_lc = text.lower()
        dm_id = m.get("id") or m.get("dm_id")

        if not dm_id:
            continue

        if any(k in text_lc for k in KEYWORDS):
            reply = (
                "🧹 Monad Dust Cleaner (Public)\n\n"
                f"Contract: {CONTRACT_ADDRESS}\n"
                "Fee: 2%\n\n"
                "To use:\n"
                "1) approve(token → contract)\n"
                "2) call cleanDustToMon(token, amount, minOut, deadline)\n\n"
                "Send token contract + amount and I’ll generate exact commands."
            )
            client.reply_dm(dm_id, reply)
            print("Auto-replied in DM ✅")
            time.sleep(3)

def fetch_new_comments(limit: int = 20):
    """
    Fetch recent comments/mentions the agent can reply to.
    Returns a list of dicts: {id, text, thread_id}
    NOTE: You must map this to the correct Moltbook SDK method available in your version.
    """
    items = []

    # Try common SDK methods (one of these should exist)
    for method_name in ["get_mentions", "mentions", "get_notifications", "notifications", "get_inbox", "inbox"]:
        fn = getattr(client, method_name, None)
        if callable(fn):
            try:
                raw = fn(limit=limit)
                # raw can be list of objects or dicts
                for x in (raw or []):
                    d = to_dict(x)  # your helper already exists at line ~15
                    text = d.get("text") or d.get("content") or d.get("body") or ""
                    cid = d.get("id") or d.get("comment_id") or d.get("notification_id")
                    thread_id = d.get("thread_id") or d.get("post_id") or d.get("parent_id") or cid
                    if cid:
                        items.append({"id": str(cid), "text": str(text), "thread_id": str(thread_id)})
                return items
            except Exception:
                pass

    # If none of the methods exist, return empty list (safe)
    return items

