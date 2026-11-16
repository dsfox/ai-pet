import unittest

from pet.config import CORE_ALPHABET
from pet.errors import PetError
from pet.lsystem import Grammar, Production, is_balanced, top_level_branches

ALPHABET = {**CORE_ALPHABET, "X": "base"}


def grammar(rules, axiom="X", max_length=80):
    return Grammar(axiom, ALPHABET, {symbol: [Production(to, weight) for to, weight in alts] for symbol, alts in rules.items()}, max_length)


class LSystemTest(unittest.TestCase):
    def test_same_seed_same_program(self):
        word = grammar({"X": [("GHA", 1)], "A": [("A", 1), ("[OA]C", 1)]})
        self.assertEqual(word.expand(5, "3:c0001"), word.expand(5, "3:c0001"))

    def test_weights_choose_alternatives(self):
        word = grammar({"X": [("A", 1)], "A": [("O", 1), ("P", 1)]})
        programs = {word.expand(2, seed)[0] for seed in range(40)}
        self.assertEqual(programs, {"O", "P"})

    def test_explosion_stops_at_last_word_that_fits(self):
        word = grammar({"X": [("XX", 1)]}, max_length=10)
        program, truncated = word.expand(20, 0)
        self.assertTrue(truncated)
        self.assertEqual(program, "X" * 8)

    def test_brackets_stay_balanced(self):
        word = grammar({"X": [("GHA", 1)], "A": [("A", 0.5), ("[OA][OA]C", 0.5)]}, max_length=200)
        for seed in range(30):
            self.assertTrue(is_balanced(word.expand(4, seed)[0]))

    def test_top_level_branches_keep_nested_ones_inside(self):
        self.assertEqual(top_level_branches("GH[O[OA]A]P[OA]C"), ["O[OA]A", "OA"])
        self.assertEqual(top_level_branches("GHOPACLT"), [])

    def test_unknown_symbol_is_refused(self):
        with self.assertRaises(PetError):
            grammar({"X": [("GQ", 1)]}).validate()

    def test_unbalanced_rule_is_refused(self):
        with self.assertRaises(PetError):
            grammar({"X": [("[GH", 1)]}).validate()

    def test_non_positive_weight_is_refused(self):
        with self.assertRaises(PetError):
            grammar({"X": [("GH", 0)]}).validate()

    def test_round_trip_through_dict(self):
        word = grammar({"X": [("GHA", 1)], "A": [("A", 0.6), ("[OA]C", 0.4)]})
        copy = Grammar.from_dict(word.to_dict())
        self.assertEqual(copy.expand(4, 9), word.expand(4, 9))


if __name__ == "__main__":
    unittest.main()
