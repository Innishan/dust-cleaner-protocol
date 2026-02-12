import os
from dotenv import load_dotenv
from moltbook import MoltbookClient

load_dotenv()

EMAIL = os.getenv("MOLTBOOK_OWNER_EMAIL")
if not EMAIL:
    raise RuntimeError("MOLTBOOK_OWNER_EMAIL not set in .env")

client = MoltbookClient()

print("Requesting Moltbook to set owner email:", EMAIL)

resp = client._post(
    "agents/me/setup-owner-email",
    {"email": EMAIL}
)

print("Response:", resp)
print("✅ If no error, check your email inbox for login link.")

