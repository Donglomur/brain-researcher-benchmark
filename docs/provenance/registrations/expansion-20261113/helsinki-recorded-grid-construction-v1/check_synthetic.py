"""Selected synthetic engineering checks; never admit a synthetic production Corpus.

Run only after exact whole-source/launcher review. This imports the selected
shared implementations, uses an explicit FixtureCorpus for complete invented
82-asset/79-infant consumer integration, and exercises low-level refusal fixtures.
No authentic EEG/annotation bodies, model, network or scientific performance
study is used by this synthetic invocation.
"""
import csv
import hashlib
import hmac
import io
import json
import math
import os
from dataclasses import replace
from pathlib import Path
import struct
import sys



BASE_CONTROL_IDS = (
    "P1_layout", "P1_auxiliary_offsets", "P1_calibrated_montage",
    "P2_c_marker_decode", "P2_c_payload_equivalence", "P2_distinct_header_identity",
    "P3_profile_metadata_census", "P3_fixture_header_not_production",
    "P3_fixture_asset_not_production", "P3_fixture_manifest_not_production",
    "P4_ref_alias_equivalence", "P4_strict_original_upper_refusal",
    "P5_first_data_is_second_zero", "P5_last_data_is_final_second",
    "P5_all79_three_streams", "P6_first_context_boundary", "P6_last_context_boundary",
    "P6_future_record_excluded", "P6_future_record_in_later_window",
    "P6_recorded_zero_and_flags_retained", "P7_full79_primary_census",
    "P7_macro_brier_arithmetic", "P7_three_expert_identity",
    "P8_paired_packet_bytes", "P8_control_flags_preserved", "P8_control_signals_differ",
    "N1_d_marker", "N1_unknown_marker", "N1_annotation_channel", "N1_strict_c_marker",
    "N2_modified_source_header", "N2_wrong_source_size", "N2_wrong_source_checksum",
    "N2_truncated_header", "N2_extra_record_size", "N2_stale_asset_descriptor",
    "N3_zero_records", "N3_nonunit_record_duration", "N3_wrong_eeg_rate",
    "N3_wrong_eeg_units", "N3_nonfinite_calibration", "N3_degenerate_calibration",
    "N3_invalid_digital_range", "N3_missing_electrode", "N3_duplicate_alias", "N3_fuzzy_alias",
    "N3_outside_digital_sample", "N3_before_first_case",
    "N3_after_last_case", "N4_missing_header", "N4_headerless",
    "N4_reordered_header", "N4_duplicate_header_id", "N4_extra_header_id",
    "N4_bom", "N4_wrong_delimiter", "N4_wrong_width", "N4_header_inside_data",
    "N4_nonbinary_interior", "N4_nonempty_padding", "N4_missing_last_record",
    "N4_extra_record", "N4_binary_whitespace", "N4_binary_coercion",
    "N5_missing_infant4_case", "N5_missing_infant29_case", "N5_missing_infant50_case",
    "N5_missing_expert", "N6_legacy_namespace_differs", "N6_changed_lineage_namespace",
    "N6_invalid_namespace_input", "N6_partial_lineage_refusal", "N6_fake_training_view",
    "N6_fake_prior_admission", "N6_fake_external_baseline", "N7_packet_field_inventory",
    "N7_invalid_quality_flags", "N8_unestablished_has_no_score",
    "N8_nonfinite_probability", "N8_fixture_not_complete_corpus",
)
INTEGRATION_CONTROL_IDS = ('P3_invented_full82_intake', 'N2_canonical_name_wrong_official_checksum', 'P3_invented_not_production_profile', 'N8_production_corpus_refuses_fixture', 'N8_production_session_refuses_fixture', 'P7_invented_full79_80case_support', 'P5_invented_three_expert_index_mapping', 'N6_fixture_namespace_distinct', 'P8_actual_trainonly_prior_mask_noise', 'N6_actual_trainview_held_target_refusal', 'N6_actual_stale_baseline_refusal', 'N6_actual_foreign_fit_role_refusal', 'N8_program_requires_prefreeze', 'N8_program_commitment_immutable', 'P8_actual_paired_A_B_all5folds', 'P8_actual_controls_original_flags', 'P7_actual_full79_scored_census', 'P7_actual_soft_expert_identity', 'N8_production_scorer_refuses_fixture', 'N8_production_paired_scorer_refuses_fixture', 'N6_actual_prediction_receipt_tamper', 'N6_actual_owner_original_tamper', 'N6_actual_case_identity_tamper', 'N5_actual_missing_scored_case', 'N5_actual_missing_fold', 'N8_actual_budget_overrun', 'N8_actual_budget_failure_permanent', 'N7_actual_packets_no_owner_cues', 'N2_cached_waveform_mutation_refusal')
CONTROL_IDS = BASE_CONTROL_IDS + INTEGRATION_CONTROL_IDS
MAX_ARTIFACT_BYTES = 120 * 1024 ** 2
WIDTHS = (("label", 16), ("transducer", 80), ("unit", 8), ("min", 8),
          ("max", 8), ("dmin", 8), ("dmax", 8), ("filter", 80),
          ("samples", 8), ("reserved", 32))


