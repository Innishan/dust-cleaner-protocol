from moltbook import MoltbookClient

# Creates a brand new agent and returns credentials (including api_key)
result = MoltbookClient.register("MonadMarketMakerBot", "Monad micro-bets + market maker quotes + build logs")

print(result)  # IMPORTANT: copy api_key somewhere safe locally, do NOT share publicly

