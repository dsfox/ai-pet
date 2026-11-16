from pet.errors import PetError

from support import PetCase


class SosTest(PetCase):
    def test_quota_rises_after_four_wins(self):
        for _ in range(3):
            self.run_cycle(success=True)
        self.assertEqual(self.pet.sos_state().quota, 1)
        self.run_cycle(success=True)
        self.assertEqual((self.pet.sos_state().name, self.pet.sos_state().quota), ("too-easy", 3))

    def test_quota_rises_after_four_failures(self):
        for _ in range(4):
            self.run_cycle(success=False)
        self.assertEqual((self.pet.sos_state().name, self.pet.sos_state().quota), ("stuck", 3))

    def test_mixed_outcomes_stay_normal(self):
        for success in (True, True, False, True):
            self.run_cycle(success=success)
        self.assertEqual(self.pet.sos_state().quota, 1)


class MutationTest(PetCase):
    def test_one_mutation_per_day_without_sos(self):
        self.pet.mutate("add", "ask-early", "Ask the human when blocked", "stuck twice")
        with self.assertRaisesRegex(PetError, "quota for today is 1"):
            self.pet.mutate("edit", "small-steps", "Prefer tiny steps", "too slow")
        self.clock.advance(days=1)
        self.pet.mutate("edit", "small-steps", "Prefer tiny steps", "too slow")

    def test_sos_allows_three(self):
        for _ in range(4):
            self.run_cycle(success=True)
        self.pet.mutate("add", "gene-a", "A", "sos")
        self.pet.mutate("add", "gene-b", "B", "sos")
        self.pet.mutate("add", "gene-c", "C", "sos")
        with self.assertRaisesRegex(PetError, "quota"):
            self.pet.mutate("add", "gene-d", "D", "sos")

    def test_immutable_gene_is_refused(self):
        with self.assertRaisesRegex(PetError, "immutable"):
            self.pet.mutate("sleep", "keep-home", None, "it slows me down")

    def test_judge_waits_for_the_trial(self):
        record = self.pet.mutate("add", "ask-early", "Ask the human when blocked", "stuck twice")
        self.run_cycle()
        self.run_cycle()
        with self.assertRaisesRegex(PetError, "needs 3 closed cycles"):
            self.pet.judge(record["id"], "accept", "looks good")
        self.run_cycle()
        self.pet.judge(record["id"], "accept", "helped")
        self.assertEqual(self.pet.genome().generation, 2)
        self.assertTrue((self.root / "life" / "generations" / "002.json").is_file())

    def test_rejected_edit_restores_text_and_keeps_a_sleeping_gene(self):
        record = self.pet.mutate("edit", "small-steps", "Take huge leaps", "faster")
        for _ in range(3):
            self.run_cycle()
        self.pet.judge(record["id"], "reject", "broke more than it fixed")
        genome = self.pet.genome()
        self.assertEqual(genome.find("small-steps")["text"], "Prefer the smallest step that tests the prediction")
        self.assertEqual([gene["text"] for gene in genome.sleeping()], ["Take huge leaps"])
        self.assertEqual(genome.generation, 1)

    def test_rejected_sleep_wakes_the_gene(self):
        record = self.pet.mutate("sleep", "skills", None, "noise")
        self.assertEqual(self.pet.genome().find("skills")["status"], "sleeping")
        for _ in range(3):
            self.run_cycle()
        self.pet.judge(record["id"], "reject", "skills mattered")
        self.assertEqual(self.pet.genome().find("skills")["status"], "active")

    def test_frozen_twin_never_mutates(self):
        twin = self.make_pet(self.make_root("twin", **{"frozen = false": "frozen = true"}))
        with self.assertRaisesRegex(PetError, "frozen"):
            twin.mutate("add", "ask-early", "Ask", "why not")
