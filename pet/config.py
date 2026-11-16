"""pet.toml: the three words (fractal, genome, goals) plus the game settings."""
import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import PetError
from .lsystem import Grammar, Production

CORE_ALPHABET = {
    "G": "goals: list top_n candidate tasks at the edge of your skill",
    "H": "hardest: the engine picks the hardest candidate",
    "R": "recall: check the task and every outside input against CRISPR spacers",
    "O": "observe: read, look around",
    "P": "predict: state what you expect and how likely it is",
    "A": "act",
    "C": "compare: prediction against outcome; pick the best branch",
    "L": "learn: compress experience into a skill, a gene or a spacer",
    "T": "tell: report to your human",
    "M": "meta: write one new rewrite rule into your grammar",
}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER = "fill in"


class ConfigError(PetError):
    pass


@dataclass(frozen=True)
class Gene:
    id: str
    text: str
    immutable: bool = False


@dataclass(frozen=True)
class Goal:
    id: str
    text: str


@dataclass(frozen=True)
class GameRules:
    edge_low: float = 0.5
    edge_high: float = 0.7
    top_n: int = 5
    mutations_per_day: int = 1
    sos_window: int = 4
    sos_mutations: int = 3
    trial_cycles: int = 3
    reuse_threshold: int = 2


class _Table:
    """Typed access to one TOML table with error messages that name the key."""

    def __init__(self, data, where):
        if not isinstance(data, dict):
            raise ConfigError(f"[{where}] must be a table")
        self.data = data
        self.where = where

    def table(self, key):
        return _Table(self.data.get(key, {}), f"{self.where}.{key}" if self.where else key)

    def get(self, key, kind, default=None, required=False):
        if key not in self.data:
            if required:
                raise ConfigError(f"[{self.where}] {key} is required")
            return default
        value = self.data[key]
        kinds = kind if isinstance(kind, tuple) else (kind,)
        if isinstance(value, bool) and bool not in kinds:
            raise ConfigError(f"[{self.where}] {key} has the wrong type")
        if not isinstance(value, kinds):
            raise ConfigError(f"[{self.where}] {key} has the wrong type")
        return value

    def text(self, key, required=True):
        value = self.get(key, str, required=required)
        if required and not value.strip():
            raise ConfigError(f"[{self.where}] {key} must not be empty")
        return value


class PetConfig:
    FILE_NAME = "pet.toml"

    def __init__(self, path, raw):
        self.path = Path(path)
        self.raw = raw
        root = _Table(tomllib.loads(raw), "")
        game = root.table("game")
        self.days = game.get("days", int, 28)
        self.frozen = game.get("frozen", bool, False)
        pinned = root.table("pinned")
        self.model = pinned.text("model")
        self.harness = pinned.text("harness")
        for key, value in (("model", self.model), ("harness", self.harness)):
            if value.startswith(PLACEHOLDER):
                raise ConfigError(f"[pinned] {key}: replace the placeholder with your real {key}")
        fractal = root.table("fractal")
        self.grammar = self._grammar(fractal)
        self.depth_every_days = fractal.get("depth_every_days", int, 3)
        if self.depth_every_days < 1:
            raise ConfigError("[fractal] depth_every_days must be positive")
        self.genes = self._genes(root.get("genome", dict, {}))
        self.goals = self._goals(root.get("goals", list, []))
        self.rules = self._rules(root.table("rules"))
        if self.days < 1:
            raise ConfigError("[game] days must be positive")

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"{path} not found")
        try:
            return cls(path, path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise ConfigError(f"{path.name}: {error}") from error

    @property
    def sha256(self):
        return hashlib.sha256(self.raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _grammar(fractal):
        custom = fractal.get("alphabet", dict, {})
        clash = sorted(set(custom) & set(CORE_ALPHABET))
        if clash:
            raise ConfigError(f"[fractal.alphabet] redefines core letters {''.join(clash)}")
        rules = {}
        for symbol, raw in fractal.get("rules", dict, {}).items():
            productions = raw if isinstance(raw, list) else [raw]
            rules[symbol] = [Production.parse(item, f"[fractal.rules] {symbol}") for item in productions]
        return Grammar(fractal.text("axiom"), {**CORE_ALPHABET, **custom}, rules, fractal.get("max_length", int, 80)).validate()

    @staticmethod
    def _genes(genome):
        genes = []
        for index, raw in enumerate(genome.get("genes", [])):
            table = _Table(raw, f"genome.genes #{index + 1}")
            gene = Gene(table.text("id"), table.text("text"), table.get("immutable", bool, False))
            if not SLUG.match(gene.id):
                raise ConfigError(f"gene id {gene.id!r} must be lowercase letters, digits and dashes")
            genes.append(gene)
        if not genes:
            raise ConfigError("[[genome.genes]] needs at least one gene")
        PetConfig._unique([gene.id for gene in genes], "gene")
        return genes

    @staticmethod
    def _goals(raw_goals):
        goals = []
        for index, raw in enumerate(raw_goals):
            table = _Table(raw, f"goals #{index + 1}")
            goals.append(Goal(table.text("id"), table.text("text")))
        if not goals:
            raise ConfigError("[[goals]] needs at least one goal")
        PetConfig._unique([goal.id for goal in goals], "goal")
        return goals

    @staticmethod
    def _rules(table):
        edge = table.get("edge", list, [0.5, 0.7])
        if len(edge) != 2 or not all(isinstance(bound, (int, float)) and not isinstance(bound, bool) for bound in edge):
            raise ConfigError("[rules] edge must be [low, high]")
        low, high = float(edge[0]), float(edge[1])
        if not 0 < low < high < 1:
            raise ConfigError("[rules] edge must satisfy 0 < low < high < 1")
        counts = {name: table.get(name, int, getattr(GameRules, name)) for name in (
            "top_n", "mutations_per_day", "sos_window", "sos_mutations", "trial_cycles", "reuse_threshold")}
        for name, value in counts.items():
            if value < 1:
                raise ConfigError(f"[rules] {name} must be positive")
        if counts["sos_mutations"] < counts["mutations_per_day"]:
            raise ConfigError("[rules] sos_mutations must not be below mutations_per_day")
        return GameRules(low, high, **counts)

    @staticmethod
    def _unique(ids, kind):
        seen = set()
        for item in ids:
            if item in seen:
                raise ConfigError(f"duplicate {kind} id {item!r}")
            seen.add(item)

    def goal_ids(self):
        return {goal.id for goal in self.goals}
