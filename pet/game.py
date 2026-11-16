"""Pet: one place that loads the seed and the living state and runs every gate before any change."""
from datetime import date
from pathlib import Path

from .config import PetConfig
from .crispr import SpacerMemory
from .cycle import CycleCloser, Diary, SkillBook, TaskPicker
from .errors import PetError
from .genome import Genome, MutationGate
from .life import Clock, Life
from .lsystem import Grammar, top_level_branches
from .meta import MetaGate
from .metrics import summarize
from .sos import SosRegulator

GRAMMAR = "grammar.json"
SEED = "seed.json"


class Pet:
    def __init__(self, root, clock=None):
        self.root = Path(root).resolve()
        self.clock = clock or Clock()
        self.config = PetConfig.load(self.root / PetConfig.FILE_NAME)
        self.life = Life(self.root)
        self.diary = Diary(self.life)
        self.spacers = SpacerMemory(self.life)
        self.skills = SkillBook(self.life)
        self.mutations = MutationGate(self.life, self.config)
        self.meta_gate = MetaGate(self.life, self.config)
        self.sos = SosRegulator(self.config.rules)

    def init(self):
        if self.life.exists():
            raise PetError("the game has already started: life/ exists")
        now = self.clock.now()
        self.life.write_json(SEED, {"start": now.date().isoformat(), "pet_toml_sha256": self.config.sha256,
                                    "frozen": self.config.frozen})
        genome = Genome.seed(self.config.genes)
        self.life.write_json(Genome.NAME, genome.data)
        self.life.write_json(GRAMMAR, self.config.grammar.to_dict())
        self._snapshot(genome, self.config.grammar)
        return now

    def check(self):
        if not self.life.exists():
            raise PetError("no life/ yet: run `python -m pet init`")
        seed = self.life.read_json(SEED)
        if seed["pet_toml_sha256"] != self.config.sha256:
            raise PetError("pet.toml changed after the game started; the seed is fixed for the whole game, restore it")
        self.genome().check_immutable(self.config.genes)
        self.grammar()
        return seed

    def genome(self):
        return Genome(self.life.read_json(Genome.NAME))

    def grammar(self):
        return Grammar.from_dict(self.life.read_json(GRAMMAR))

    def day(self):
        start = date.fromisoformat(self.life.read_json(SEED)["start"])
        return (self.clock.now().date() - start).days + 1

    def depth(self, day):
        return 1 + (day - 1) // self.config.depth_every_days

    def sos_state(self):
        return self.sos.state([cycle.success for cycle in self.diary.closed()])

    def open_cycle(self, candidates):
        self.check()
        if self.config.frozen:
            raise PetError("a frozen twin does not choose tasks: use `tasks --mirror <path to the main pet>`")
        self._require_no_open_cycle()
        self._require_playing()
        chosen, clean = TaskPicker(self.config, self.spacers).pick(candidates)
        return self._open(chosen, clean, None)

    def mirror_cycle(self, main_root, p_success, expect):
        self.check()
        if not self.config.frozen:
            raise PetError("only a frozen twin mirrors tasks; set [game] frozen = true in the twin's pet.toml")
        self._require_no_open_cycle()
        self._require_playing()
        mirrored = {cycle.opened.get("mirror_of") for cycle in self.diary.cycles()}
        source = next((cycle for cycle in Diary(Life(main_root)).cycles() if cycle.id not in mirrored), None)
        if source is None:
            raise PetError("the main pet has no new task to mirror")
        if isinstance(p_success, bool) or not isinstance(p_success, (int, float)) or not 0 <= p_success <= 1:
            raise PetError("--p must be a probability 0..1")
        if not expect or not expect.strip():
            raise PetError("--expect must say what you expect")
        chosen = {**source.opened["chosen"], "p_success": float(p_success), "expect": expect.strip()}
        return self._open(chosen, [], source.id)

    def _open(self, chosen, candidates, mirror_of):
        now, day = self.clock.now(), self.day()
        cycle_id = self.diary.next_id()
        program, truncated = self.grammar().expand(self.depth(day), seed=f"{day}:{cycle_id}")
        record = {"event": "open", "id": cycle_id, "at": now.isoformat(), "day": day, "depth": self.depth(day),
                  "program": program, "truncated": truncated, "branches": top_level_branches(program),
                  "candidates": candidates, "chosen": chosen, "mirror_of": mirror_of,
                  "model": self.config.model, "harness": self.config.harness}
        self.diary.append(record)
        return record

    def close_cycle(self, cycle_id, result):
        self.check()
        cycle = self.diary.open_cycle()
        if cycle is None or cycle.id != cycle_id:
            raise PetError(f"{cycle_id} is not the open cycle")
        closed = CycleCloser(self.skills).validate(cycle, result)
        now = self.clock.now().isoformat()
        record = {"event": "close", "id": cycle_id, "at": now, **closed,
                  "model": self.config.model, "harness": self.config.harness}
        self.diary.append(record)
        if closed["new_skill"]:
            self.skills.add(closed["new_skill"], cycle_id, now)
        if closed["spacer"]:
            self.spacers.add(closed["spacer"], cycle_id, now)
        return record

    def mutate(self, operation, gene_id, text, reason):
        self.check()
        genome = self.genome()
        record = self.mutations.propose(genome, operation, gene_id, text, reason, self.sos_state().quota,
                                        self.clock.now(), len(self.diary.closed()))
        self.life.write_json(Genome.NAME, genome.data)
        return record

    def judge(self, mutation_id, verdict, reason):
        self.check()
        closed = self.diary.closed()
        proposal = next((record for record in self.mutations.pending() if record["id"] == mutation_id), None)
        split = proposal["closed_at_propose"] if proposal else len(closed)
        evidence = {"before": summarize(closed[:split]), "since": summarize(closed[split:])}
        genome = self.genome()
        record = self.mutations.judge(genome, mutation_id, verdict, reason, self.clock.now(), len(closed), evidence)
        self.life.write_json(Genome.NAME, genome.data)
        if verdict == "accept":
            self._snapshot(genome, self.grammar())
        return record

    def meta(self, symbol, to, weight, define, reason):
        self.check()
        grammar, record = self.meta_gate.write(self.grammar(), self.diary.open_cycle(), symbol, to, weight, define,
                                               reason, self.clock.now())
        self.life.write_json(GRAMMAR, grammar.to_dict())
        genome = self.genome()
        genome.data["generation"] += 1
        self.life.write_json(Genome.NAME, genome.data)
        self._snapshot(genome, grammar)
        return record

    def crispr_add(self, spacer):
        self.check()
        return self.spacers.add(spacer, "manual", self.clock.now().isoformat())

    def status(self):
        self.check()
        day, sos = self.day(), self.sos_state()
        today = self.clock.now().date().isoformat()
        cycle = self.diary.open_cycle()
        closed_count = len(self.diary.closed())
        if cycle is None:
            preview, _ = self.grammar().expand(self.depth(day), seed=f"{day}:{self.diary.next_id()}")
        return {
            "day": day, "days": self.config.days, "depth": self.depth(day), "frozen": self.config.frozen,
            "sos": sos, "mutations_used": len(self.mutations.proposed_on(today)),
            "open": None if cycle is None else {"cycle": cycle, "meta_left": self.meta_gate.quota(cycle)},
            "next_program": preview if cycle is None else None,
            "goals": self.config.goals, "genome": self.genome(),
            "pending": [{"id": record["id"], "op": record["op"], "gene": record["gene"],
                         "waited": closed_count - record["closed_at_propose"]} for record in self.mutations.pending()],
            "trial_cycles": self.config.rules.trial_cycles,
            "alphabet": self.grammar().alphabet,
        }

    def _require_no_open_cycle(self):
        cycle = self.diary.open_cycle()
        if cycle is not None:
            raise PetError(f"cycle {cycle.id} is still open: close it first")

    def _require_playing(self):
        day = self.day()
        if day > self.config.days:
            raise PetError(f"the game is over (day {day} of {self.config.days}): run `python -m pet report`")
        if day < 1:
            raise PetError("the clock is before the start of the game")

    def _snapshot(self, genome, grammar):
        self.life.save_generation(genome.generation, {"generation": genome.generation, "at": self.clock.now().isoformat(),
                                                      "genome": genome.data, "grammar": grammar.to_dict()})