class Checks:
    def __init__(self):
        self.rows = []
        self.seen = set()

    def check(self, name, condition):
        if (name not in CONTROL_IDS or name in self.seen or not condition or
                len(self.rows) >= len(CONTROL_IDS) or CONTROL_IDS[len(self.rows)] != name):
            raise AssertionError("failed_or_invalid_control:" + name)
        self.seen.add(name)
        self.rows.append({"id": name, "status": "PASS"})

    def refuses(self, name, call, accepted=None):
        accepted = (intake.Refusal,) if accepted is None else accepted
        try:
            call()
        except accepted:
            self.check(name, True)
        else:
            self.check(name, False)


def field(value, width):
    raw = str(value).encode("ascii")
    if len(raw) > width:
        raise AssertionError("fixture_field_overflow")
    return raw.ljust(width, b" ")


def make_fixture(marker="", suffix="Ref", future_delta=0, record_count=32):
    electrodes = sorted(intake.ELECTRODES)
    labels = ["ECG synthetic"] + ["EEG " + e + "-" + suffix for e in electrodes[:7]]
    labels += ["Resp synthetic"] + ["EEG " + e + "-" + suffix for e in electrodes[7:]]
    electrode_number = {e: j for j, e in enumerate(electrodes)}
    channels = []
    for label in labels:
        electrode = next((e for e in electrodes if label == "EEG " + e + "-" + suffix), None)
        j = electrode_number[electrode] if electrode is not None else None
        gain = j + 1 if j is not None else 1
        offset = j * gain if j is not None else 0
        channels.append({"label": label, "transducer": "SYNTHETIC", "unit": "uV",
                         "min": -32768 * gain + offset, "max": 32767 * gain + offset,
                         "dmin": -32768, "dmax": 32767, "filter": "",
                         "samples": 256 if j is not None else (3 if label.startswith("ECG") else 5),
                         "reserved": "", "electrode": electrode, "j": j})
    header_size = 256 * (len(channels) + 1)
    fixed = b"".join((field(0, 8), field("SYNTHETIC_NOT_A_PATIENT", 80),
                      field("SYNTHETIC_COMPONENT_FIXTURE", 80), field("01.01.00", 8),
                      field("00.00.00", 8), field(header_size, 8), field(marker, 44),
                      field(record_count, 8), field(1, 8), field(len(channels), 4)))
    header = fixed + b"".join(field(ch[key], width) for key, width in WIDTHS for ch in channels)
    records = []
    for record in range(record_count):
        for ch in channels:
            j = ch["j"]
            if j is None:
                values = [-30000 + s for s in range(ch["samples"])]
            else:
                values = [(-j if record == 5 else record * 100 + j * 10 + s % 7)
                          + (future_delta if record == 31 and j == 0 else 0)
                          for s in range(ch["samples"])]
            records.append(struct.pack("<" + str(len(values)) + "h", *values))
    return header, b"".join(records), channels, electrode_number


def changed_fixed(raw, start, width, value):
    return raw[:start] + field(value, width) + raw[start + width:]


