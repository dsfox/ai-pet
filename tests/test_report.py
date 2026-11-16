from pet.cycle import Cycle
from pet.errors import PetError
from pet.metrics import Report, summarize

from support import PetCase


def cycle(p_success, success):
    return Cycle({"chosen": {"p_success": p_success}}, {"success": success})


class BrierTest(PetCase):
    def test_known_numbers(self):
        stats = summarize([cycle(0.6, True), cycle(0.6, False), cycle(0.5, True)])
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["brier"], round((0.16 + 0.36 + 0.25) / 3, 3))
        self.assertAlmostEqual(stats["success_rate"], 0.667)

    def test_empty(self):
        self.assertEqual(summarize([])["n"], 0)


class ReportTest(PetCase):
    def test_report_shows_reused_skills(self):
        self.run_cycle(new_skill={"name": "search", "how": "type, enter"})
        self.run_cycle(skills_used=["search"])
        self.run_cycle(skills_used=["search"])
        text = "\n".join(Report(self.pet).lines())
        self.assertIn("reused >= 2 times: 1", text)

    def test_changed_versions_are_flagged(self):
        self.run_cycle()
        self.assertNotIn("WARNING", "\n".join(Report(self.pet).lines()))
        self.pet.life.append("diary.jsonl", {"event": "note", "model": "test-model-2", "harness": "test-harness-1"})
        self.assertIn("WARNING", "\n".join(Report(self.pet).lines()))

    def test_twin_compares_on_the_same_tasks(self):
        twin = self.make_pet(self.make_root("twin", **{"frozen = false": "frozen = true"}))
        with self.assertRaisesRegex(PetError, "--mirror"):
            twin.open_cycle([])
        with self.assertRaisesRegex(PetError, "no new task"):
            twin.mirror_cycle(self.root, 0.6, "it works")
        main = self.run_cycle(success=True)
        mirrored = twin.mirror_cycle(self.root, 0.6, "it works")
        self.assertEqual(mirrored["mirror_of"], main["id"])
        self.assertEqual(mirrored["chosen"]["task"], main["chosen"]["task"])
        twin.close_cycle(mirrored["id"], {"success": False, "outcome": "x", "lesson": "y",
                                          "branches": [{"name": f"b{i}", "score": 0} for i, _ in enumerate(mirrored["branches"])],
                                          "merged": "b0" if mirrored["branches"] else None,
                                          "spacer": {"pattern": "twin failure", "kind": "error", "note": ""}})
        text = "\n".join(Report(self.pet, twin).lines())
        self.assertIn("evolving pet: n=1  success=100%", text)
        self.assertIn("frozen twin:  n=1  success=0%", text)
