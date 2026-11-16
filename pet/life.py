"""life/: the agent's living state. Journals are append-only JSON lines."""
import json
import os
from datetime import datetime
from pathlib import Path


class Clock:
    ENV = "AI_PET_NOW"

    def __init__(self, fixed=None):
        self.fixed = fixed

    def now(self):
        if self.fixed is not None:
            return self.fixed
        override = os.environ.get(self.ENV)
        if override:
            return datetime.fromisoformat(override)
        return datetime.now().replace(microsecond=0)


class Life:
    DIR_NAME = "life"

    def __init__(self, root):
        self.dir = Path(root) / self.DIR_NAME

    def exists(self):
        return (self.dir / "seed.json").is_file()

    def path(self, name):
        return self.dir / name

    def read_json(self, name):
        return json.loads(self.path(name).read_text(encoding="utf-8"))

    def write_json(self, name, data):
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def append(self, name, record):
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def records(self, name):
        target = self.path(name)
        if not target.is_file():
            return []
        return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]

    def save_generation(self, number, snapshot):
        self.write_json(f"generations/{number:03d}.json", snapshot)
