#!/usr/bin/env python3
"""Deterministic consistency checks for the public curation contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "curation"
SCHEMA_PATH = CONTRACT_DIR / "curation-contracts-v1.schema.json"
RUBRIC_PATH = CONTRACT_DIR / "evolvable-rubric-v1.md"
PROMPT_PATH = ROOT / "TOPIC_TRIAGE_CONTROLLER_PROMPT.md"
EVOLVABLE_SKILL_PATH = (
    ROOT / ".claude" / "skills" / "self-evolvable-question-design" / "SKILL.md"
)

REQUIRED_DEFINITIONS = {
    "ArtifactRef",
    "PrivateArtifactRef",
    "Actor",
    "CurationJob",
    "StageResult",
    "CurationTransition",
    "BenchmarkQuestionSpec",
    "EvolvableQuestionFamily",
}
EVIDENCE_STATUSES = {"reported", "verified", "measured", "planned", "missing"}
STAGE_OUTCOMES = {"passed", "killed", "blocked", "retry"}
VISIBILITIES = {"public", "author_private", "oracle_private", "restricted"}
CANONICAL_RUBRIC_PHRASES = {
    "C3": "exogenous, time-forward, sequestered freshness",
    "C4": "capability-orthogonal gradient plus a mandatory falsification test",
    "C5": "cheap, pre-committed re-targeting rule",
}


def _enum(schema: dict, definition: str) -> set[str]:
    return set(schema["$defs"][definition]["enum"])


def _transition_is_valid(
    transitions: dict[str, dict[str, object]],
    stage: str,
    from_state: str,
    to_state: str,
    outcome: str,
) -> bool:
    rule = transitions.get(stage)
    if not rule:
        return False
    inputs = set(rule["inputs"])
    if outcome == "passed":
        return from_state in inputs and to_state == rule.get("passed")
    if outcome == "killed":
        return from_state in inputs and to_state == rule.get("killed")
    if outcome == "blocked":
        return from_state in inputs and to_state == "blocked"
    if outcome == "retry":
        return from_state == "blocked" and to_state in inputs
    if outcome == "released":
        return (
            stage == "ADJUDICATE"
            and from_state in inputs
            and to_state == rule.get("released")
        )
    if outcome == "retired":
        return (
            stage == "ADJUDICATE"
            and from_state in inputs
            and to_state == rule.get("retired")
        )
    return False


def _private_artifact_is_valid(ref: dict[str, object]) -> bool:
    return {
        "artifact_id",
        "uri",
        "sha256",
        "media_type",
        "visibility",
    }.issubset(ref) and ref.get("visibility") in {
        "author_private",
        "oracle_private",
        "restricted",
    }


def _evidence_item_is_valid(item: dict[str, object]) -> bool:
    return item.get("status") != "measured" or bool(item.get("evidence_refs"))


def _worker_release_status_is_valid(status: str) -> bool:
    return status in {"draft", "adjudication_pending"}


def _stage_result_is_valid(artifact_refs: list[object]) -> bool:
    return len(artifact_refs) >= 1


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    skill = EVOLVABLE_SKILL_PATH.read_text(encoding="utf-8")

    missing = REQUIRED_DEFINITIONS - set(schema["$defs"])
    assert not missing, f"missing schema definitions: {sorted(missing)}"
    assert _enum(schema, "EvidenceStatus") == EVIDENCE_STATUSES
    assert _enum(schema, "StageOutcome") == STAGE_OUTCOMES
    assert _enum(schema, "ArtifactVisibility") == VISIBILITIES
    assert "released" not in _enum(schema, "StageOutcome")

    artifact_schema = schema["$defs"]["ArtifactRef"]
    assert artifact_schema["additionalProperties"] is False
    assert set(artifact_schema["required"]) == {
        "artifact_id",
        "uri",
        "sha256",
        "media_type",
        "visibility",
    }
    executor_schema = schema["$defs"]["ExecutedBy"]
    assert executor_schema["additionalProperties"] is False
    assert set(executor_schema["required"]) == {
        "agent",
        "model_snapshot",
        "skill_sha",
        "tool_manifest_ref",
    }
    assert executor_schema["properties"]["skill_sha"] == {
        "$ref": "#/$defs/Sha256"
    }
    assert executor_schema["properties"]["tool_manifest_ref"] == {
        "$ref": "#/$defs/ArtifactRef"
    }
    private_ref_schema = schema["$defs"]["PrivateArtifactRef"]
    assert private_ref_schema["allOf"][0] == {"$ref": "#/$defs/ArtifactRef"}
    assert set(private_ref_schema["allOf"][1]["properties"]["visibility"]["enum"]) == (
        VISIBILITIES - {"public"}
    )

    evidence_schema = schema["$defs"]["EvidenceItem"]
    assert evidence_schema["allOf"][0]["then"]["properties"]["evidence_refs"][
        "minItems"
    ] == 1
    assert _evidence_item_is_valid(
        {"status": "measured", "evidence_refs": [{"artifact_id": "run"}]}
    )
    assert not _evidence_item_is_valid({"status": "measured", "evidence_refs": []})
    assert _evidence_item_is_valid({"status": "planned", "evidence_refs": []})

    transition_schema = schema["$defs"]["CurationTransition"]
    assert transition_schema["properties"]["schema_version"]["const"] == (
        "CurationTransitionV1"
    )
    assert transition_schema["additionalProperties"] is False
    assert {
        "schema_version",
        "transition_id",
        "opportunity_id",
        "candidate_id",
        "job_id",
        "stage",
        "outcome",
        "from_state",
        "to_state",
        "artifact_refs",
        "actor",
    } == set(transition_schema["required"])
    assert "content_sha256" not in transition_schema["properties"]
    assert "source_result_ref" not in transition_schema["properties"]
    assert "evidence_refs" not in transition_schema["properties"]
    assert "timestamp" not in transition_schema["properties"]

    stage_result_schema = schema["$defs"]["StageResult"]
    assert stage_result_schema["properties"]["artifact_refs"]["minItems"] == 1

    for definition in ("BenchmarkQuestionSpec", "EvolvableQuestionFamily"):
        assert set(schema["$defs"][definition]["properties"]["release_status"]["enum"]) == {
            "draft",
            "adjudication_pending",
        }
    benchmark_schema = schema["$defs"]["BenchmarkQuestionSpec"]
    for field in ("private_failure_axis_ref", "private_hidden_lever_ref"):
        assert benchmark_schema["properties"][field] == {
            "$ref": "#/$defs/PrivateArtifactRef"
        }
    private_ref = {
        "artifact_id": "hidden-axis",
        "uri": "artifact://private/hidden-axis",
        "sha256": "a" * 64,
        "media_type": "application/json",
        "visibility": "oracle_private",
    }
    assert _private_artifact_is_valid(private_ref)
    assert not _private_artifact_is_valid({"visibility": "oracle_private"})
    assert not _private_artifact_is_valid({**private_ref, "visibility": "public"})
    assert _worker_release_status_is_valid("draft")
    assert not _worker_release_status_is_valid("released")
    assert _stage_result_is_valid([private_ref])
    assert not _stage_result_is_valid([])

    transitions = schema["x-stage-transition-contract"]
    assert _transition_is_valid(
        transitions, "SCOUT", "unstarted", "scouted", "passed"
    )
    assert _transition_is_valid(
        transitions, "STEP0", "data_acquired", "step0_killed", "killed"
    )
    assert _transition_is_valid(
        transitions, "STEP0", "data_acquired", "blocked", "blocked"
    )
    assert _transition_is_valid(
        transitions, "STEP0", "blocked", "data_acquired", "retry"
    )
    assert _transition_is_valid(
        transitions,
        "ADJUDICATE",
        "benchmark_calibrated",
        "released",
        "released",
    )
    assert not _transition_is_valid(
        transitions, "SCOUT", "unstarted", "released", "released"
    )
    assert not _transition_is_valid(
        transitions,
        "BENCHMARK_DRAFT",
        "step0_passed",
        "released",
        "released",
    )
    assert not _transition_is_valid(
        transitions,
        "CALIBRATE_FAMILY",
        "family_drafted",
        "released",
        "passed",
    )

    for criterion in [f"C{index}" for index in range(1, 11)] + ["F0"]:
        matches = re.findall(rf"\*\*{criterion}\b", rubric)
        assert len(matches) == 1, f"{criterion} must be defined exactly once in rubric"

    rubric_lower = rubric.lower()
    for criterion, phrase in CANONICAL_RUBRIC_PHRASES.items():
        assert phrase in rubric_lower, f"{criterion} canonical wording drifted"
        assert criterion in prompt, f"{criterion} missing from worker prompt"

    assert "evolvable-rubric-v1.md" in skill
    assert "parameterized generation" not in prompt.lower()
    assert "contamination resistance" not in prompt.lower()
    assert "freshness or ratchet mechanism" not in prompt.lower()

    print("curation contracts: OK")


if __name__ == "__main__":
    main()
