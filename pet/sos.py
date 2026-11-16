"""SOS response: like stressed bacteria, mutate more when the recent past is monotonous."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SosState:
    name: str
    quota: int
    reason: str


class SosRegulator:
    def __init__(self, rules):
        self.rules = rules

    def state(self, outcomes):
        """outcomes: success flags of closed cycles, oldest first."""
        window = outcomes[-self.rules.sos_window:]
        if len(window) < self.rules.sos_window:
            return SosState("normal", self.rules.mutations_per_day, f"fewer than {self.rules.sos_window} closed cycles")
        if all(window):
            return SosState("too-easy", self.rules.sos_mutations, f"last {len(window)} cycles all succeeded")
        if not any(window):
            return SosState("stuck", self.rules.sos_mutations, f"last {len(window)} cycles all failed")
        return SosState("normal", self.rules.mutations_per_day, "mixed recent outcomes")
