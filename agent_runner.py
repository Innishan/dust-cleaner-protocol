import time
import os

from agent import run_agent_once

SLEEP_SECONDS = int(os.getenv("AGENT_SLEEP_SECONDS", "900"))  # 900 = 15 min

if __name__ == "__main__":
    while True:
        try:
            run_agent_once()
        except Exception as e:
            print("[runner] run_agent_once error:", e)

        print(f"[runner] sleeping {SLEEP_SECONDS}s...")
        time.sleep(SLEEP_SECONDS)
