"""Complete paired-workflow output validation, without labels or scoring."""
import math
import re

HASH = re.compile(r"[0-9a-f]{64}\Z")
ARMS = frozenset(("viewer_only", "code_enabled"))


class PredictionRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PredictionRefusal(message)


def valid_hash(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def admit_manifest(manifest):
    """Validate a caller-authenticated complete public case/hash manifest.

    These shape checks do not prove the authentic full source population. The
    admitted source-index/delivery driver must establish that separate binding.
    """
    require(type(manifest) is list and 0 < len(manifest) <= 10000,
            "bounded complete manifest required")
    expected = {}
    for item in manifest:
        require(type(item) is dict and set(item) == {"case_id", "observation_sha256"},
                "public manifest fields differ")
        require(valid_hash(item["case_id"]) and valid_hash(item["observation_sha256"]),
                "exact case and observation hashes required")
        require(item["case_id"] not in expected, "duplicate expected case")
        expected[item["case_id"]] = item["observation_sha256"]
    return expected


def admit_predictions(manifest, submitted, arm):
    """Require one prediction or explicit abstention for every frozen case.

    Never silently drop failures, renormalize probabilities or substitute a
    prediction for an abstention. Scores and abstention penalties are outside
    this transport contract and require a separately admitted scoring policy.
    """
    expected = admit_manifest(manifest)
    require(arm in ARMS, "unknown declared workflow")
    require(type(submitted) is dict and set(submitted) == {"schema", "arm", "cases"}
            and submitted["schema"] == "dosei_paired_workflow_predictions_v1"
            and submitted["arm"] == arm, "workflow output envelope differs")
    cases = submitted["cases"]
    require(type(cases) is list and len(cases) == len(expected),
            "every frozen case requires an output slot")
    found = {}
    for row in cases:
        require(type(row) is dict and set(row) ==
                {"case_id", "observation_sha256", "status", "probabilities"},
                "prediction fields differ")
        ident = row["case_id"]
        require(valid_hash(ident) and ident in expected and ident not in found,
                "unknown or duplicate prediction case")
        require(row["observation_sha256"] == expected[ident],
                "prediction was not bound to the matched observation")
        status, probabilities = row["status"], row["probabilities"]
        require(type(status) is str and status in ("ok", "abstain"),
                "explicit prediction or abstention required")
        if status == "abstain":
            require(probabilities is None, "abstention probabilities must be null")
            copied = None
        else:
            require(type(probabilities) is list and len(probabilities) == 5,
                    "five ordered MOAAS-category probabilities required")
            require(all(type(p) in (int, float) and 0 <= p <= 1 and math.isfinite(p)
                        for p in probabilities), "finite probabilities in [0,1] required")
            require(abs(math.fsum(probabilities) - 1) <= 1e-6,
                    "probabilities must sum to one without repair")
            copied = list(probabilities)
        found[ident] = {"case_id": ident, "observation_sha256": expected[ident],
                        "status": status, "probabilities": copied}
    require(set(found) == set(expected), "complete prediction coverage required")
    return [found[item["case_id"]] for item in manifest]


def admit_pair(manifest, submitted):
    """Validate two workflows against one identical manifest; calculate no score."""
    require(type(submitted) is dict and set(submitted) == ARMS,
            "both declared workflow outputs required")
    return {arm: admit_predictions(manifest, submitted[arm], arm) for arm in sorted(ARMS)}