def changed_channel(raw, channels, key, index, value):
    start = 256
    for name, width in WIDTHS:
        if name == key:
            return changed_fixed(raw, start + index * width, width, value)
        start += len(channels) * width
    raise AssertionError("unknown_fixture_channel_field")


def csv_bytes(rows):
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    return output.getvalue().encode("ascii")


def synthetic_rows(durations, expert=0):
    return [list(map(str, intake.INFANTS))] + [
        [str((i + k + expert) % 2) if k < durations[i] else "" for i in intake.INFANTS]
        for k in range(32)]


def expected_bipolar(electrode_numbers, a, b, record, sample):
    def physical(e):
        j = electrode_numbers[e]
        value = -j if record == 5 else record * 100 + j * 10 + sample % 7
        return (value + j) * (j + 1)
    return physical(a) - physical(b)


def run(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    checks = Checks()
    artifacts = []
    assets = []
    mutations = []
    written = 0

    def write(name, data):
        nonlocal written
        if written + len(data) > MAX_ARTIFACT_BYTES:
            raise AssertionError("synthetic_artifact_cap")
        path = root / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        written += len(data)
        artifacts.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return path

    def mutate_append(name, data):
        nonlocal written
        if written + len(data) > MAX_ARTIFACT_BYTES:
            raise AssertionError("synthetic_mutation_artifact_cap")
        path = root / name
        with path.open("ab") as handle:
            handle.write(data)
        written += len(data)
        mutations.append({"name": name, "operation": "intentional_append_for_refusal_control",
                          "bytes_appended": len(data), "final_bytes": path.stat().st_size,
                          "final_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    def fixture_asset(name, content):
        write(name, content)
        item = intake.Asset(root, {"name": name, "bytes": len(content),
                                  "md5": hashlib.md5(content, usedforsecurity=False).hexdigest()})
        assets.append(item)
        return item

    def decode(raw, total, marker=""):
        return intake.decode_fixed_record_header(io.BytesIO(raw), total, marker)

    try:
        raw, data, channels, numbers = make_fixture()
        total = len(raw) + len(data)
        header = decode(raw, total)
        asset = fixture_asset("synthetic_blank.edf", raw + data)
        first = intake.read_recorded_window(asset, header, 29)
        last = intake.read_recorded_window(asset, header, 31)
        checks.check("P1_layout", header.records == 32 and len(header.channels) == 21 and
                     len(header.electrode_indices) == 19 and len(first) == 18)
        offsets = []
        cursor = 0
        for ch in channels:
            offsets.append(cursor)
            cursor += 2 * ch["samples"]
        checks.check("P1_auxiliary_offsets", [ch.byte_offset for ch in header.channels] == offsets and
                     header.record_bytes == cursor and header.channels[0].samples == 3 and
                     header.channels[8].samples == 5)
        checks.check("P1_calibrated_montage", all(
            math.isclose(first[c][r * 256 + m], expected_bipolar(numbers, a, b, r, m), abs_tol=1e-8)
            for c, (a, b) in enumerate(intake.MONTAGE) for r, m in ((0, 0), (5, 17), (17, 255), (29, 7))))
        raw_c, data_c, _, _ = make_fixture("EDF+C")
        header_c = decode(raw_c, len(raw_c) + len(data_c), "EDF+C")
        asset_c = fixture_asset("synthetic_c.edf", raw_c + data_c)
        checks.check("P2_c_marker_decode", header_c.records == header.records and data_c == data)
        checks.check("P2_c_payload_equivalence", intake.read_recorded_window(asset_c, header_c, 29) == first)
        checks.check("P2_distinct_header_identity", header_c.sha256 != header.sha256 and
                     raw_c[192:236].strip() == b"EDF+C")
        profiles = profile.source_profiles()
        checks.check("P3_profile_metadata_census", len(profiles["headers"]) == 79 and
                     set(profiles["exceptions"]) == {4, 29, 50} and len(profiles["annotations"]) == 3)
        authentic_meta = profiles["headers"][4]
        checks.refuses("P3_fixture_header_not_production", lambda: intake.inspect_profile_header(
            raw_c, "eeg4.edf", authentic_meta["published_bytes"], authentic_meta["published_md5"]))
        checks.refuses("P3_fixture_asset_not_production", lambda: intake.read_helsinki_recorded_grid_header(asset_c))
        fake_manifest = write("fixture_manifest.json", b"{}\n")
        checks.refuses("P3_fixture_manifest_not_production", lambda: intake.Corpus(root, fake_manifest))
        raw_ref, data_ref, _, _ = make_fixture(suffix="REF")
        header_ref = decode(raw_ref, len(raw_ref) + len(data_ref))
        asset_ref = fixture_asset("synthetic_upper.edf", raw_ref + data_ref)
        checks.check("P4_ref_alias_equivalence", intake.read_recorded_window(asset_ref, header_ref, 29) == first)
        checks.refuses("P4_strict_original_upper_refusal", lambda: intake.read_header(io.BytesIO(raw_ref), total))
        durations = {i: 30 + i % 3 for i in intake.INFANTS}
        streams = [intake.parse_recorded_grid_csv(io.BytesIO(csv_bytes(synthetic_rows(durations, e))),
                                                durations, 32) for e in range(3)]
        checks.check("P5_first_data_is_second_zero", all(streams[e][i][0] == (i + e) % 2
                     for i in intake.INFANTS for e in range(3)))
        checks.check("P5_last_data_is_final_second", all(streams[e][i][-1] == (i + durations[i] - 1 + e) % 2
                     for i in intake.INFANTS for e in range(3)))
        checks.check("P5_all79_three_streams", len(streams) == 3 and all(
            set(s) == set(intake.INFANTS) and all(len(s[i]) == durations[i] for i in intake.INFANTS)
            for s in streams))
        checks.check("P6_first_context_boundary", all(len(ch) == 30 * 256 for ch in first) and
                     all(math.isclose(first[c][0], expected_bipolar(numbers, a, b, 0, 0), abs_tol=1e-8)
                         for c, (a, b) in enumerate(intake.MONTAGE)))
        checks.check("P6_last_context_boundary", all(
            math.isclose(last[c][0], expected_bipolar(numbers, a, b, 2, 0), abs_tol=1e-8) and
            math.isclose(last[c][-1], expected_bipolar(numbers, a, b, 31, 255), abs_tol=1e-8)
            for c, (a, b) in enumerate(intake.MONTAGE)))
        future_raw, future_data, _, _ = make_fixture(future_delta=100)
        future_asset = fixture_asset("synthetic_future.edf", future_raw + future_data)
        checks.check("P6_future_record_excluded", intake.read_recorded_window(future_asset, header, 29) == first)
        checks.check("P6_future_record_in_later_window", intake.read_recorded_window(future_asset, header, 31) != last)
        flags = intake.derive_quality_flags(first)
        last_flags = intake.derive_quality_flags(last)
        checks.check("P6_recorded_zero_and_flags_retained", flags.zero_bipolar[5] and flags.any_flatline[5] and last_flags.zero_bipolar[3] and
                     all(v == 0 for ch in first for v in ch[5 * 256:6 * 256]))

        class SyntheticMathOnly:
            def seconds(self, infant):
                return range(29, 30 + infant % 2)
            def votes(self, infant, second):
                return (0, 1, 1) if second == 29 else (1, 0, 0)

        toy = SyntheticMathOnly()
        predictions = {(i, k): (0.5 if i % 2 else 0.2) for i in intake.INFANTS for k in toy.seconds(i)}
        losses = scorer._loss_kernel(toy, predictions)
        expected_macro = sum(sum(((0.5 if i % 2 else 0.2) - (2 / 3 if k == 29 else 1 / 3)) ** 2
                                 for k in toy.seconds(i)) / len(toy.seconds(i)) for i in intake.INFANTS) / 79
        checks.check("P7_full79_primary_census", losses["infant_count"] == 79 and
                     losses["case_count"] == sum(len(toy.seconds(i)) for i in intake.INFANTS))
        checks.check("P7_macro_brier_arithmetic", math.isclose(losses["soft_vote_brier"], expected_macro,
                     rel_tol=1e-12, abs_tol=1e-12))
        checks.check("P7_three_expert_identity", math.isclose(losses["mean_expert_brier"],
                     expected_macro + 2 / 9, abs_tol=1e-12) and len(losses["expert_brier"]) == 3)
        key = b"synthetic-owner-only-key-32-bytes!!"
        lineage_sha = "a" * 64
        case_id = protocol.case_identifier(key, 0, 1, 29, lineage_sha)
        packet_a = protocol.public_packet(case_id, first, flags)
        packet_b = protocol.public_packet(case_id, first, flags)
        amp = protocol.projected_signal(first, "amplitude_only")
        noise_fit = protocol.NoiseFit((0.0,) * 18, (1.0,) * 18, (), 0, lineage_sha)
        noise = protocol.projected_signal(first, "training_noise", noise_fit, b"x" * 32)
        packets = [json.loads(packet_a), json.loads(protocol.public_packet(case_id, amp, flags)),
                   json.loads(protocol.public_packet(case_id, noise, flags))]
        checks.check("P8_paired_packet_bytes", packet_a == packet_b)
        checks.check("P8_control_flags_preserved", all(p["quality_flags"] == packets[0]["quality_flags"]
                     and p["target_relative_interval"] == [29, 30] for p in packets))
        checks.check("P8_control_signals_differ", amp != first and noise != first and
                     protocol.projected_signal(first, "recorded_eeg") == first)
        checks.refuses("N1_d_marker", lambda: decode(changed_fixed(raw, 192, 44, "EDF+D"), total, "EDF+D"))
        checks.refuses("N1_unknown_marker", lambda: decode(changed_fixed(raw, 192, 44, "UNKNOWN"), total, "UNKNOWN"))
        checks.refuses("N1_annotation_channel", lambda: decode(changed_channel(raw, channels, "label", 0, "EDF Annotations"), total))
        checks.refuses("N1_strict_c_marker", lambda: intake.read_header(io.BytesIO(raw_c), total))
        checks.refuses("N2_modified_source_header", lambda: intake.inspect_profile_header(
            changed_fixed(raw_c, 244, 8, 2), "eeg4.edf", authentic_meta["published_bytes"], authentic_meta["published_md5"]))
        checks.refuses("N2_wrong_source_size", lambda: intake.inspect_profile_header(
            raw_c, "eeg4.edf", authentic_meta["published_bytes"] - 2, authentic_meta["published_md5"]))
        checks.refuses("N2_wrong_source_checksum", lambda: intake.inspect_profile_header(
            raw_c, "eeg4.edf", authentic_meta["published_bytes"], "0" * 32))
        checks.refuses("N2_truncated_header", lambda: decode(raw[:-1], total))
        checks.refuses("N2_extra_record_size", lambda: decode(raw, total + header.record_bytes))
        stale = fixture_asset("synthetic_stale.bin", b"ABCD")
        mutate_append("synthetic_stale.bin", b"E")
        checks.refuses("N2_stale_asset_descriptor", stale.check_unchanged)
        eeg = next(index for index, ch in enumerate(channels) if ch["electrode"] is not None)
        checks.refuses("N3_zero_records", lambda: decode(changed_fixed(raw, 236, 8, 0), total))
        checks.refuses("N3_nonunit_record_duration", lambda: decode(changed_fixed(raw, 244, 8, 2), total))
        for name, item, value in (("N3_wrong_eeg_rate", "samples", 128), ("N3_wrong_eeg_units", "unit", "mV"),
                                  ("N3_nonfinite_calibration", "min", "nan"), ("N3_degenerate_calibration", "max", channels[eeg]["min"]),
                                  ("N3_invalid_digital_range", "dmax", -32768)):
            checks.refuses(name, lambda item=item, value=value: decode(changed_channel(raw, channels, item, eeg, value), total))
        checks.refuses("N3_missing_electrode", lambda: decode(changed_channel(raw, channels, "label", eeg, "EEG Unknown-Ref"), total))
        duplicate = changed_channel(raw, channels, "label", 0, channels[eeg]["label"].replace("-Ref", "-REF"))
        duplicate = changed_channel(duplicate, channels, "samples", 0, 256)
        checks.refuses("N3_duplicate_alias", lambda: decode(duplicate, total))
        checks.refuses("N3_fuzzy_alias", lambda: decode(changed_channel(raw, channels, "label", eeg, "X" + channels[eeg]["label"]), total))
        checks.refuses("N3_outside_digital_sample", lambda: header.channels[eeg].physical(32768))
        checks.refuses("N3_before_first_case", lambda: intake.read_recorded_window(asset, header, 28))
        checks.refuses("N3_after_last_case", lambda: intake.read_recorded_window(asset, header, 32))
        base_rows = synthetic_rows(durations)

        def csv_refusal(name, edit):
            rows = [list(r) for r in base_rows]
            edit(rows)
            checks.refuses(name, lambda: intake.parse_recorded_grid_csv(io.BytesIO(csv_bytes(rows)), durations, 32))

        checks.refuses("N4_missing_header", lambda: intake.parse_recorded_grid_csv(io.BytesIO(b""), durations, 32))
        csv_refusal("N4_headerless", lambda r: r.pop(0))
        csv_refusal("N4_reordered_header", lambda r: r[0].reverse())
        csv_refusal("N4_duplicate_header_id", lambda r: r[0].__setitem__(1, "1"))
        csv_refusal("N4_extra_header_id", lambda r: r[0].append("80"))
        checks.refuses("N4_bom", lambda: intake.parse_recorded_grid_csv(io.BytesIO(b"\xef\xbb\xbf" + csv_bytes(base_rows)), durations, 32))
        checks.refuses("N4_wrong_delimiter", lambda: intake.parse_recorded_grid_csv(io.BytesIO(csv_bytes(base_rows).replace(b",", b";")), durations, 32))
        csv_refusal("N4_wrong_width", lambda r: r[1].pop())
        csv_refusal("N4_header_inside_data", lambda r: r.__setitem__(5, list(r[0])))
        csv_refusal("N4_nonbinary_interior", lambda r: r[1].__setitem__(0, "0.5"))
        csv_refusal("N4_nonempty_padding", lambda r: r[31].__setitem__(2, "0"))
        csv_refusal("N4_missing_last_record", lambda r: r.pop())
        csv_refusal("N4_extra_record", lambda r: r.append([""] * 79))
        csv_refusal("N4_binary_whitespace", lambda r: r[1].__setitem__(0, " 0"))
        csv_refusal("N4_binary_coercion", lambda r: r[1].__setitem__(0, "0.0"))
        for infant in (4, 29, 50):
            incomplete = dict(predictions)
            incomplete.pop((infant, 29))
            checks.refuses("N5_missing_infant" + str(infant) + "_case", lambda incomplete=incomplete:
                          scorer._loss_kernel(toy, incomplete), accepted=(KeyError,))

        class MissingExpert(SyntheticMathOnly):
            def votes(self, infant, second):
                return (0, 1)

        checks.refuses("N5_missing_expert", lambda: scorer._loss_kernel(MissingExpert(), predictions))
        old_id = hmac.new(key, b"helsinki-v4:0:1:29", hashlib.sha256).hexdigest()
        checks.check("N6_legacy_namespace_differs", old_id != case_id)
        checks.check("N6_changed_lineage_namespace", case_id != protocol.case_identifier(key, 0, 1, 29, "b" * 64))
        checks.refuses("N6_invalid_namespace_input", lambda: protocol.case_identifier(key, 0, 1, 28, lineage_sha))
        checks.refuses("N6_partial_lineage_refusal", lambda: profile.validate_lineage({"profile": profile.profile_identity()}))
        checks.refuses("N6_fake_training_view", lambda: protocol.TrainingView(toy, 0))
        role = protocol.roles(0)
        prior = protocol.ConstantPrior(0.5, role["training"], (), 0, lineage_sha, "c" * 64)
        checks.refuses("N6_fake_prior_admission", lambda: protocol.validate_prior(prior, toy, 0))
        checks.refuses("N6_fake_external_baseline", lambda: protocol.validate_external_baseline_manifest(
            {"fit_infants": role["training"], "selection_infants": (), "lineage_sha256": lineage_sha}, toy, 0))
        checks.check("N7_packet_field_inventory", all(set(p) == {"case_id", "sample_hz", "units", "montage",
            "context_seconds", "target_relative_interval", "quality_flags", "waveform"} for p in packets))
        checks.refuses("N7_invalid_quality_flags", lambda: protocol.public_packet(case_id, first, {}))
        refused_score = scorer.score_full79(toy, [])
        checks.check("N8_unestablished_has_no_score", refused_score["status"] == "UNESTABLISHED" and
                     refused_score["primary_score"] is None and refused_score["scientifically_qualified"] is False)
        checks.refuses("N8_nonfinite_probability", lambda: intake.finite(float("nan")))
        checks.check("N8_fixture_not_complete_corpus", not isinstance(toy, intake.Corpus))
        integration = integration_checks(root, write, checks, mutate_append, intake=intake, profile=profile,
                                         fixture=fixture, protocol=protocol, scorer=scorer,
                                         make_fixture=make_fixture, csv_bytes=csv_bytes)
        if checks.seen != set(CONTROL_IDS):
            raise AssertionError("control_inventory_incomplete")
        result = {"schema": "recorded_grid_synthetic_component_checks_v1", "status": "SYNTHETIC_RECORDED_GRID_CONTROLS_PASSED",
                  "expected_control_ids": list(CONTROL_IDS), "controls": checks.rows,
                  "control_count": len(CONTROL_IDS), "artifact_bytes_before_result": written,
                  "artifacts": artifacts, "intentional_fixture_mutations": mutations,
                  "production_Corpus_admitted": False,
                  "complete_production_session_end_to_end_exercised": False,
                  "complete_invented_corpus_and_session_integration": integration,
                  "authentic_primary_inputs_read": 0, "model_calls": 0, "scientific_scores": 0,
                  "synthetic_math_loss_checks": True, "scientifically_qualified": False,
                  "unexercised_gates": ["Complete authentic production Corpus and real waveform custody",
                                        "Actual neural model and scientific performance campaign",
                                        "External process/target/network/resource host isolation",
                                        "Competent authentic task-specific baseline reproduction"],
                  "limitations": ["Full invented82-asset/80-case integration is explicitly fixture-only, never production source identity.",
                                  "No actual source header/CSV compatibility or neural performance follows from this synthetic invocation."]}
        payload = (json.dumps(result, indent=2) + "\n").encode()
        write("RESULT.json", payload)
        print(json.dumps({"status": result["status"], "control_ids": [r["id"] for r in checks.rows],
                          "checks_executed_count": len(checks.rows), "fixture_bytes": written,
                          "unexercised_gates": result["unexercised_gates"],
                          "scientifically_qualified": False,
                          "result_bytes": len(payload), "result_sha256": hashlib.sha256(payload).hexdigest(),
                          "total_artifact_bytes": written, "result_path": str(root / "RESULT.json")}))
    except BaseException as exc:
        failure = {"schema": "recorded_grid_synthetic_component_failure_v1", "status": "FAIL",
                   "exception_type": type(exc).__name__, "reason": str(exc),
                   "completed_controls": checks.rows, "expected_control_ids": list(CONTROL_IDS),
                   "artifact_bytes": written, "scientifically_qualified": False}
        payload = (json.dumps(failure, indent=2) + "\n").encode()
        if not (root / "FAILURE.json").exists():
            write("FAILURE.json", payload)
        raise
    finally:
        for asset in assets:
            asset.close()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    from full_fixture_checks import INTEGRATION_IDS, integration_checks
    if INTEGRATION_IDS != INTEGRATION_CONTROL_IDS:
        raise AssertionError("integration_control_inventory_changed")
    import helsinki_intake as intake
    import helsinki_profile as profile
    import helsinki_fixture as fixture
    import helsinki_protocol as protocol
    import helsinki_score as scorer
    run(sys.argv[2])
