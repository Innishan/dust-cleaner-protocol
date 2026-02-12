class MicroBet:
    def __init__(self, question, stake, agent_a, agent_b):
        self.question = question
        self.stake = stake
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.resolved = False
        self.winner = None

    def resolve(self, outcome: bool):
        self.resolved = True
        if outcome:
            self.winner = self.agent_a
        else:
            self.winner = self.agent_b

    def summary(self):
        if not self.resolved:
            return "Bet unresolved"
        return f"Winner: {self.winner} | Stake: {self.stake}"

