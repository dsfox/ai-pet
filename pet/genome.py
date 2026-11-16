"""The genome: starting rules that mutate on trial and are judged after a few cycles."""
import copy

from .config import SLUG
from .errors import PetError

OPERATIONS = ("add", "edit", "sleep", "wake")
VERDICTS = ("accept", "reject")


class Genome:
    NAME = "genome.json"

    def __init__(self, data):
        self.data = data

    @classmethod
    def seed(cls, genes):
        return cls({
            "generation": 1,
            "genes": [{"id": gene.id, "text": gene.text, "immutable": gene.immutable, "status": "active", "pending": None}
                      for gene in genes],
        })

    @property
    def generation(self):
        return self.data["generation"]

    @property
    def genes(self):
        return self.data["genes"]

    def find(self, gene_id):
        return next((gene for gene in self.genes if gene["id"] == gene_id), None)

    def active(self):
        return [gene for gene in self.genes if gene["status"] == "active"]

    def sleeping(self):
        return [gene for gene in self.genes if gene["status"] == "sleeping"]

    def check_immutable(self, seed_genes):
        for seed_gene in seed_genes:
            if not seed_gene.immutable:
                continue
            gene = self.find(seed_gene.id)
            if gene is None or gene["text"] != seed_gene.text or gene["status"] != "active" or not gene["immutable"]:
                raise PetError(f"immutable gene {seed_gene.id!r} was touched; restore it from pet.toml")


class MutationGate:
    NAME = "mutations.jsonl"

    def __init__(self, life, config):
        self.life = life
        self.config = config

    def journal(self):
        return self.life.records(self.NAME)

    def pending(self):
        judged = {record["id"] for record in self.journal() if record["event"] == "judge"}
        return [record for record in self.journal() if record["event"] == "propose" and record["id"] not in judged]

    def proposed_on(self, date):
        return [record for record in self.journal() if record["event"] == "propose" and record["at"][:10] == date]

    def propose(self, genome, operation, gene_id, text, reason, quota, now, closed_count):
        if self.config.frozen:
            raise PetError("this pet is a frozen control twin: its genome never mutates")
        if operation not in OPERATIONS:
            raise PetError(f"mutation must be one of {', '.join(OPERATIONS)}")
        if not reason or not reason.strip():
            raise PetError("a mutation needs a reason")
        today = now.date().isoformat()
        if len(self.proposed_on(today)) >= quota:
            raise PetError(f"mutation quota for today is {quota}; it rises only under SOS")
        gene = genome.find(gene_id)
        previous = copy.deepcopy(gene)
        mutation_id = f"m{sum(record['event'] == 'propose' for record in self.journal()) + 1:03d}"
        if operation == "add":
            self._require(SLUG.match(gene_id or ""), "gene id must be lowercase letters, digits and dashes")
            self._require(gene is None, f"gene {gene_id!r} already exists")
            self._require(text and text.strip(), "add needs --text")
            genome.genes.append({"id": gene_id, "text": text.strip(), "immutable": False, "status": "active", "pending": mutation_id})
        else:
            self._require(gene is not None, f"no gene {gene_id!r}")
            self._require(not gene["immutable"], f"gene {gene_id!r} is immutable")
            self._require(gene["pending"] is None, f"gene {gene_id!r} already has a mutation on trial")
            if operation == "edit":
                self._require(text and text.strip() and text.strip() != gene["text"], "edit needs a new --text")
                gene["text"] = text.strip()
            elif operation == "sleep":
                self._require(gene["status"] == "active", f"gene {gene_id!r} is not active")
                gene["status"] = "sleeping"
            else:
                self._require(gene["status"] == "sleeping", f"gene {gene_id!r} is not sleeping")
                gene["status"] = "active"
            gene["pending"] = mutation_id
        record = {"event": "propose", "id": mutation_id, "at": now.isoformat(), "op": operation, "gene": gene_id,
                  "previous": previous, "after": copy.deepcopy(genome.find(gene_id)), "reason": reason.strip(),
                  "closed_at_propose": closed_count}
        self.life.append(self.NAME, record)
        return record

    def judge(self, genome, mutation_id, verdict, reason, now, closed_count, evidence):
        if verdict not in VERDICTS:
            raise PetError(f"verdict must be one of {', '.join(VERDICTS)}")
        if not reason or not reason.strip():
            raise PetError("a verdict needs a reason")
        proposal = next((record for record in self.pending() if record["id"] == mutation_id), None)
        self._require(proposal is not None, f"no mutation {mutation_id!r} on trial")
        waited = closed_count - proposal["closed_at_propose"]
        trial = self.config.rules.trial_cycles
        self._require(waited >= trial, f"mutation {mutation_id} needs {trial} closed cycles on trial, has {waited}")
        gene = genome.find(proposal["gene"])
        gene["pending"] = None
        if verdict == "accept":
            genome.data["generation"] += 1
        else:
            self._revert(genome, gene, proposal)
        record = {"event": "judge", "id": mutation_id, "at": now.isoformat(), "verdict": verdict,
                  "reason": reason.strip(), "evidence": evidence}
        self.life.append(self.NAME, record)
        return record

    @staticmethod
    def _revert(genome, gene, proposal):
        previous = proposal["previous"]
        if proposal["op"] == "add":
            gene["status"] = "sleeping"
            return
        if proposal["op"] == "edit":
            genome.genes.append({"id": f"{gene['id']}-{proposal['id']}", "text": gene["text"], "immutable": False,
                                 "status": "sleeping", "pending": None})
        gene["text"] = previous["text"]
        gene["status"] = previous["status"]

    @staticmethod
    def _require(condition, message):
        if not condition:
            raise PetError(message)
