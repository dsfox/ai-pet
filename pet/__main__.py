"""Command line: python -m pet <command>. A refused rule prints the reason and exits with code 2."""
import argparse
import json
import sys
from pathlib import Path

from .errors import PetError
from .game import Pet
from .metrics import Report

REFUSED = 2
SPACER_HIT = 1


class Cli:
    def __init__(self, args):
        self.args = args
        self.pet = Pet(args.root)

    def run(self):
        return getattr(self, f"cmd_{self.args.command}")()

    def cmd_init(self):
        self.pet.init()
        print(f"life/ created. Day 1 of {self.pet.config.days}. Next: python -m pet today")

    def cmd_check(self):
        self.pet.check()
        print("ok: seed intact, immutable genes intact, grammar valid")

    def cmd_today(self):
        status = self.pet.status()
        sos = status["sos"]
        print(f"day {status['day']} of {status['days']}, depth {status['depth']}{'  [frozen twin]' if status['frozen'] else ''}")
        print(f"SOS: {sos.name} ({sos.reason}); mutations today {status['mutations_used']}/{sos.quota}")
        if status["open"]:
            cycle = status["open"]["cycle"]
            print(f"open cycle {cycle.id}: {cycle.opened['chosen']['task']}")
            self._program(cycle.opened["program"], status["alphabet"])
            print(f"M left in this cycle: {status['open']['meta_left']}")
        else:
            print("no open cycle. Next program if you open one now:")
            self._program(status["next_program"], status["alphabet"])
        print("goals:")
        for goal in status["goals"]:
            print(f"  {goal.id}: {goal.text}")
        print("active genes:")
        for gene in status["genome"].active():
            marks = " [immutable]" if gene["immutable"] else (f" [trial {gene['pending']}]" if gene["pending"] else "")
            print(f"  {gene['id']}{marks}: {gene['text']}")
        print(f"sleeping genes: {len(status['genome'].sleeping())}")
        for pending in status["pending"]:
            ready = "ready to judge" if pending["waited"] >= status["trial_cycles"] else f"{pending['waited']}/{status['trial_cycles']} cycles"
            print(f"mutation {pending['id']} ({pending['op']} {pending['gene']}): {ready}")

    @staticmethod
    def _program(program, alphabet):
        print(f"  program: {program}")
        used = [letter for letter in alphabet if letter in program]
        print("  " + "; ".join(f"{letter} = {alphabet[letter].split(':')[0]}" for letter in used))

    def cmd_tasks(self):
        if self.args.mirror:
            record = self.pet.mirror_cycle(Path(self.args.mirror), self.args.p, self.args.expect)
        else:
            if not self.args.file:
                raise PetError("tasks needs a JSON file with the candidates, or --mirror for a twin")
            record = self.pet.open_cycle(self._json(self.args.file))
        chosen = record["chosen"]
        print(f"opened {record['id']} (day {record['day']}, depth {record['depth']})")
        print(f"H: {chosen['task']}  [goal {chosen['goal']}, difficulty {chosen['difficulty']}, p={chosen['p_success']}]")
        print(f"P: {chosen['expect']}")
        print(f"program: {record['program']}{'  (truncated at max_length)' if record['truncated'] else ''}")
        for index, branch in enumerate(record["branches"], 1):
            print(f"branch {index}: [{branch}]  -> run as a separate sub-agent")
        if record["program"].count("M"):
            print(f"M: you may write {record['program'].count('M')} new rule(s) in this cycle")

    def cmd_close(self):
        record = self.pet.close_cycle(self.args.id, self._json(self.args.file))
        print(f"closed {record['id']}: {'success' if record['success'] else 'failure'}")
        if record["spacer"]:
            print(f"CRISPR spacer stored: {record['spacer']['pattern']!r}")
        sos = self.pet.sos_state()
        print(f"SOS now: {sos.name}, mutation quota {sos.quota}")

    def cmd_mutate(self):
        record = self.pet.mutate(self.args.op, self.args.gene, self.args.text, self.args.reason)
        print(f"{record['id']}: {record['op']} {record['gene']} on trial for {self.pet.config.rules.trial_cycles} cycles")

    def cmd_judge(self):
        record = self.pet.judge(self.args.id, self.args.verdict, self.args.reason)
        evidence = record["evidence"]
        print(f"{record['id']}: {record['verdict']}ed. before {evidence['before']}, since {evidence['since']}")
        print(f"generation {self.pet.genome().generation}")

    def cmd_meta(self):
        define = tuple(self.args.define) if self.args.define else None
        record = self.pet.meta(self.args.symbol, self.args.to, self.args.weight, define, self.args.reason)
        print(f"new rule {record['symbol']} -> {record['to']} (weight {record['weight']}); generation {self.pet.genome().generation}")

    def cmd_crispr(self):
        if self.args.action == "add":
            record = self.pet.crispr_add({"pattern": self.args.pattern, "kind": self.args.kind, "note": self.args.note or ""})
            print("stored" if record else "already known")
            return 0
        self.pet.check()
        text = Path(self.args.file).read_text(encoding="utf-8") if self.args.file else (self.args.text or "")
        hits = self.pet.spacers.matches(text)
        for hit in hits:
            print(f"MATCH {hit['kind']}: {hit['pattern']!r} {hit['note']}")
        if not hits:
            print("clean")
        return SPACER_HIT if hits else 0

    def cmd_report(self):
        self.pet.check()
        twin = Pet(self.args.twin) if self.args.twin else None
        print("\n".join(Report(self.pet, twin).lines()))

    @staticmethod
    def _json(source):
        raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise PetError(f"{source}: invalid JSON: {error}") from error


