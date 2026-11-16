# Protocol

Everyone grows a different pet, so results are comparable only if everyone keeps the same few rules. The engine enforces most of them; the rest is on your honour.

## 1. Shared diary format

`life/diary.jsonl` is written only by the engine:
- one `open` record per cycle: day, program, candidates, chosen task, prediction, model and harness;
- one `close` record per cycle: outcome, branches, skills, lesson, spacer.

Do not edit it by hand.

## 2. Three metrics

`python -m pet report` computes them:

- **Prediction honesty.** Brier score of the chosen task's `p_success` against the outcome: 0 is perfect, 0.25 is a coin. A pet that says 60 % should succeed about 6 times in 10.
- **Skill growth.** A skill counts only after it was used again in at least `reuse_threshold` cycles. Declaring a skill is free; reusing it is evidence.
- **Task difficulty.** Rated 1..5 before the work starts, averaged by week. Without this metric the first two are easy to game by taking easy tasks. The engine also blocks that: candidates must sit at the edge of competence, and the hardest one is taken.

## 3. Control twin

Run a frozen copy (`frozen = true`) of your pet on the same tasks (`tasks --mirror`). Without it nobody can tell evolution from the base model being good. Report both lines of `report --twin`.

## 4. Pinned versions

Fill `[pinned]` and keep the model and the harness for the whole game. Every diary record carries them; `report` warns if they changed. A model upgrade in the middle of the game would pass for evolution.

## 5. Mutation journal

`life/mutations.jsonl` lists every genome mutation:
- the reason it was proposed;
- the verdict: accepted or rejected;
- the evidence: success and Brier before and since;
- every new grammar rule.

`life/generations/` keeps a snapshot of every generation. Share the journal with your results.

## 6. Four weeks and a final review

The game lasts `days = 28`. After the last day the engine refuses new cycles. Then:
1. Run `python -m pet report --twin ...`.
2. Push your repository.
3. Come to the shared review. Like Axelrod's tournament, the interesting part is comparing strategies: whose fractal grew fastest, whose genome held up, which goals made pets develop at all.

Change `[rules]` only before `init`, and say so when you share results.
