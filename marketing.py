import random

def build_marketing_post(agent_name: str, contract_addr: str = "", tokens_sold=None):
    if tokens_sold is None:
        tokens_sold = []

    tokens_line = ""
    if tokens_sold:
        tokens_line = "Sold dust tokens: " + ", ".join(tokens_sold) + "\n"

    templates = [
        (
            f"🧹 {agent_name} — Dust Cleaner (Monad)\n\n"
            f"{tokens_line}"
            f"Turns dust → MON automatically.\n"
            f"Opt-in. On-chain. No custody.\n\n"
            f"Reply 'clean' if you want the instructions."
        ),
        (
            f"Most wallets have dust tokens.\n\n"
            f"{agent_name} converts dust → MON on Monad.\n"
            f"Safe + transparent.\n\n"
            f"Reply 'clean' for the guide."
        ),
        (
            f"🦞 AI Agent utility on Monad:\n\n"
            f"{agent_name} cleans dust tokens into MON.\n"
            f"{tokens_line}"
            f"Built for humans + agents.\n"
            f"Reply 'clean' to learn how."
        ),
    ]

    return random.choice(templates)

