"""The fractal word: a stochastic L-system that grows the agent's work program."""
import random
from dataclasses import dataclass

from .errors import PetError

BRACKETS = "[]"


class GrammarError(PetError):
    pass


@dataclass(frozen=True)
class Production:
    to: str
    weight: float = 1.0

    @classmethod
    def parse(cls, raw, where):
        if isinstance(raw, str):
            return cls(compact(raw))
        if not isinstance(raw, dict) or not isinstance(raw.get("to"), str):
            raise GrammarError(f"{where}: a production is a string or {{to = \"...\", weight = 1}}")
        weight = raw.get("weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise GrammarError(f"{where}: weight must be a number")
        return cls(compact(raw["to"]), float(weight))


def compact(word):
    return "".join(word.split())


def is_balanced(word):
    depth = 0
    for symbol in word:
        if symbol == "[":
            depth += 1
        elif symbol == "]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def top_level_branches(program):
    """Sub-programs inside the outermost brackets; each one runs as its own sub-agent."""
    branches, depth, start = [], 0, 0
    for index, symbol in enumerate(program):
        if symbol == "[":
            if depth == 0:
                start = index + 1
            depth += 1
        elif symbol == "]":
            depth -= 1
            if depth == 0:
                branches.append(program[start:index])
    return branches


class Grammar:
    def __init__(self, axiom, alphabet, rules, max_length):
        self.axiom = compact(axiom)
        self.alphabet = dict(alphabet)
        self.rules = {symbol: list(productions) for symbol, productions in rules.items()}
        self.max_length = max_length

    def validate(self):
        if not self.axiom:
            raise GrammarError("axiom is empty")
        if isinstance(self.max_length, bool) or not isinstance(self.max_length, int) or self.max_length < len(self.axiom):
            raise GrammarError("max_length must be an integer not shorter than the axiom")
        for letter in self.alphabet:
            if len(letter) != 1 or letter in BRACKETS or letter.isspace():
                raise GrammarError(f"alphabet letter {letter!r} must be one non-bracket character")
        self._check_word(self.axiom, "axiom")
        for symbol, productions in self.rules.items():
            if symbol not in self.alphabet:
                raise GrammarError(f"rule for unknown symbol {symbol!r}")
            if not productions:
                raise GrammarError(f"rule {symbol} has no productions")
            for production in productions:
                self._check_word(production.to, f"rule {symbol} -> {production.to}")
                if production.weight <= 0:
                    raise GrammarError(f"rule {symbol} -> {production.to}: weight must be positive")
        return self

    def _check_word(self, word, where):
        unknown = sorted({symbol for symbol in word if symbol not in self.alphabet and symbol not in BRACKETS})
        if unknown:
            raise GrammarError(f"{where}: unknown symbols {''.join(unknown)}")
        if not is_balanced(word):
            raise GrammarError(f"{where}: unbalanced brackets")

    def expand(self, depth, seed):
        """Rewrite every symbol `depth` times; stop at the last word that fits max_length."""
        self.validate()
        rng = random.Random(seed)
        word, truncated = self.axiom, False
        for _ in range(depth):
            grown = "".join(self._rewrite(symbol, rng) for symbol in word)
            if len(grown) > self.max_length:
                truncated = True
                break
            word = grown
        return word, truncated

    def _rewrite(self, symbol, rng):
        productions = self.rules.get(symbol)
        if not productions:
            return symbol
        return rng.choices(productions, weights=[production.weight for production in productions])[0].to

    def production_count(self):
        return sum(len(productions) for productions in self.rules.values())

    def with_letter(self, letter, meaning):
        if letter in self.alphabet:
            raise GrammarError(f"letter {letter!r} already means: {self.alphabet[letter]}")
        alphabet = {**self.alphabet, letter: meaning}
        return Grammar(self.axiom, alphabet, self.rules, self.max_length).validate()

    def with_production(self, symbol, production):
        rules = {key: list(value) for key, value in self.rules.items()}
        rules.setdefault(symbol, []).append(production)
        return Grammar(self.axiom, self.alphabet, rules, self.max_length).validate()

    def to_dict(self):
        return {
            "axiom": self.axiom,
            "alphabet": self.alphabet,
            "rules": {symbol: [{"to": p.to, "weight": p.weight} for p in productions] for symbol, productions in self.rules.items()},
            "max_length": self.max_length,
        }

    @classmethod
    def from_dict(cls, data):
        rules = {
            symbol: [Production.parse(raw, f"rule {symbol}") for raw in productions]
            for symbol, productions in data["rules"].items()
        }
        return cls(data["axiom"], data["alphabet"], rules, data["max_length"]).validate()
