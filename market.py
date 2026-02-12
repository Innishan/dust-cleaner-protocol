class MarketMaker:
    def __init__(self, base_token, quote_token, spread=0.02):
        self.base = base_token
        self.quote = quote_token
        self.spread = spread  # 2% spread

    def quote_buy(self, price):
        return price * (1 + self.spread)

    def quote_sell(self, price):
        return price * (1 - self.spread)

