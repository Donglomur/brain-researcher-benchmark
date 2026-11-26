"""Complete generated campaign files, never authentic neural observations.

The only source dataset material used here is the public 686-name RECORDS
roster. All durations, annotations, signal identities, deployment and custody
records are invented controls. Original campaign.run creates the transcripts;
generated peers never request a signal window or invoke an image renderer.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import types

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
DURATION = 120
LIMITS = {"read_bytes": 512 * 1048576, "write_bytes": 64 * 1048576,
          "signal_samples": 100000, "actions": 10000, "seconds": 180}
PAIR_LIMITS = {"read_bytes": 1024 * 1048576, "write_bytes": 128 * 1048576,
               "signal_samples": 100000, "actions": 10000, "seconds": 180}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode() + b"\n"


def ordered_encoded(value):
    return json.dumps(value, sort_keys=False, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode() + b"\n"


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)
    return {"path": str(path), **pin(raw)}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def load_source():
    manifest = (PACKAGE / "SOURCE_MANIFEST.json").read_bytes()
    declared = json.loads(manifest)
    row = next(r for r in declared["files"] if r["name"] == "entry.py")
    raw = (PACKAGE / "entry.py").read_bytes()
    assert pin(raw) == {k: row[k] for k in ("bytes", "sha256")}
    entry = types.ModuleType("generated_neural010_pair_entry")
    entry.__file__ = str(PACKAGE / "entry.py")
    exec(compile(raw, entry.__file__, "exec"), entry.__dict__)
    root, load, reads, source = entry.bootstrap(len(manifest), pin(manifest)["sha256"])
    pair = load("paired_conditions")
    return {"entry": entry, "root": root, "load": load, "reads": reads,
            "source": source, "pair": pair, "replay": load("captured_replay"),
            "legacy": pair.load_legacy(root)}


class GeneratedFixture:
    def __init__(self, root, runtime):
        self.root = Path(root)
        self.root.mkdir(mode=0o700)
        self.runtime, self.legacy = runtime, runtime["legacy"]
        self.u, self.c = self.legacy["u"], self.legacy["campaign"]
        self.source = self.legacy["source"]
        self.public, self.private = self.root / "prepared/public", self.root / "prepared/private"
        self.public.mkdir(parents=True, mode=0o700)
        self.private.mkdir(parents=True, mode=0o700)
        self.roster_raw = (HERE / "CHBMIT_RECORDS.txt").read_bytes()
        assert pin(self.roster_raw) == self.u.c.RECORDS_PIN
        roster = self.u.c.roster(self.roster_raw)
        self.roster_desc = write(self.root / "RECORDS", self.roster_raw)
        self.rows, panels, provenance, targets = [], [], [], []
        labels = ["FP1-F7", "FP1-F7"]
        montage = hashlib.sha256(encoded(sorted(labels))[:-1]).hexdigest()
        for source, person in sorted(roster.items()):
            rid, pid = digest(source)[:24], digest(person)[:24]
            projection = pin(b"GENERATED UNOPENED PROJECTION")
            source_pin = pin(("GENERATED EDF IDENTITY:" + source).encode())
            row = {"recording_id": rid, "patient_id": pid, "duration_seconds": DURATION,
                   "montage_id": montage, "channel_count": 2, "channel_labels": list(labels),
                   "source_edf": source_pin, "target_free_projection": projection}
            self.rows.append(row)
            panels.append({"recording_id": rid, "patient_id": pid, "duration_seconds": DURATION,
                           "observed_intervals": [[0, DURATION]], "path": "signals/" + rid + ".h5", **projection})
            provenance.append({"recording_id": rid, "source_path": source, "source_edf": source_pin,
                               "header": {"generated_only": True}, "annotation_evidence": {"generated_only": True}})
            targets.append({"recording_id": rid, "events": [[0, 1]]})
        self.rows.sort(key=lambda r: r["recording_id"])
        panels.sort(key=lambda r: r["recording_id"])
        provenance.sort(key=lambda r: r["recording_id"])
        targets.sort(key=lambda r: r["recording_id"])
        self.people = sorted({r["patient_id"] for r in self.rows})
        assert len(self.rows) == 686 and len(self.people) == 23
        panel_raw = encoded({"schema_version": 1, "task_id": "NEURAL-009", "records": panels})
        self.panel = write(self.public / "panel.json", panel_raw)
        self.metadata = write(self.public / "metadata.json", encoded({"schema": "neural010-target-free-metadata-v1", "records": self.rows}))
        self.provenance = write(self.private / "SOURCE_PROVENANCE.json", encoded({"records": provenance}))
        self.assessment_raw = encoded({"schema_version": 1, "task_id": "NEURAL-009",
                                       "panel_sha256": self.panel["sha256"], "records": targets})
        self.assessment = write(self.private / "assessment.json", self.assessment_raw)
        self.views = []
        unused = pin(b"GENERATED UNMATERIALIZED INNER VIEW")
        for person in self.people:
            # Real final training views allow the existing source to construct
            # the explicitly unmatched other22 negative control.
            document = {"schema": "neural010-detector-view-v1", "task_id": "NEURAL-010",
                        "outer_person": person, "inner_person": None, "role": "training",
                        "records": [dict(r, events=[[0, 1]]) for r in self.rows if r["patient_id"] != person]}
            folder = self.private / "views" / person / "final"
            train = write(folder / "TRAIN.json", encoded(document))
            query = write(folder / "QUERY.json", b"GENERATED STAT-ONLY QUERY")
            support = write(folder / "SUPPORT.json", b"GENERATED STAT-ONLY SUPPORT")
            self.views.append({"name": person + "/final", "artifacts": {
                "TRAIN.json": self.u.c.bare(train), "QUERY.json": self.u.c.bare(query),
                "SUPPORT.json": self.u.c.bare(support)}})
            for inner in self.people:
                if inner != person:
                    self.views.append({"name": person + "/inner/" + inner,
                                       "artifacts": {n: dict(unused) for n in
                                           ("TRAIN.json", "QUERY.json", "SUPPORT.json", "VALIDATION.json")}})
        receipt = {"schema": "neural010-original-preparation-v1",
                   "status": "prepared_not_runtime_or_scientifically_qualified",
                   "records": 686, "people": 23, "source_folders": 24,
                   "source_manifest": self.u.c.ORIGINAL_MANIFEST, "source_roster": self.u.c.LOCK,
                   "global_assessment_release_authorized": False,
                   "panel": self.u.c.bare(self.panel), "metadata": self.u.c.bare(self.metadata),
                   "assessment": self.u.c.bare(self.assessment), "source_provenance": self.u.c.bare(self.provenance),
                   "views": self.views, "vendor_sources": self.u.c.VENDOR_PIN,
                   "annotation_reads": pin(b"GENERATED ANNOTATION DECLARATION"), "actual_models_or_scores": 0,
                   "cost_snapshot": {"original_origin": 1.0, "deadline": 1001.0,
                       "logical_reserved_read_bytes": 1000, "logical_reserved_write_bytes": 1000,
                       "limits": {"read_bytes": 10**9, "write_bytes": 10**9,
                                  "whole_seconds": 1000.0, "project_peak_bytes": 10**9},
                       "physical_IO_or_RSS_measured": False}}
        self.receipt = write(self.private / "PREPARATION.json", encoded(receipt))
        self.preparation = {"schema": "neural010-preparation-compatibility-selection-v1", "route": "original",
                            "receipt": self.receipt, "public_root": str(self.public), "private_root": str(self.private),
                            "records": self.roster_desc, "selected_source_manifest": self.u.c.ORIGINAL_MANIFEST,
                            "selected_original_roster": self.u.c.LOCK}
        self.io_roots = [str(self.root), str(self.legacy["root"])]
        io = self.u.IO(self.io_roots, self.u.Budget(LIMITS))
        detector = self.c.library(self.legacy["root"], io)
        prepared = self.u.c.admit(self.preparation, io)
        projection = self.u.c.export_detection(prepared, self.legacy["root"] / "vendor/detection-interface-v1", io)["projection"]
        self.scientific_panel = projection["scientific_panel"]
        self.support = projection["support"]
        self.reference_pins, self.reference_runs = self.references(self.root / "references")
        self.campaigns = {}
        self.count_signal_reads = 0

    def references(self, root, *, changed=False):
        refs, runs = {}, {}
        for arm in ("matched_no_eeg", "signal_reference", "montage_only"):
            records = [{"recording_id": row["recording_id"], "events": [[0, 1]] if changed else []}
                       for row in self.rows]
            raw = encoded({"schema": "neural010-scientific-events-v2", "panel_sha256": pin(self.scientific_panel)["sha256"],
                           "arm": arm, "records": records})
            refs[arm] = write(root / (arm + ".json"), raw)
            closed = write(root / (arm + ".closure.json"), encoded({"generated_only": True, "arm": arm}))
            run = {"schema": "neural010-reference-run-binding-v1", "arm": arm,
                   "stream": self.u.c.bare(refs[arm]), "held_people": self.people,
                   "source_identity": pin(b"GENERATED REFERENCE SOURCE"), "training_protocol": pin(b"GENERATED TRAINING"),
                   "tuning_protocol": pin(b"GENERATED TUNING"), "resource_protocol": pin(b"GENERATED RESOURCES"),
                   "closure_evidence": closed}
            runs[arm] = write(root / (arm + ".run.json"), encoded(run))
        return refs, runs

    def _peers(self, answers):
        owner = self
        def factory(io, root, context, role, cap):
            class Peer:
                def __init__(self):
                    self.seq = 0
                    io.directory(root)

                def request(self, value):
                    io.budget.charge("actions", 1)
                    self.seq += 1
                    packet = {"schema": "neural010-service-request-v1", "context_id": context,
                              "role": role, "sequence": self.seq, "body": value}
                    desc = io.create(Path(root) / ("request-" + str(self.seq) + ".json"), encoded(packet))
                    if role == "custody":
                        if value["operation"] == "freeze_state":
                            reply = {"schema": "neural010-external-state-freeze-v1", "context_id": context,
                                     "request_sha256": desc["sha256"], "candidate_contract": value["candidate_contract"],
                                     "fold_state_sha256": value["fold_state_sha256"], "training_complete": True,
                                     "held_query_not_delivered": True, "state_immutable_for_query": True}
                        else:
                            reply = {"schema": "neural010-external-context-receipt-v1", "operation": value["operation"],
                                     "context_id": context, "request_sha256": desc["sha256"],
                                     "status": "isolated_context_started" if value["operation"] == "launch" else "natural_exit_and_context_retired",
                                     "fold_state_sha256": value.get("fold_state_sha256"), "submission": value.get("submission")}
                    elif role == "participant" and value["operation"] == "initialize":
                        reply = {"kind": "ready", "method_sha256": value["method_sha256"],
                                 "fold_state_sha256": digest("GENERATED STATE:" + context)}
                    elif role == "participant" and value["operation"] == "held_person_query":
                        query = value["query"]
                        rows = [{"recording_id": r["recording_id"], "events": copy.deepcopy(answers)} for r in query["records"]]
                        reply = {"kind": "submit", "submission": {"schema": "neural010-detection-submission-v1",
                                 "query_sha256": hashlib.sha256(encoded(query)[:-1]).hexdigest(), "records": rows}}
                    else:
                        raise AssertionError("generated peer must not observe signals or render")
                    raw = encoded({"schema": "neural010-service-response-v1", "context_id": context, "role": role,
                                   "sequence": self.seq, "request_sha256": desc["sha256"], "body": reply})
                    assert len(raw) <= cap
                    io.budget.charge("read_bytes", len(raw) + 1)
                    return reply, raw, desc
            return Peer()
        return factory

    def campaign(self, label, mode, answers, *, training="none", refs=None, context_alias=None,
                 namespace_alias=None, learning=None, reverse_reference_order=False):
        assert label not in self.campaigns
        where = self.root / "campaign-inputs" / label
        refs, runs = refs or (self.reference_pins, self.reference_runs)
        serializer = encoded
        if reverse_reference_order:
            # The source accepts JSON object order; retain the actual reverse
            # acquisition sequence instead of canonicalizing it away here.
            refs = {key: refs[key] for key in sorted(refs, reverse=True)}
            runs = {key: runs[key] for key in sorted(runs, reverse=True)}
            serializer = ordered_encoded
        policy = {"training": training, "max_actions_per_fold": 10, "max_samples_per_request": 64,
                  "max_channels_per_request": 2, "frame_bytes": 1048576,
                  "delivery": "rendered_pixels" if mode == "typed_viewer" else "calibrated_windows",
                  "display_half_range_microvolts": 100.0 if mode == "typed_viewer" else None}
        contract = {k: digest("GENERATED COMMON:" + k) for k in self.c.CONTRACT_FIELDS}
        contract["method_sha256"] = digest("GENERATED METHOD:" + label)
        contract["training_policy_sha256"] = pin(encoded({"training": training}))["sha256"]
        contract["tool_policy_sha256"] = pin(encoded({"mode": mode, "policy": policy}))["sha256"]
        contract["resource_policy_sha256"] = pin(encoded(LIMITS))["sha256"]
        if learning is not None:
            contract["learning_policy_sha256"] = learning
        contexts = {}
        for person in self.people:
            folder = self.root / "exchanges" / (namespace_alias or label) / person
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            contexts[person] = {"context_id": digest("GENERATED CONTEXT:" + (context_alias or label) + ":" + person),
                                "participant_exchange": str(folder / "participant"), "custody_exchange": str(folder / "custody"),
                                "renderer_exchange": str(folder / "renderer") if mode == "typed_viewer" else None}
        proof = {"schema": "neural010-independent-reference-binding-v1", "evidence_class": "generated_control",
                 "reference_pins": {k: self.u.c.bare(v) for k, v in refs.items()}, "candidate_contract": contract,
                 "interpretation": "fixed_reference_comparison", "reference_runs": runs, "matching_evidence": None}
        proof_desc = write(where / "reference-provenance.json", serializer(proof))
        evaluation = {"schema": "neural010-event-evaluation-selection-v1", "references": refs,
                      "reference_provenance": proof_desc, "interpretation": "fixed_reference_comparison",
                      "candidate_contract": contract, "original_panel": self.u.c.bare(self.panel),
                      "original_assessment": self.u.c.bare(self.assessment)}
        eval_desc = write(where / "evaluation.json", serializer(evaluation))
        request = {"schema": "neural010-event-campaign-request-v1", "source": self.source,
                   "preparation": self.preparation, "mode": mode, "candidate_contract": contract,
                   "policy": policy, "contexts": contexts, "limits": dict(LIMITS), "evaluation": eval_desc}
        request_raw = encoded(request)
        caps = ["fresh_context_per_person", "only_current_fold_allowlist", "no_controller_filesystem", "no_cross_fold_memory",
                "independent_launch_and_close", "read_only_signals", policy["delivery"]]
        if mode == "typed_viewer":
            caps += ["no_code_execution", "no_raw_array_or_svg_export", "no_task_specific_detector_tools", "visual_observation_only"]
        deployment = {"schema": "neural010-event-deployment-binding-v1", "campaign_request": pin(request_raw),
                      "source": self.source, "evidence_class": "generated_control", "context_ids": sorted(v["context_id"] for v in contexts.values()),
                      "mode": mode, "capabilities": caps}
        deployment_desc = write(where / "deployment.json", encoded(deployment))
        authority = {"schema": "neural010-event-campaign-authority-v1", "request": pin(request_raw),
                     "source": self.source, "evidence_class": "generated_control", "deployment_receipt": deployment_desc,
                     "context_ids": deployment["context_ids"]}
        authority_raw = encoded(authority)
        io = self.u.IO(self.io_roots, self.u.Budget(LIMITS))
        out = self.root / "campaigns" / label
        out.parent.mkdir(exist_ok=True, mode=0o700)
        class NoSignals:
            def __init__(self, *args):
                pass
            def window(self, *args):
                raise AssertionError("no authentic or generated signal operation selected")
        complete = self.c.run(request_raw, authority_raw, pin(authority_raw), source_pin=self.source,
                              source_root=self.legacy["root"], output_root=out, io=io,
                              signal_factory=NoSignals, exchange_factory=self._peers(answers))
        result = {"root": out, "complete": complete, "request": request, "request_raw": request_raw,
                  "run_costs": dict(io.budget.used), "answers": copy.deepcopy(answers)}
        self.campaigns[label] = result
        return result

    def score_envelopes(self, campaign, root, *, assessment=None):
        assessment = assessment or self.assessment
        request = {"schema": "neural010-event-score-request-v1", "source": self.source,
                   "campaign": campaign["complete"],
                   "campaign_request": {"path": str(campaign["root"] / "SELECTED_REQUEST.json"), **pin(campaign["request_raw"])},
                   "limits": dict(LIMITS)}
        raw = encoded(request)
        authority = {"schema": "neural010-event-score-authority-v1", "request": pin(raw),
                     "campaign": campaign["complete"], "source": self.source,
                     "evidence_class": "generated_control", "assessment": assessment}
        return {"request": write(Path(root) / "score-request.json", raw),
                "authority": write(Path(root) / "score-authority.json", encoded(authority))}

    def pair_selection(self, root, left, right, *, assessment=None, limits=None, capture_bytes=128 * 1048576):
        root = Path(root)
        root.mkdir(parents=True, mode=0o700)
        left_selection = self.score_envelopes(left, root / "left")
        right_selection = self.score_envelopes(right, root / "right")
        request = {"schema": "neural010-paired-condition-request-v1", "source": self.runtime["source"],
                   "left": left_selection, "right": right_selection,
                   "limits": dict(limits or PAIR_LIMITS), "capture_bytes": capture_bytes}
        raw = encoded(request)
        authority = {"schema": "neural010-paired-condition-authority-v1", "request": pin(raw),
                     "source": self.runtime["source"], "left": left_selection, "right": right_selection,
                     "assessment": assessment or self.assessment, "evidence_class": "generated_control",
                     "interpretation": "descriptive_zero_training_access_conditions"}
        auth = encoded(authority)
        write(root / "paired-request.json", raw)
        write(root / "paired-authority.json", auth)
        return raw, auth, pin(auth)

    def clone_campaign(self, campaign, root):
        root = Path(root)
        root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(campaign["root"], root, copy_function=shutil.copyfile)
        return {**campaign, "root": root,
                "complete": {"path": str(root / "CAMPAIGN.json"), **pin((root / "CAMPAIGN.json").read_bytes())}}

    def missing_second_record(self, campaign, root):
        """Retain coherent custody binding while breaking the scientific roster."""
        copied = self.clone_campaign(campaign, root)
        complete = read_json(copied["root"] / "CAMPAIGN.json")
        fold = complete["folds"][0]
        folder = copied["root"] / fold["person"]
        submission = read_json(folder / "SUBMISSION.json")
        submission["records"].pop()
        raw = encoded(submission)
        (folder / "SUBMISSION.json").write_bytes(raw)
        fold["submission"] = pin(raw)
        close = read_json(folder / "CLOSE_REQUEST.json")
        close["body"]["submission"] = pin(raw)
        close_raw = encoded(close)
        (folder / "CLOSE_REQUEST.json").write_bytes(close_raw)
        fold["close_request"] = pin(close_raw)
        closed = read_json(folder / "CLOSURE.json")
        closed["request_sha256"] = pin(close_raw)["sha256"]
        closed["body"]["request_sha256"] = pin(close_raw)["sha256"]
        closed["body"]["submission"] = pin(raw)
        closed_raw = encoded(closed)
        (folder / "CLOSURE.json").write_bytes(closed_raw)
        fold["closure"] = pin(closed_raw)
        final = encoded(complete)
        (copied["root"] / "CAMPAIGN.json").write_bytes(final)
        copied["complete"] = {"path": str(copied["root"] / "CAMPAIGN.json"), **pin(final)}
        return copied
