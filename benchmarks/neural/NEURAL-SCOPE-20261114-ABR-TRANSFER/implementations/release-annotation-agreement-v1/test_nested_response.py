"""Generated first-final recursion regression; no authentic inputs or labels.

Use --implementation to select the scorer and --fixture to select the existing
synthetic roster builder. An optional --representation/--documents pair checks
both explicit store-producer pins against generated public metadata. The legacy
failure flag is for an immutable predecessor proof, not a passing current scorer.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    output = args.output.absolute()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("fresh generated output directory required")
    output.mkdir(mode=0o700)
    scorer = load(args.implementation, "nested_response_scorer")
    fixture = load(args.fixture, "nested_response_fixture")
    fixture.a = scorer
    _, _, refs, codes, roster, provider = fixture.fixture()
    pair = scorer.Pair(output / "pair", roster, provider, b"fixed generated programme\n",
                       b"generated common instructions\n", source_identity=scorer.sha(b"generated only"))
    bad_id = roster.ids[0]
    depth = 1500
    assert sys.getrecursionlimit() < depth
    malformed = (b'{"case_id":"' + bad_id.encode() + b'","predicted_annotation_code":'
                 + b"[" * depth + b"0" + b"]" * depth + b"}")
    assert len(malformed) <= scorer.MAX_FINAL
    for arm in ("direct", "programme"):
        for cid in roster.ids:
            pair.expose(arm)
            raw = malformed if arm == "direct" and cid == bad_id else scorer.canonical(
                {"case_id": cid, "predicted_annotation_code": codes[cid]})
            pair.submit(arm, cid, raw)
    pair.seal()
    findings = {"generated_only": True, "retained_finals": len(pair._finals),
                "malformed_response_bytes": len(malformed), "methods": []}
    if args.historical_failure_only:
        try:
            pair.score(refs)
        except RecursionError:
            findings["historical_recursion_error_reproduced"] = True
        else:
            raise AssertionError("predecessor did not reproduce the nested-response failure")
        assert pair._scored
        findings["methods"].append("predecessor_one_shot_recursion_failure")
    else:
        result = pair.score(refs)
        direct, programme = result["arms"]["direct"], result["arms"]["programme"]
        assert direct["coverage"] == {"required": 936, "valid": 935, "invalid": 1}
        assert direct["failure_case_ids"] == [bad_id]
        assert direct["aggregate_withheld"] is True and "metrics" not in direct
        assert programme["coverage"] == {"required": 936, "valid": 936, "invalid": 0}
        assert programme["aggregate_withheld"] is False
        assert programme["metrics"]["animal_macro_exact_numeric_code_agreement"] == 1.0
        for key, value in scorer.HOLDS.items():
            assert result[key] == value
        try:
            pair.score(refs)
        except ValueError:
            pass
        else:
            raise AssertionError("one-shot score was reopened")
        findings["direct_coverage"] = direct["coverage"]
        findings["programme_coverage"] = programme["coverage"]
        findings["methods"].append("nested_final_is_invalid_without_aborting_complete_score")
    if args.representation is not None:
        assert args.documents is not None and not args.historical_failure_only
        rep = load(args.representation, "nested_response_representation")
        store = output / "generated_store"
        (store / "operator").mkdir(parents=True)
        (store / "public").mkdir()
        documents = args.documents.read_bytes()
        assert (len(documents), scorer.sha(documents)) == rep.DOCUMENTS_PIN
        (store / "public/COMMON_DOCUMENTATION.txt").write_bytes(documents)
        counts = [17] * 831 + [19] + [20] * 104
        rows = [{"case_id": f"{i:032x}", "packet_path": f"public/cases/{i:032x}.json",
                 "trace_count": n, "sample_count": n * rep.SAMPLES_PER_TRACE,
                 "page_count": (n + 2) // 3} for i, n in enumerate(counts)]
        index = scorer.canonical({"source_complete_sha256": rep.COMPLETE_PIN[1], "cases": rows})
        (store / "operator/INDEX.json").write_bytes(index)
        manifest = {"schema": "abr-complete-delivery-preparation-v1", "mode": rep.MODE,
                    "native_complete_pin": list(rep.COMPLETE_PIN), "raster_pin": list(rep.RASTER_PIN),
                    "documents_pin": list(rep.DOCUMENTS_PIN), "cases": rep.CASE_COUNT,
                    "traces": rep.TRACE_COUNT, "samples": rep.TOTAL_SAMPLES,
                    "index_pin": {"bytes": len(index), "sha256": scorer.sha(index)},
                    "pages_available_on_demand": sum(r["page_count"] for r in rows), **rep.HOLDS}
        for label, producer, accepted in (("legacy", rep.PREVIOUS_IMPLEMENTATION_PIN, True),
                                           ("current", rep.IMPLEMENTATION_PIN, True),
                                           ("unknown", (rep.IMPLEMENTATION_PIN[0], "0" * 64), False)):
            manifest["implementation_pin"] = list(producer)
            body = scorer.canonical(manifest)
            (store / "COMPLETE.json").write_bytes(body)
            try:
                _, loaded, _, records, loaded_docs = rep.open_store(scorer, store, (len(body), scorer.sha(body)))
            except ValueError as exc:
                assert not accepted and str(exc) == "prepared store source identity"
            else:
                assert accepted and loaded["implementation_pin"] == list(producer)
                assert len(records) == 936 and loaded_docs == documents
            findings["methods"].append(label + "_producer_pin_admission")
    findings["retained_artifact_bytes"] = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    assert findings["retained_artifact_bytes"] < 2 * 1024**2
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", type=Path, default=Path(__file__).with_name("abr_release.py"))
    parser.add_argument("--fixture", type=Path, default=Path(__file__).with_name("test_abr_release.py"))
    parser.add_argument("--representation", type=Path)
    parser.add_argument("--documents", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--historical-failure-only", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    findings = run(args)
    findings["elapsed_seconds"] = time.monotonic() - started
    print(json.dumps(findings, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
