"""The three protocol metrics plus growth, version drift and the twin comparison."""
from collections import Counter, defaultdict


def summarize(cycles):
    """Success rate and Brier score (0 is perfect, 0.25 is a coin) of closed cycles."""
    closed = [cycle for cycle in cycles if not cycle.is_open]
    if not closed:
        return {"n": 0, "success_rate": None, "brier": None}
    successes = sum(cycle.success for cycle in closed)
    brier = sum((cycle.p_success - cycle.success) ** 2 for cycle in closed) / len(closed)
    return {"n": len(closed), "success_rate": round(successes / len(closed), 3), "brier": round(brier, 3)}


def _fmt(stats):
    if not stats["n"]:
        return "no closed cycles"
    return f"n={stats['n']}  success={stats['success_rate']:.0%}  brier={stats['brier']:.3f}"


def _week(day):
    return (day - 1) // 7 + 1


class Report:
    def __init__(self, pet, twin=None):
        self.pet = pet
        self.twin = twin

    def lines(self):
        pet = self.pet
        cycles = pet.diary.cycles()
        out = [f"AI Pet report: day {pet.day()} of {pet.config.days}, generation {pet.genome().generation}", ""]
        out += ["1. Prediction honesty", f"   {_fmt(summarize(cycles))}", ""]
        out += ["2. Skill growth (a skill counts once it is reused)"] + self._skills(cycles) + [""]
        out += ["3. Task difficulty (chosen task, mean 1..5, by week)"] + self._difficulty(cycles) + [""]
        out += ["Growth of the fractal"] + self._growth(cycles) + [""]
        out += ["Mutation journal"] + self._mutations() + [""]
        out += ["Pinned versions"] + self._pinned() + [""]
        if self.twin is not None:
            out += ["Control twin (same tasks)"] + self._twin(cycles) + [""]
        return out

    def _skills(self, cycles):
        uses = Counter(name for cycle in cycles if cycle.closed for name in cycle.closed["skills_used"])
        names = sorted(self.pet.skills.names())
        threshold = self.pet.config.rules.reuse_threshold
        reused = [name for name in names if uses[name] >= threshold]
        rows = [f"   declared {len(names)}, reused >= {threshold} times: {len(reused)}"]
        rows += [f"   {name}: used {uses[name]}x" for name in names]
        return rows

    @staticmethod
    def _difficulty(cycles):
        by_week = defaultdict(list)
        for cycle in cycles:
            by_week[_week(cycle.opened["day"])].append(cycle.opened["chosen"]["difficulty"])
        if not by_week:
            return ["   no cycles yet"]
        return [f"   week {week}: {sum(values) / len(values):.2f} over {len(values)} cycles" for week, values in sorted(by_week.items())]

    def _growth(self, cycles):
        seed, now = self.pet.config.grammar, self.pet.grammar()
        rows = [f"   rules: {seed.production_count()} -> {now.production_count()}, letters: {len(seed.alphabet)} -> {len(now.alphabet)}"]
        by_week = defaultdict(list)
        for cycle in cycles:
            by_week[_week(cycle.opened["day"])].append(len(cycle.opened["program"]))
        rows += [f"   week {week}: program length {sum(values) / len(values):.1f}, max {max(values)}" for week, values in sorted(by_week.items())]
        return rows

    def _mutations(self):
        journal = self.pet.mutations.journal()
        verdicts = Counter(record["verdict"] for record in journal if record["event"] == "judge")
        proposed = sum(record["event"] == "propose" for record in journal)
        metas = sum(record["event"] == "meta" for record in journal)
        spacers = Counter(spacer["kind"] for spacer in self.pet.spacers.all())
        return [f"   genome mutations proposed {proposed}: accepted {verdicts['accept']}, rejected {verdicts['reject']}, "
                f"on trial {len(self.pet.mutations.pending())}",
                f"   new grammar rules (M): {metas}",
                f"   CRISPR spacers: {spacers['error']} errors, {spacers['injection']} injections"]

    def _pinned(self):
        versions = Counter((record["model"], record["harness"]) for record in self.pet.life.records("diary.jsonl"))
        if len(versions) <= 1:
            return [f"   stable: {self.pet.config.model} / {self.pet.config.harness}"]
        return ["   WARNING: model or harness changed during the game; growth is not comparable"] + [
            f"   {model} / {harness}: {count} records" for (model, harness), count in versions.items()]

    def _twin(self, cycles):
        mirrored = {cycle.opened.get("mirror_of"): cycle for cycle in self.twin.diary.cycles() if not cycle.is_open}
        pairs = [(cycle, mirrored[cycle.id]) for cycle in cycles if not cycle.is_open and cycle.id in mirrored]
        if not pairs:
            return ["   no matched closed cycles yet"]
        return [f"   evolving pet: {_fmt(summarize([main for main, _ in pairs]))}",
                f"   frozen twin:  {_fmt(summarize([twin for _, twin in pairs]))}"]
