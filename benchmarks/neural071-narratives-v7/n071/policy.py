"""Exact adopted design identities, scopes and capability gates."""
from .errors import need
from .identity import digest, exact
PRIOR = "61a88dea57636c784e240611ff456cbf46e50de3aee331df8834c3f8987e5566"
CLOCK = "37ad4e48f44987f2acc029e08ad750d85ca383a076cf76ab9f9166172ff90876"
LABEL = "exploratory_public_corpus_with_shared_corpus_prior"
ARMS = ("NUISANCE", "LEXICAL", "CONTEXT")
RESPONSES = ("REAL_RESPONSE", "ZERO_RESPONSE")
MODES = ("F", "I")
REFERENCES = ("Rmean/ALL", "R0/NUISANCE", "R0/LEXICAL", "R0/CONTEXT",
              "R2/NUISANCE", "R2/LEXICAL", "R2/CONTEXT", "Rtemp/T", "Racoustic/A")
GAPS = ("atlas-content-and-rights", "two-scrambled-alignments", "native-TR-and-clock",
        "source-version-and-rights", "model-tokenizer-content-and-rights",
        "native-runtime-and-numerical-agreement", "provider-price-and-monetary-cap",
        "whole-tree-isolation-and-resource-accounting", "setup-extraction-resource-profile")
HISTORICAL = ("Layer 8 was selected on Narratives responses from 101 listeners, seven stories "
              "and 237 pairs. Overlap with the current 171 listeners is UNKNOWN. "
              "Train-only current fitting does not make that global prior independent. "
              "REAL/ZERO is an access sanity check, not proof of native neural understanding.")

def evidence(direct=False):
    return {"method_prior_identity": PRIOR, "clock_conventions_identity": CLOCK,
            "evaluation_label": LABEL, "historical_layer8_direct_consumer": direct}

def validate_evidence(obj, direct):
    for key,value in evidence(direct).items():
        need(obj.get(key) == value and (key != "historical_layer8_direct_consumer" or
             type(obj[key]) is bool), "design-evidence-" + key)

class Qualification:
    """An externally adopted, exact complete qualification packet; no implicit defaults."""
    def __init__(self, record, expected_identity):
        from .identity import identity
        need(identity(record) == digest(expected_identity), "qualification-pin")
        exact(record, ("generation", "source", "gates", "bindings", "original_receipts",
                       "whole_host_memory", "build_only"))
        need(record["build_only"] is False, "build-only-no-science")
        need(set(record["gates"]) == set(GAPS), "complete-qualification-gaps")
        for gap in GAPS:
            need(record["gates"][gap] == "qualified" and gap in record["original_receipts"],
                 "qualification-open-" + gap)
        self.record = record
        self.identity = expected_identity

    def require(self, generation, source):
        need(self.record["generation"] == generation and self.record["source"] == source,
             "qualification-generation-source")
        return self.record["bindings"]
