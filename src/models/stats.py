class TFTStats:
    def __init__(self, current_rank, average_position, last_games):
        self.current_rank = current_rank
        self.average_position = average_position
        self.last_games = last_games

    def to_dict(self):
        return {
            "current_rank": self.current_rank,
            "average_position": self.average_position,
            "last_games": self.last_games
        }