# AI Pet

A game of three words for people who run AI agents. Take any agent harness (Claude Code, Codex, hermes-agent, or your own), give it three words, and watch for four weeks what it grows into.

- **Fractal**: how it grows. A simple rule applied to its own result again and again.
- **Genome**: what it grows from. Starting rules it follows, mutates and passes on.
- **Goals**: why it grows. Without a goal it refuses to develop. You choose the goal.

This repository is the starting kit. You write one file, `pet.toml`. The engine `pet/` enforces the rules with code, so every participant plays the same game and the results can be compared.

## Three steps

1. **Copy the template.** Use "Use this template" on GitHub or `git clone`, one folder per pet. Python 3.11+ is the only requirement.
2. **Write `pet.toml`.**
   - `[pinned]`: your model and harness, fixed for the whole game.
   - `[fractal]`: your L-system. An axiom and rewrite rules over the letters of a work cycle.
   - `[[genome.genes]]`: your starting rules; mark the ones that must never change `immutable = true`.
   - `[[goals]]`: what your pet should become good at.
3. **Start.** Run `python -m pet init`, then tell your agent: *"Read AGENTS.md and live by it."* Commit `life/` every day.

The example `pet.toml` is playable once `[pinned]` is filled in. Run it unchanged first if you want to see the game before designing your own.

## What grows

Each cycle the engine rewrites your axiom `depth` times; depth rises by one every `depth_every_days`. With the example rules:

```
day 1   GHROPACLT
day 4   GHROP[OA][OA]CCLT
day 10  GHROP[O[OA][OA]C][OA]CCLMMT
```

The programs are random draws with a seed; these three are real output of the example rules.

Five mechanics are built in:

| Mechanic | Rule | Enforced by |
|---|---|---|
| Edge of competence | G lists 5 tasks, each with a 50–70 % chance of success; H takes the hardest | `tasks` refuses easier or hopeless candidates and picks itself |
| Parallel branches | every `[ ]` is a real sub-agent; the best attempt is merged back | `close` requires a score for each branch and the merged one |
| Rules that write rules | each M lets the pet add a rewrite rule or a new letter for a skill | `meta` counts the Ms of the open cycle |
| SOS response | 4 wins or 4 losses in a row raise the daily mutation quota from 1 to 3, like stressed bacteria | `mutate` checks the quota |
| CRISPR memory | every failure leaves a spacer, a short signature that recognises the same trap or a hostile input next time | `close` refuses a failure without one; `tasks` refuses matching candidates |

## Commands

```
python -m pet init                 start the game, freeze pet.toml
python -m pet today                day, program, SOS state, goals, genes
python -m pet tasks FILE           G + H + R: open a cycle
python -m pet close ID FILE        C + L: record the outcome
python -m pet mutate OP GENE ...   one genome mutation on trial
python -m pet judge ID accept|reject --reason ...
python -m pet meta --symbol S --to "..." [--define K "meaning"] --reason ...
python -m pet crispr add|check ...
python -m pet report [--twin PATH] the protocol metrics
python -m pet check                seed, immutable genes, grammar
```

Examples of the JSON inputs are in `examples/`. Tests: `python -m unittest discover -s tests`.

## Control twin

Copy your folder before `init`, set `frozen = true` in the copy and start it too. The twin never mutates; it takes the same tasks as your pet with `tasks --mirror ../my-pet`. Then `report --twin ../my-twin` shows whether evolution adds anything over the bare model.

Rules for comparing results: [PROTOCOL.md](PROTOCOL.md).
