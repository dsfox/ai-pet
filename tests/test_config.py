import json

from pet.config import PetConfig
from pet.errors import PetError
from pet.game import Pet

from support import REPO, PetCase, seed_toml


class TemplateTest(PetCase):
    def test_template_refuses_until_pinned_versions_are_filled(self):
        with self.assertRaisesRegex(PetError, "placeholder"):
            PetConfig.load(REPO / "pet.toml")

    def test_filled_template_is_valid(self):
        config = PetConfig.load(self.root / "pet.toml")
        self.assertEqual(config.rules.top_n, 5)
        self.assertEqual(config.grammar.expand(1, 0)[0], "GHROPACLT")


class SeedGuardTest(PetCase):
    def test_init_twice_is_refused(self):
        with self.assertRaisesRegex(PetError, "already started"):
            self.pet.init()

    def test_edited_seed_is_caught(self):
        path = self.root / "pet.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("edge = [0.5, 0.7]", "edge = [0.1, 0.99]"), encoding="utf-8")
        with self.assertRaisesRegex(PetError, "pet.toml changed"):
            Pet(self.root, self.clock).check()

    def test_touched_immutable_gene_is_caught(self):
        genome_path = self.root / "life" / "genome.json"
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
        genome["genes"][0]["text"] = "Break whatever you like"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        with self.assertRaisesRegex(PetError, "immutable gene 'keep-home'"):
            self.pet.check()

    def test_removed_immutable_gene_is_caught(self):
        genome_path = self.root / "life" / "genome.json"
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
        genome["genes"] = genome["genes"][1:]
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        with self.assertRaises(PetError):
            self.pet.check()

    def test_broken_grammar_in_life_is_caught(self):
        grammar_path = self.root / "life" / "grammar.json"
        grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
        grammar["rules"]["X"] = [{"to": "G[H", "weight": 1}]
        grammar_path.write_text(json.dumps(grammar), encoding="utf-8")
        with self.assertRaisesRegex(PetError, "unbalanced"):
            self.pet.check()


class ConfigErrorsTest(PetCase):
    def load(self, **replacements):
        path = self.dir / "variant.toml"
        path.write_text(seed_toml(**replacements), encoding="utf-8")
        return PetConfig.load(path)

    def test_bad_edge_is_refused(self):
        with self.assertRaisesRegex(PetError, "edge"):
            self.load(**{"edge = [0.5, 0.7]": "edge = [0.7, 0.5]"})

    def test_core_letter_cannot_be_redefined(self):
        with self.assertRaisesRegex(PetError, "core letters"):
            self.load(**{'X = "the base cycle"': 'G = "something else"'})

    def test_duplicate_gene_is_refused(self):
        with self.assertRaisesRegex(PetError, "duplicate gene"):
            self.load(**{'id = "small-steps"': 'id = "predict-first"'})

    def test_rule_with_unknown_letter_is_refused(self):
        with self.assertRaisesRegex(PetError, "unknown symbols"):
            self.load(**{'{ to = "L M", weight = 0.3 }': '{ to = "L Q", weight = 0.3 }'})
