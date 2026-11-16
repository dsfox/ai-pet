import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pet.game import Pet
from pet.life import Clock

REPO = Path(__file__).resolve().parent.parent
START = datetime(2026, 11, 17, 10, 0, 0)


def seed_toml(**replacements):
    text = (REPO / "pet.toml").read_text(encoding="utf-8")
    text = text.replace('model = "fill in: the model id your agent runs on"', 'model = "test-model-1"')
    text = text.replace('harness = "fill in: Claude Code / Codex / hermes-agent / ... and its version"', 'harness = "test-harness-1"')
    for old, new in replacements.items():
        if old not in text:
            raise AssertionError(f"fixture text not found: {old}")
        text = text.replace(old, new)
    return text


class ManualClock(Clock):
    def __init__(self):
        super().__init__(START)

    def advance(self, days=0, hours=0):
        self.fixed += timedelta(days=days, hours=hours)


def candidates(difficulties=(1, 2, 3, 4, 5), probabilities=(0.7, 0.6, 0.6, 0.55, 0.5), goal="browser"):
    return [{"task": f"task {index}", "goal": goal, "difficulty": difficulty, "p_success": probability,
             "expect": f"expectation {index}"}
            for index, (difficulty, probability) in enumerate(zip(difficulties, probabilities))]


def result(cycle, success=True, **extra):
    branches = [{"name": f"b{index}", "score": 0.5} for index, _ in enumerate(cycle["branches"])]
    data = {"success": success, "outcome": "done", "lesson": "noted", "branches": branches,
            "merged": branches[0]["name"] if branches else None}
    if not success:
        data["spacer"] = {"pattern": f"failure of {cycle['id']}", "kind": "error", "note": "test"}
    data.update(extra)
    return data


class PetCase(unittest.TestCase):
    toml_replacements = {}

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ai-pet-test-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.root = self.make_root("main", **self.toml_replacements)
        self.clock = ManualClock()
        self.pet = self.make_pet(self.root)

    def make_root(self, name, **replacements):
        root = self.dir / name
        root.mkdir()
        (root / "pet.toml").write_text(seed_toml(**replacements), encoding="utf-8")
        return root

    def make_pet(self, root, init=True):
        pet = Pet(root, self.clock)
        if init:
            pet.init()
        return pet

    def run_cycle(self, pet=None, success=True, **extra):
        pet = pet or self.pet
        record = pet.open_cycle(candidates())
        pet.close_cycle(record["id"], result(record, success, **extra))
        return record
