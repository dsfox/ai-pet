"""CRISPR memory: short spacers cut from past errors and hostile inputs."""
from .errors import PetError

KINDS = ("error", "injection")
MIN_PATTERN = 4


def normalize(text):
    return " ".join(text.casefold().split())


class SpacerMemory:
    NAME = "spacers.jsonl"

    def __init__(self, life):
        self.life = life

    def all(self):
        return self.life.records(self.NAME)

    @staticmethod
    def validate(spacer, where="spacer"):
        if not isinstance(spacer, dict):
            raise PetError(f"{where} must be an object {{pattern, kind, note}}")
        pattern = spacer.get("pattern")
        if not isinstance(pattern, str) or len(normalize(pattern)) < MIN_PATTERN:
            raise PetError(f"{where}.pattern must be a string of at least {MIN_PATTERN} characters")
        if spacer.get("kind") not in KINDS:
            raise PetError(f"{where}.kind must be one of {', '.join(KINDS)}")
        note = spacer.get("note", "")
        if not isinstance(note, str):
            raise PetError(f"{where}.note must be a string")
        return {"pattern": pattern, "kind": spacer["kind"], "note": note}

    def add(self, spacer, source, at):
        record = {**self.validate(spacer), "source": source, "at": at}
        if any(normalize(known["pattern"]) == normalize(record["pattern"]) for known in self.all()):
            return None
        self.life.append(self.NAME, record)
        return record

    def matches(self, text):
        haystack = normalize(text)
        return [spacer for spacer in self.all() if normalize(spacer["pattern"]) in haystack]
