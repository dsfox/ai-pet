"""One cycle: G picks candidates, H takes the hardest, C and L close it with the outcome."""
from dataclasses import dataclass

from .crispr import SpacerMemory
from .errors import PetError

DIFFICULTY = range(1, 6)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(record, key, where):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PetError(f"{where}.{key} must be a non-empty string")
    return value.strip()


@dataclass
class Cycle:
    opened: dict
    closed: dict | None = None

    @property
    def id(self):
        return self.opened["id"]

    @property
    def is_open(self):
        return self.closed is None

    @property
    def success(self):
        return None if self.closed is None else self.closed["success"]

    @property
    def p_success(self):
        return self.opened["chosen"]["p_success"]


class Diary:
    NAME = "diary.jsonl"

    def __init__(self, life):
        self.life = life

    def cycles(self):
        cycles = {}
        for record in self.life.records(self.NAME):
            if record["event"] == "open":
                cycles[record["id"]] = Cycle(record)
            elif record["event"] == "close":
                cycles[record["id"]].closed = record
        return list(cycles.values())

    def open_cycle(self):
        return next((cycle for cycle in self.cycles() if cycle.is_open), None)

    def closed(self):
        return [cycle for cycle in self.cycles() if not cycle.is_open]

    def next_id(self):
        return f"c{len(self.cycles()) + 1:04d}"

    def append(self, record):
        self.life.append(self.NAME, record)


class SkillBook:
    NAME = "skills.jsonl"

    def __init__(self, life):
        self.life = life

    def names(self):
        return {record["name"] for record in self.life.records(self.NAME)}

    def add(self, skill, cycle_id, at):
        self.life.append(self.NAME, {**skill, "born_in": cycle_id, "at": at})


class TaskPicker:
    def __init__(self, config, spacers):
        self.config = config
        self.spacers = spacers

    def pick(self, candidates):
        rules = self.config.rules
        if not isinstance(candidates, list) or len(candidates) != rules.top_n:
            raise PetError(f"G: submit exactly {rules.top_n} candidate tasks")
        clean = [self._candidate(raw, index) for index, raw in enumerate(candidates)]
        tasks = [candidate["task"].casefold() for candidate in clean]
        if len(set(tasks)) != len(tasks):
            raise PetError("G: candidate tasks must be different")
        for index, candidate in enumerate(clean):
            hits = self.spacers.matches(candidate["task"])
            if hits:
                raise PetError(f"R: candidate {index + 1} matches spacer {hits[0]['pattern']!r} ({hits[0]['kind']}); replace it")
        position = min(range(len(clean)), key=lambda index: (-clean[index]["difficulty"], clean[index]["p_success"], index))
        return clean[position], clean

    def _candidate(self, raw, index):
        where = f"candidate {index + 1}"
        if not isinstance(raw, dict):
            raise PetError(f"{where} must be an object")
        rules = self.config.rules
        candidate = {"task": _text(raw, "task", where), "goal": raw.get("goal"), "expect": _text(raw, "expect", where)}
        if candidate["goal"] not in self.config.goal_ids():
            raise PetError(f"{where}.goal must be one of: {', '.join(sorted(self.config.goal_ids()))}")
        difficulty = raw.get("difficulty")
        if not isinstance(difficulty, int) or isinstance(difficulty, bool) or difficulty not in DIFFICULTY:
            raise PetError(f"{where}.difficulty must be an integer 1..5")
        probability = raw.get("p_success")
        if not _number(probability) or not rules.edge_low <= probability <= rules.edge_high:
            raise PetError(
                f"{where}.p_success must be within the edge of competence "
                f"[{rules.edge_low}, {rules.edge_high}]; easier or hopeless tasks do not count")
        candidate.update(difficulty=difficulty, p_success=float(probability))
        return candidate


class CycleCloser:
    def __init__(self, skills):
        self.skills = skills

    def validate(self, cycle, result):
        where = "result"
        if not isinstance(result, dict):
            raise PetError("result must be an object")
        if not isinstance(result.get("success"), bool):
            raise PetError("result.success must be true or false")
        closed = {
            "success": result["success"],
            "outcome": _text(result, "outcome", where),
            "lesson": _text(result, "lesson", where),
        }
        closed.update(self._branches(cycle, result))
        closed["skills_used"] = self._skills_used(result)
        closed["new_skill"] = self._new_skill(result)
        spacer = result.get("spacer")
        if spacer is None and not closed["success"]:
            raise PetError("L: a failed cycle must leave a CRISPR spacer {pattern, kind, note}")
        closed["spacer"] = None if spacer is None else SpacerMemory.validate(spacer, "result.spacer")
        return closed

    @staticmethod
    def _branches(cycle, result):
        expected = cycle.opened["branches"]
        branches = result.get("branches", [])
        if not isinstance(branches, list) or len(branches) != len(expected):
            raise PetError(f"C: the program had {len(expected)} parallel branches; report each one in result.branches")
        names = []
        for index, branch in enumerate(branches):
            where = f"result.branches[{index}]"
            if not isinstance(branch, dict):
                raise PetError(f"{where} must be an object {{name, score, note}}")
            names.append(_text(branch, "name", where))
            if not _number(branch.get("score")) or not 0 <= branch["score"] <= 1:
                raise PetError(f"{where}.score must be a number 0..1")
        if len(set(names)) != len(names):
            raise PetError("C: branch names must be different")
        merged = result.get("merged")
        if expected and merged not in names:
            raise PetError("C: result.merged must name the branch you merged back")
        if not expected and merged is not None:
            raise PetError("C: there were no branches to merge")
        return {"branches": branches, "merged": merged}

    def _skills_used(self, result):
        used = result.get("skills_used", [])
        if not isinstance(used, list) or not all(isinstance(name, str) for name in used):
            raise PetError("result.skills_used must be a list of skill names")
        unknown = sorted(set(used) - self.skills.names())
        if unknown:
            raise PetError(f"unknown skills {', '.join(unknown)}: a skill exists only after a cycle declares it in new_skill")
        return sorted(set(used))

    def _new_skill(self, result):
        skill = result.get("new_skill")
        if skill is None:
            return None
        if not isinstance(skill, dict):
            raise PetError("result.new_skill must be an object {name, how}")
        clean = {"name": _text(skill, "name", "result.new_skill"), "how": _text(skill, "how", "result.new_skill")}
        if clean["name"] in self.skills.names():
            raise PetError(f"skill {clean['name']!r} already exists; list it in skills_used instead")
        return clean
