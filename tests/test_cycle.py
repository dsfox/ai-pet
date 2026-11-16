from pet.errors import PetError

from support import PetCase, candidates, result


class TaskChoiceTest(PetCase):
    def test_engine_takes_the_hardest(self):
        record = self.pet.open_cycle(candidates(difficulties=(2, 5, 3, 5, 1), probabilities=(0.6, 0.6, 0.6, 0.55, 0.7)))
        self.assertEqual(record["chosen"]["task"], "task 3")

    def test_tie_goes_to_the_first(self):
        record = self.pet.open_cycle(candidates(difficulties=(4, 4, 4, 4, 4), probabilities=(0.6,) * 5))
        self.assertEqual(record["chosen"]["task"], "task 0")

    def test_exactly_top_n_candidates(self):
        with self.assertRaisesRegex(PetError, "exactly 5"):
            self.pet.open_cycle(candidates()[:4])

    def test_candidates_outside_the_edge_are_refused(self):
        for probability in (0.9, 0.2):
            with self.assertRaisesRegex(PetError, "edge of competence"):
                self.pet.open_cycle(candidates(probabilities=(0.6, 0.6, probability, 0.6, 0.6)))

    def test_unknown_goal_is_refused(self):
        with self.assertRaisesRegex(PetError, "goal must be one of"):
            self.pet.open_cycle(candidates(goal="world-domination"))

    def test_difficulty_out_of_range_is_refused(self):
        with self.assertRaisesRegex(PetError, "difficulty"):
            self.pet.open_cycle(candidates(difficulties=(1, 2, 3, 4, 6)))

    def test_duplicate_tasks_are_refused(self):
        tasks = candidates()
        tasks[1]["task"] = "TASK 0"
        with self.assertRaisesRegex(PetError, "different"):
            self.pet.open_cycle(tasks)

    def test_second_open_cycle_is_refused(self):
        self.pet.open_cycle(candidates())
        with self.assertRaisesRegex(PetError, "still open"):
            self.pet.open_cycle(candidates())

    def test_game_is_over_after_the_last_day(self):
        self.clock.advance(days=28)
        with self.assertRaisesRegex(PetError, "game is over"):
            self.pet.open_cycle(candidates())

    def test_depth_grows_with_days(self):
        self.assertEqual(self.pet.open_cycle(candidates())["depth"], 1)
        self.clock.advance(days=6)
        self.assertEqual(self.pet.depth(self.pet.day()), 3)


class CloseTest(PetCase):
    def open_with_branches(self):
        for _ in range(60):
            record = self.pet.open_cycle(candidates())
            if record["branches"]:
                return record
            self.pet.close_cycle(record["id"], result(record))
        self.fail("the template grammar never produced a branch")

    def setUp(self):
        super().setUp()
        self.clock.advance(days=3)

    def test_failure_needs_a_spacer(self):
        record = self.pet.open_cycle(candidates())
        data = result(record, success=False)
        del data["spacer"]
        with self.assertRaisesRegex(PetError, "spacer"):
            self.pet.close_cycle(record["id"], data)

    def test_failure_spacer_is_stored(self):
        record = self.pet.open_cycle(candidates())
        self.pet.close_cycle(record["id"], result(record, success=False))
        self.assertEqual(len(self.pet.spacers.all()), 1)

    def test_each_branch_must_be_reported(self):
        record = self.open_with_branches()
        data = result(record)
        data["branches"] = data["branches"][:-1]
        with self.assertRaisesRegex(PetError, "parallel branches"):
            self.pet.close_cycle(record["id"], data)

    def test_merged_branch_must_exist(self):
        record = self.open_with_branches()
        with self.assertRaisesRegex(PetError, "merged"):
            self.pet.close_cycle(record["id"], result(record, merged="nonexistent"))

    def test_skill_must_be_declared_before_use(self):
        record = self.pet.open_cycle(candidates())
        with self.assertRaisesRegex(PetError, "unknown skills"):
            self.pet.close_cycle(record["id"], result(record, skills_used=["search"]))
        self.pet.close_cycle(record["id"], result(record, new_skill={"name": "search", "how": "type and press enter"}))
        record = self.pet.open_cycle(candidates())
        self.pet.close_cycle(record["id"], result(record, skills_used=["search"]))

    def test_wrong_cycle_id_is_refused(self):
        record = self.pet.open_cycle(candidates())
        with self.assertRaisesRegex(PetError, "not the open cycle"):
            self.pet.close_cycle("c9999", result(record))
