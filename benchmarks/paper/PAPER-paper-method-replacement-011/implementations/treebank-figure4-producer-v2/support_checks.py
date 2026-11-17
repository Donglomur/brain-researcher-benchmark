"""Observe same-case claims without changing or rejecting author computations.

Disagreements produce separate evidence; source outputs remain inspectable.
Missing observations never become invented events, folds or identities.
"""
from __future__ import annotations

from custody import canonical_bytes, digest


class SupportChecks:
    def __init__(self, prepared, windows):
        self.eligible = {subject: set(names) for subject, names in prepared["eligibility"].items()}
        self.runs = prepared["recording_inventory"]
        self.windows = windows
        self.samples = {}
        self.splits = {}
        self.labels = {}
        self.observed_samples = set()
        self.observed_splits = set()
        self.observed_mappings = set()
        self.observed_windows = set()
        self.unavailable = 0
        self.missing_reasons = {}
        self.disagreements = 0

    def _issue(self, event, reason):
        self.disagreements += 1
        return {"event": "source_support_disagreement", "context": event.get("context"),
                "reason": reason, "source_computation_action": "preserved_unchanged",
                "same_case_claim": "unavailable"}

    def observe(self, event):
        context = event.get("context")
        if not isinstance(context, dict):
            return []
        subject, contact = context.get("source_subject"), context.get("contact")
        if subject not in self.eligible or contact not in self.eligible[subject]:
            return [self._issue(event, "observed source context differs from declared eligible support")]
        issues = []
        window = context.get("window")
        key = None
        if window is not None:
            index = window.get("index")
            if type(index) is not int or not 0 <= index < len(self.windows):
                return [self._issue(event, "observed source window is outside the actual grid")]
            expected = self.windows[index]
            key = (subject, contact, index)
            if (window.get("nominal_start") != expected["nominal_start"] or
                    window.get("requested_sample_start") != expected["requested_start_sample"] or
                    window.get("requested_sample_duration") != expected["requested_sample_count"]):
                issues.append(self._issue(event, "source window definition differs from observed original grid"))
            supplied, parent = window.get("supplied_shape"), window.get("parent_shape")
            if supplied and parent:
                actual = max(0, min(parent[-1], expected["requested_start_sample"] + expected["requested_sample_count"]) -
                             expected["requested_start_sample"])
                if supplied[-1] != actual:
                    issues.append(self._issue(event, "source slice extent differs from its actual parent extent"))
        kind = event.get("event")
        if kind == "sampling":
            run = event.get("run_id")
            if run not in self.runs[subject] or event.get("run_subject") != subject:
                issues.append(self._issue(event, "sampling recording differs from original ordered inventory"))
            elif event.get("status") != "observed":
                self.unavailable += 1
            else:
                payload = {name: event.get(name) for name in ("positive", "negative", "concatenation_order",
                           "positive_candidate_count", "negative_candidate_count", "sampling_frequency", "result_shape")}
                identity = digest(canonical_bytes(payload))
                baseline = self.samples.setdefault((subject, run), identity)
                if baseline != identity:
                    issues.append(self._issue(event, "sampled original cases differ across contacts; no resampling applied"))
                self.observed_samples.add((subject, contact, run))
        elif kind == "split" and key is not None:
            if event.get("status") != "observed":
                self.unavailable += 1
            else:
                labels = event.get("dataset_labels")
                partitions = [event.get(name) for name in ("train", "validation", "test")]
                if not isinstance(labels, list) or any(not isinstance(part, list) for part in partitions):
                    issues.append(self._issue(event, "observed split lacks concrete labels/membership lists"))
                else:
                    flat = [index for part in partitions for index in part]
                    valid = (all(type(index) is int for index in flat) and len(set(flat)) == len(flat) and
                             set(flat) == set(range(len(labels))) and not partitions[1])
                    if not valid:
                        issues.append(self._issue(event, "source split is not the complete disjoint original train/test support"))
                    else:
                        if ([labels[index] for index in partitions[0]] != event.get("train_labels") or
                                [labels[index] for index in partitions[2]] != event.get("test_labels")):
                            issues.append(self._issue(event, "source split labels do not match observed positional membership"))
                    identity = digest(canonical_bytes({"partitions": partitions, "labels": labels}))
                    if self.splits.setdefault(subject, identity) != identity:
                        issues.append(self._issue(event, "source cases/splits differ across contacts or windows; source outputs retained"))
                self.observed_splits.add(key)
        elif kind == "label_mapping" and key is not None:
            if event.get("status") != "observed":
                self.unavailable += 1
            else:
                mapping = event.get("mapping")
                valid = (isinstance(mapping, list) and bool(mapping) and
                         all(isinstance(row, dict) and set(row) == {"label", "index"} and
                             type(row["index"]) is int and row["index"] >= 0 for row in mapping))
                if not valid:
                    self.unavailable += 1
                    return issues + [self._issue(event, "observed class mapping lacks concrete label/index associations")]
                associations = [(canonical_bytes(row["label"]).hex(), row["index"]) for row in mapping]
                if (len({row[0] for row in associations}) != len(associations) or
                        len({row[1] for row in associations}) != len(associations)):
                    self.unavailable += 1
                    return issues + [self._issue(event, "observed class mapping has ambiguous associations")]
                # Mapping insertion order is immaterial; raw event order stays in the private stream.
                identity = digest(canonical_bytes(sorted(associations)))
                if self.labels.setdefault(subject, identity) != identity:
                    issues.append(self._issue(event, "actual source class mapping differs across contacts or windows"))
                self.observed_mappings.add(key)
        elif kind == "window_result" and key is not None:
            if event.get("status") == "observed":
                if key in self.observed_windows:
                    issues.append(self._issue(event, "duplicate observed source window result"))
                self.observed_windows.add(key)
                for reason in event.get("unavailable_observations", []):
                    self.unavailable += 1
                    self.missing_reasons[reason] = self.missing_reasons.get(reason, 0) + 1
            else:
                self.unavailable += 1
        return issues

    def summary(self):
        expected_windows = sum(len(names) for names in self.eligible.values()) * len(self.windows)
        expected_samples = sum(len(names) * len(self.runs[subject]) for subject, names in self.eligible.items())
        complete = (len(self.observed_windows) == expected_windows and len(self.observed_splits) == expected_windows and
                    len(self.observed_mappings) == expected_windows and
                    len(self.observed_samples) == expected_samples and self.unavailable == 0)
        return {"source_outputs_preserved": True, "disagreements": self.disagreements,
                "unavailable_observations": self.unavailable,
                "window_unavailable_reasons": dict(self.missing_reasons),
                "expected_window_calls": expected_windows, "observed_window_calls": len(self.observed_windows),
                "observed_split_calls": len(self.observed_splits),
                "observed_label_mapping_calls": len(self.observed_mappings),
                "expected_sampling_calls": expected_samples, "observed_sampling_calls": len(self.observed_samples),
                "same_case_claim": "consistent_in_complete_observed_support" if complete and not self.disagreements else "unavailable",
                "limit": "This is observation consistency, not original-release or scientific-outcome admission."}
