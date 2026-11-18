"""Private original-endpoint arithmetic after both complete public arms close."""
import contract
import dependencies
from storage import need


def grade_collections(panel, responses, outcome):
    """Pure evaluator arithmetic; calling this function is not runtime evidence.

    The coordinator is responsible for the closure/private-read barrier. No
    threshold for paper reproduction, improvement, or SOTA is invented here.
    """
    need(type(responses) is dict and set(responses) == {"A", "B"}, "two complete assistance conditions")
    collections = {role: contract.collect(panel, responses[role], outcome) for role in ("A", "B")}
    scorer = dependencies.load("score")
    scores = {}
    for role in ("A", "B"):
        collection = collections[role]
        scores[role] = scorer.score_cell(collection["observations"], collection["probabilities_object"], ("face", "object"))
    need(collections["A"]["observations"] == collections["B"]["observations"], "identical original held support")
    return {"schema": "meg-paired-original-endpoint-score/v1", "outcome": outcome,
        "panel_sha256": panel["panel_sha256"], "observations_per_condition": 188,
        "participants": 94, "folds": 10, "scores": scores,
        "B_minus_A_accuracy": scores["B"]["accuracy"] - scores["A"]["accuracy"],
        "source_feature_claims": {role: collections[role]["source_feature_rows"] for role in ("A", "B")},
        "historical_folds_authenticated": False,
        "reference_numerical_agreement_evaluated": False,
        "paper_reproduction_success": None, "paper_improvement_success": None,
        "scientific_qualification": False,
        "interpretation": "Original unweighted mean-fold accuracy/population fold SD on the supplied matched folds. Assistance-arm difference is descriptive; no original reference output, uncertainty rule or paper-win decision is supplied."}
