from moltbook import MoltbookClient
from dotenv import dotenv_values

def get_client():
    env = dotenv_values(".env")
    return MoltbookClient(api_key=env["MOLTBOOK_API_KEY"])

def heartbeat():
    mb = get_client()
    return mb.status()

def post_build_log(title: str, content: str):
    mb = get_client()
    # posts are rate limited by SDK
    return mb.create_post(submolt="builds", title=title, content=content)