def parser():
    root = argparse.ArgumentParser(prog="python -m pet", description="AI Pet: fractal, genome, goals")
    root.add_argument("--root", default=".", help="folder with pet.toml (default: current folder)")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="start the game: create life/ from pet.toml")
    commands.add_parser("check", help="verify seed, immutable genes and grammar")
    commands.add_parser("today", help="day, program, SOS state, goals and genes")
    tasks = commands.add_parser("tasks", help="G+H+R: submit candidates, the engine takes the hardest")
    tasks.add_argument("file", nargs="?", help="JSON list of candidates, or - for stdin")
    tasks.add_argument("--mirror", help="twin only: path to the main pet")
    tasks.add_argument("--p", type=float, help="twin only: your own success probability")
    tasks.add_argument("--expect", help="twin only: what you expect")
    close = commands.add_parser("close", help="C+L: record the outcome of the open cycle")
    close.add_argument("id")
    close.add_argument("file", help="JSON result, or - for stdin")
    mutate = commands.add_parser("mutate", help="propose one genome mutation")
    mutate.add_argument("op", choices=["add", "edit", "sleep", "wake"])
    mutate.add_argument("gene")
    mutate.add_argument("--text")
    mutate.add_argument("--reason", required=True)
    judge = commands.add_parser("judge", help="accept or reject a mutation after its trial")
    judge.add_argument("id")
    judge.add_argument("verdict", choices=["accept", "reject"])
    judge.add_argument("--reason", required=True)
    meta = commands.add_parser("meta", help="M: add a rewrite rule to your grammar")
    meta.add_argument("--symbol", required=True)
    meta.add_argument("--to", required=True)
    meta.add_argument("--weight", type=float, default=1.0)
    meta.add_argument("--define", nargs=2, metavar=("LETTER", "MEANING"), help="introduce a new letter")
    meta.add_argument("--reason", required=True)
    crispr = commands.add_parser("crispr", help="CRISPR memory of errors and hostile inputs")
    crispr.add_argument("action", choices=["add", "check"])
    crispr.add_argument("--pattern")
    crispr.add_argument("--kind", choices=["error", "injection"])
    crispr.add_argument("--note")
    crispr.add_argument("--text")
    crispr.add_argument("--file")
    report = commands.add_parser("report", help="the protocol metrics")
    report.add_argument("--twin", help="path to the frozen control twin")
    return root


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        return Cli(args).run() or 0
    except PetError as error:
        print(f"refused: {error}", file=sys.stderr)
        return REFUSED


if __name__ == "__main__":
    sys.exit(main())
