"""Authenticated pre-query reference-selection custody, never a grading choice."""
from dataclasses import dataclass
import json
from cohort import ARMS, require
from io_support import canonical_bytes, object_digest
from storage import read_json_exact, write_json_fresh
from reference.models import setting_grid, select_setting

FAMILY_PUBLIC = {"ridge": "ridge", "shrinkage_lda": "lda", "fourier_ridge": "fourier_ridge"}


def _json(pin, budget):
    require(type(pin) is dict and type(pin.get("bytes")) is int and 0 < pin["bytes"] <= 4 * 1024 * 1024,
            "Bounded authenticated reference-evidence metadata")
    return read_json_exact(pin["path"], pin, budget)


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class ReferenceSelection:
    """Immutable derived evidence; full phase authority separately binds its hash."""
    encoded: bytes

    @property
    def document(self):
        return json.loads(self.encoded)

    @property
    def digest(self):
        return object_digest(self.document)

    @property
    def families(self):
        return {(row["fold_ordinal"], row["arm"]): row["family"] for row in self.document["cases"]}


def derive_reference_selection(program_pin, budget):
    """Read exact actual training outputs and recompute all48-record choices.

    This function performs no fits and reads no query data or targets. The
    program pin must first be joined to the accepted train_references phase
    completion/output manifest by the phase operand gate.
    """
    program = _json(program_pin, budget)
    require(program.get("schema") == "neural053_full_reference_program_v1" and
            type(program.get("completed_fits")) is int and program["completed_fits"] == 3904,
            "Complete reference-program output")
    require(type(program.get("cases")) is list and len(program["cases"]) == 16, "All16 reference cases")
    expected = {(f, a) for f in range(4) for a in ARMS}
    seen, choices = set(), []
    grid = setting_grid()
    for stored in program["cases"]:
        case = stored["case"]
        key = (case["fold_ordinal"], case["arm"])
        require(type(key[0]) is int and key in expected and key not in seen, "Unique complete reference case")
        seen.add(key)
        require(case == {"fold_ordinal": key[0], "arm": key[1], "inner_fits": 240,
                         "selected_family_refits": 3, "centroid_fits": 1}, "Exact reference-case programme")
        manifest = _json(stored["manifest"], budget)
        require(stored["artifact_manifest_sha256"] == stored["manifest"]["sha256"] and
                {k: v for k, v in stored.items() if k not in {"manifest", "artifact_manifest_sha256"}} == manifest,
                "Top-level programme joins actual complete case manifest")
        require(manifest["case"] == case and type(manifest["fits"]) is int and manifest["fits"] == 244 and
                set(manifest["plans"]) == {"ridge", "lda", "fourier_ridge", "centroid"}, "All final reference plans")
        evidence = _json(manifest["training_selection"], budget)
        require(evidence.get("schema") == "neural053_reference_case_v1" and
                (evidence["fold_ordinal"], evidence["arm"]) == key and evidence["fits"] == 244 and
                evidence.get("engineering_profile") is False, "Canonical training-only evidence identity")
        records = evidence["selection_records"]
        require(type(records) is list and len(records) == 48, "Complete16-by3 training metrics")
        for row in records:
            require(row.get("people") == 3 and row.get("classes") == 1854 and
                    row.get("validation_rows_per_person_class") == 10 and
                    row["top1_fraction"][1] == 55620, "Complete grouped training validation support")
        fits = evidence["fit_records"]
        require(type(fits) is list and len(fits) == 244, "All recorded training/refit operations")
        inner = [f for f in fits if f.get("phase") == "inner"]
        final = [f for f in fits if f.get("phase") == "final"]
        require(len(inner) == 240 and {(f["rank"], f["split"]) for f in inner} ==
                {(rank, split) for rank in range(16) for split in range(15)} and
                len(final) == 4 and {f["family"] for f in final} == {"ridge", "lda", "fourier_ridge", "centroid"},
                "Exact complete inner/final fitting lineage")
        require(all(_sha(f.get("state_digest")) and _sha(f.get("fit_support")) for f in fits) and
                all(_sha(f.get("validation_support")) for f in inner), "Bound source-state/fit/validation lineage")
        selected = {family: select_setting([r for r in records if grid[r["rank"]]["family"] == family], family)
                    for family in FAMILY_PUBLIC}
        winner = select_setting(records)
        family = FAMILY_PUBLIC[grid[winner["rank"]]["family"]]
        require(evidence["selected"] == selected and evidence["primary_family"] == family and
                manifest["primary_family"] == family, "Frozen primary family recomputed from actual training metrics")
        for f in final:
            if f["family"] == "centroid":
                require(f["temperature"] == 1, "Historical centroid temperature")
            else:
                internal = next(k for k, v in FAMILY_PUBLIC.items() if v == f["family"])
                require(f["rank"] == selected[internal]["rank"] and
                        f["temperature"] == selected[internal]["temperature"], "Final refit matches training-selected setting")
        choices.append({"fold_ordinal": key[0], "arm": key[1], "family": family,
                        "rank": winner["rank"], "temperature": winner["temperature"],
                        "case_manifest": stored["manifest"], "training_evidence": manifest["training_selection"],
                        "final_plans": manifest["plans"]})
    require(seen == expected, "No missing reference case")
    order = {a: i for i, a in enumerate(ARMS)}
    choices.sort(key=lambda row: (row["fold_ordinal"], order[row["arm"]]))
    document = {"schema": "neural053_reference_selection_v2", "source_reference_program": program_pin,
                "selection_phase": "training_only_before_query", "cases": choices,
                "criterion": "higher_equal_person_class_balanced_top1_then_lower_logloss_then_base_temperature_rank"}
    return ReferenceSelection(canonical_bytes(document))


def admit_reference_selection(selection_pin, program_pin, expected_digest, budget):
    """Authenticate current evidence and compare to independently approved choice."""
    stored = _json(selection_pin, budget)
    derived = derive_reference_selection(program_pin, budget)
    require(stored == derived.document and derived.digest == expected_digest,
            "Missing, stale or substituted pre-query primary reference selection")
    return derived


def store_reference_selection(path, program_pin, budget):
    selection = derive_reference_selection(program_pin, budget)
    return write_json_fresh(path, selection.document, budget), selection
