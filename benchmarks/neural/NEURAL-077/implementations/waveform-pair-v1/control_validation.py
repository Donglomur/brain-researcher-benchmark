"""One explicitly admitted engineering control; importing this file runs nothing.

Uses only the already frozen fixed-0.5 client, one new complete programme arm,
the accepted old no-tools proof and unchanged protected metrics. Not an AI run.
"""
import argparse
from pathlib import Path
import platform
import resource
import time

import pair

OUTPUT_CAP = 96 * 1024 * 1024


def validate(delivery_root, frozen_file, frozen_sha256, python, legacy_control, private_locations, output):
    pair.need(platform.system() == "Darwin", "The selected engineering control uses the macOS transport")
    started = time.monotonic()
    output = pair.bundle.unlinked(output)
    output.mkdir(mode=0o700)
    try:
        body = pair.read(frozen_file)
        pair.need(pair.pin(body)["sha256"] == frozen_sha256, "Approved fixed bundle changed")
        frozen = pair.decode(body)
        pair.bundle.verify(frozen)
        # The later protocol pins the entire bundle. This also refuses any
        # replacement source/config even if it has internally consistent hashes.
        sources = pair.sources()
        members = frozen["members"]
        import base64
        pair.need(frozen["manifest"] == {"schema": "neural077_python_bundle_v1", "entry_module": "main",
                                         "modules": ["main.py"], "config": "config.json"}
                  and base64.b64decode(members["main.py"]["base64"], validate=True)
                  == sources[2]["waveform-transport-v1/scripted_client.py"]
                  and base64.b64decode(members["config.json"]["base64"], validate=True) == b"{}\n",
                  "Only the unchanged fixed-0.5 software control is admitted")
        arm = pair.run_arm(delivery_root, pair.CONDITIONS[1], frozen_file, output / "programme", python,
                           sources[0].Limits(max_prompt_bytes=262144, wall_seconds=3, campaign_seconds=120))
        remaining = 165 - (time.monotonic() - started)
        pair.need(remaining >= 5, "No remaining evaluator allowance; preserve unscored arm")
        paired = pair.dispatch_grade(delivery_root, None, output / "programme", legacy_control,
                                     private_locations, output / "comparison", min(30, remaining))
        report = pair.decode(pair.read(output / "comparison/grade/RESULT.json"))
        pair.need(report["trial_count"] == 400 and report["private_loader_invocations"] == 2
                  and report["a"]["canonical_score"]["candidate"]["participant_macro_balanced_accuracy"] == .5
                  and report["b"]["canonical_score"]["candidate"]["participant_macro_balanced_accuracy"] == .5
                  and report["a_minus_b"]["participant_macro_balanced_accuracy"] == 0
                  and report["a_minus_b"]["participant_macro_log_loss"] == 0,
                  "Complete identical fixed-control arithmetic required")
        retained = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        # Four public NPZ snapshots are reclaimed by the unchanged comparator
        # and this operator. Include conservative ZIP-header rewrite overhead.
        reclaimed = report["accounting"]["temporary_submission_bytes_created"]
        pair.need(retained + reclaimed + 4096 + 65536 <= OUTPUT_CAP, "Control artifact envelope exceeded")
        own, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt = {"schema": "neural077_complete_paired_control_v1", "status": "complete_engineering_control",
                   "new_programme_queries": 400, "reused_no_tools_queries": 400, "demonstrations": 4,
                   "frozen": pair.pin(body), "arm": pair.pin(pair.encode(arm)), "comparison": paired,
                   "wall_seconds_before_receipt": time.monotonic() - started,
                   "cpu_self_seconds": own.ru_utime + own.ru_stime,
                   "cpu_reaped_children_seconds": children.ru_utime + children.ru_stime,
                   "macos_self_peak_rss_bytes": own.ru_maxrss,
                   "macos_maximum_reaped_child_rss_bytes": children.ru_maxrss,
                   "process_tree_peak_ram_measured": False, "hard_ram_enforcement_claimed": False,
                   "retained_before_receipt_bytes": retained,
                   "reclaimed_submission_snapshot_bytes": reclaimed,
                   "conservative_zip_rewrite_allowance_bytes": 4096,
                   "receipt_and_log_allowance_bytes": 65536, "artifact_cap_bytes": OUTPUT_CAP,
                   "old_no_tools_proof_replayed": False, "model_calls": 0, "provider_calls": 0,
                   "new_fits": 0, "scientific_qualification": False, "new_ai_performance": False}
        pair.write(output / "COMPLETE.json", pair.encode(receipt))
        return receipt
    except BaseException as error:
        pair.write(output / "FAILED.json", pair.encode({"status": "incomplete_control", "error_type": type(error).__name__,
                                                        "retry_allowed": False,
                                                        "wall_seconds_before_failure": time.monotonic() - started}))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("delivery-root", "frozen-file", "frozen-sha256", "python", "legacy-control", "private-locations", "output"):
        parser.add_argument("--" + field, required=True)
    validate(**vars(parser.parse_args()))
