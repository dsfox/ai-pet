"""M: the rule that writes rules. Each M in the current program allows one new production."""
from .errors import PetError
from .lsystem import BRACKETS, Production, compact


class MetaGate:
    def __init__(self, life, config):
        self.life = life
        self.config = config

    def used_in(self, cycle_id):
        return [record for record in self.life.records("mutations.jsonl")
                if record["event"] == "meta" and record["cycle"] == cycle_id]

    def quota(self, cycle):
        return cycle.opened["program"].count("M") - len(self.used_in(cycle.id))

    def write(self, grammar, cycle, symbol, to, weight, define, reason, now):
        if self.config.frozen:
            raise PetError("this pet is a frozen control twin: its grammar never changes")
        if cycle is None:
            raise PetError("M works inside a cycle: open one with `tasks` first")
        if self.quota(cycle) <= 0:
            raise PetError(f"no M left in the program of {cycle.id}: {cycle.opened['program']}")
        if not reason or not reason.strip():
            raise PetError("a new rule needs a reason")
        if define is not None:
            letter, meaning = define
            if not meaning.strip():
                raise PetError("a new letter needs a meaning")
            grammar = grammar.with_letter(letter, meaning.strip())
        if len(symbol) != 1 or symbol in BRACKETS:
            raise PetError("--symbol must be one letter")
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise PetError("--weight must be positive")
        grammar = grammar.with_production(symbol, Production(compact(to), float(weight)))
        record = {"event": "meta", "cycle": cycle.id, "at": now.isoformat(), "symbol": symbol, "to": compact(to),
                  "weight": float(weight), "define": None if define is None else {"letter": define[0], "meaning": define[1]},
                  "reason": reason.strip()}
        self.life.append("mutations.jsonl", record)
        return grammar, record
