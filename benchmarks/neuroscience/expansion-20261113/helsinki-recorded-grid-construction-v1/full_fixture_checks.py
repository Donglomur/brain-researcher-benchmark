"""Full invented-corpus engineering checks, called by the single reviewed harness.

No independently runnable campaign, production-source bypass or monkeypatch.
"""
import hashlib
import json
from dataclasses import replace


INTEGRATION_IDS = (
    "P3_invented_full82_intake", "N2_canonical_name_wrong_official_checksum",
    "P3_invented_not_production_profile",
    "N8_production_corpus_refuses_fixture", "N8_production_session_refuses_fixture",
    "P7_invented_full79_80case_support", "P5_invented_three_expert_index_mapping",
    "N6_fixture_namespace_distinct", "P8_actual_trainonly_prior_mask_noise",
    "N6_actual_trainview_held_target_refusal", "N6_actual_stale_baseline_refusal",
    "N6_actual_foreign_fit_role_refusal", "N8_program_requires_prefreeze",
    "N8_program_commitment_immutable", "P8_actual_paired_A_B_all5folds",
    "P8_actual_controls_original_flags", "P7_actual_full79_scored_census",
    "P7_actual_soft_expert_identity", "N8_production_scorer_refuses_fixture",
    "N8_production_paired_scorer_refuses_fixture", "N6_actual_prediction_receipt_tamper",
    "N6_actual_owner_original_tamper", "N6_actual_case_identity_tamper",
    "N5_actual_missing_scored_case", "N5_actual_missing_fold",
    "N8_actual_budget_overrun", "N8_actual_budget_failure_permanent",
    "N7_actual_packets_no_owner_cues", "N2_cached_waveform_mutation_refusal",
)


def integration_checks(root, write, checks, mutate_append, *, intake, profile,
                       fixture, protocol, scorer, make_fixture, csv_bytes):
    corpus_root = root / "invented_corpus"
    corpus_root.mkdir(mode=0o700)
    rows = []
    for infant in intake.INFANTS:
        count = 31 if infant == 1 else 30
        marker = "EDF+C" if infant in (4, 29, 50) else ""
        raw, payload, _, _ = make_fixture(marker, "REF" if infant % 2 else "Ref",
                                          record_count=count)
        body = raw + payload
        name = "eeg" + str(infant) + ".edf"
        write("invented_corpus/" + name, body)
        rows.append({"name": name, "bytes": len(body),
                     "md5": hashlib.md5(body, usedforsecurity=False).hexdigest(),
                     "sha256": hashlib.sha256(body).hexdigest(),
                     "header_sha256": hashlib.sha256(raw).hexdigest(),
                     "recorded_seconds": count, "marker": marker})
    for expert, name in enumerate(intake.ANNOTATIONS):
        contents = [list(map(str, intake.INFANTS))] + [
            [str((infant + second + expert) % 2) if second < (31 if infant == 1 else 30) else ""
             for infant in intake.INFANTS] for second in range(31)]
        body = csv_bytes(contents)
        write("invented_corpus/" + name, body)
        rows.append({"name": name, "bytes": len(body),
                     "md5": hashlib.md5(body, usedforsecurity=False).hexdigest(),
                     "sha256": hashlib.sha256(body).hexdigest()})
    manifest = {"schema": "helsinki_invented_corpus_manifest_v1",
                "source_kind": "invented_fixture", "files": rows}
    manifest_path = write("invented_corpus/MANIFEST.json", (json.dumps(manifest, indent=2) + "\n").encode())
    corpus = fixture.FixtureCorpus(corpus_root, manifest_path)
    try:
        lineage = corpus.lineage()
        lineage_sha = intake.digest(lineage)
        checks.check("P3_invented_full82_intake", len(corpus.assets) == 82 and len(corpus.headers) == 79 and
                     len(corpus.annotations) == 79 and all(len(corpus.annotations[i][0]) == 3 for i in intake.INFANTS))
        def wrong_official_checksum():
            try:
                intake.read_helsinki_recorded_grid_header(corpus.assets["eeg1.edf"])
            except intake.Refusal as exc:
                if str(exc) != "official_complete_asset_checksum_mismatch":
                    raise AssertionError("wrong_production_asset_refusal_stage") from exc
                raise
        checks.refuses("N2_canonical_name_wrong_official_checksum", wrong_official_checksum)
        checks.refuses("P3_invented_not_production_profile", lambda: profile.validate_lineage(lineage))
        checks.refuses("N8_production_corpus_refuses_fixture", lambda: intake.Corpus(corpus_root, manifest_path))
        key = b"engineering-owner-key-never-participant-20261113"
        checks.refuses("N8_production_session_refuses_fixture", lambda: protocol.Session(
            corpus, 0, protocol.CONDITIONS[0], "recorded_eeg", key, "synthetic-null-model-v1", None, None))
        checks.check("P7_invented_full79_80case_support", sum(len(corpus.seconds(i)) for i in intake.INFANTS) == 80 and
                     corpus.declared_recorded_seconds == {i: (31 if i == 1 else 30) for i in intake.INFANTS})
        checks.check("P5_invented_three_expert_index_mapping", all(
            corpus.annotations[i][0][e] == (i + e) % 2 and
            corpus.annotations[i][-1][e] == (i + corpus.durations[i] - 1 + e) % 2
            for i in intake.INFANTS for e in range(3)))
        checks.check("N6_fixture_namespace_distinct", protocol.case_identifier(key, 0, 1, 29, lineage_sha) !=
                     protocol.case_identifier(key, 0, 1, 29, lineage_sha, protocol_id=fixture.FIXTURE_PROTOCOL_ID))
        priors, masks, noise_fits = {}, {}, {}
        for fold in range(5):
            priors[fold] = protocol.fit_prior(corpus, fold)
            masks[fold] = protocol.fit_mask_prior(corpus, fold)
            noise_fits[fold] = protocol.fit_noise(corpus, fold)
        checks.check("P8_actual_trainonly_prior_mask_noise", all(
            fit.training_infants == protocol.roles(fold)["training"] and fit.lineage_sha256 == lineage_sha
            for fold in range(5) for fit in (priors[fold], masks[fold], noise_fits[fold])))
        view = protocol.TrainingView(corpus, 0)
        held = protocol.roles(0)["test"][0]
        checks.refuses("N6_actual_trainview_held_target_refusal", lambda: view.votes(held, 29))
        checks.refuses("N6_actual_stale_baseline_refusal", lambda: protocol.validate_prior(
            replace(priors[0], lineage_sha256="0" * 64), corpus, 0))
        checks.refuses("N6_actual_foreign_fit_role_refusal", lambda: protocol.validate_prior(
            replace(priors[0], training_infants=protocol.roles(0)["test"]), corpus, 0))

        def session(fold, arm, control):
            return protocol.EngineeringSession(corpus, fold, arm, control, key, "synthetic-null-model-v1",
                priors[fold], masks[fold], noise_fit=noise_fits[fold] if control == "training_noise" else None)

        probe = session(0, protocol.CONDITIONS[1], "recorded_eeg")
        checks.refuses("N8_program_requires_prefreeze", probe.next_packet)
        probe.freeze_program(b"SYNTHETIC_FIXED_NULL_PREDICTOR_v1")
        checks.refuses("N8_program_commitment_immutable", lambda: probe.freeze_program(b"changed"))
        groups = {}
        packet_inventory_ok = True
        committed = 0
        for arm in protocol.CONDITIONS:
            for control in protocol.SIGNAL_CONDITIONS:
                sessions = []
                for fold in range(5):
                    active = probe if (arm, control, fold) == (protocol.CONDITIONS[1], "recorded_eeg", 0) else session(fold, arm, control)
                    if arm == protocol.CONDITIONS[1] and active.program_sha256 is None:
                        active.freeze_program(b"SYNTHETIC_FIXED_NULL_PREDICTOR_v1")
                    while not active.complete():
                        body = active.next_packet()
                        packet = json.loads(body)
                        packet_inventory_ok = packet_inventory_ok and set(packet) == {
                            "case_id", "sample_hz", "units", "montage", "context_seconds",
                            "target_relative_interval", "quality_flags", "waveform"}
                        case_id = packet["case_id"]
                        probability = active.baseline_probability(case_id)
                        mask_probability = active.mask_only_probability(case_id)
                        if not (0 <= probability <= 1 and 0 <= mask_probability <= 1):
                            raise AssertionError("fitted_comparator_probability_range")
                        active.commit(case_id=case_id, packet_sha256=hashlib.sha256(body).hexdigest(),
                                      probability=probability,
                                      program_sha256=active.program_sha256 if arm == protocol.CONDITIONS[1] else None)
                        committed += 1
                    sessions.append(active)
                groups[(arm, control)] = sessions
        pairs = [scorer.validate_engineering_paired_arms(corpus, groups[(protocol.CONDITIONS[0], control)],
                                                        groups[(protocol.CONDITIONS[1], control)])
                 for control in protocol.SIGNAL_CONDITIONS]
        checks.check("P8_actual_paired_A_B_all5folds", len(pairs) == 3 and all(
                     pair["paired_source_projection"] == "matched" for pair in pairs))
        alignments = [scorer.validate_engineering_control_alignment(corpus, groups[(arm, "recorded_eeg")],
                                                                   groups[(arm, control)])
                      for arm in protocol.CONDITIONS for control in ("amplitude_only", "training_noise")]
        checks.check("P8_actual_controls_original_flags", len(alignments) == 4 and all(
                     row["original_inputs_and_flags"] == "matched" for row in alignments))
        raw_a, raw_b = groups[(protocol.CONDITIONS[0], "recorded_eeg")], groups[(protocol.CONDITIONS[1], "recorded_eeg")]
        scores = [scorer.score_engineering_full79(corpus, sessions) for sessions in groups.values()]
        checks.check("P7_actual_full79_scored_census", committed == 480 and len(scores) == 6 and all(
            value["status"] == "SYNTHETIC_ENGINEERING_LOSS_ONLY" and value["engineering_only"] is True and
            value["scientifically_qualified"] is False and value["losses"]["infant_count"] == 79 and
            value["losses"]["case_count"] == 80 for value in scores))
        checks.check("P7_actual_soft_expert_identity", all(abs(value["losses"]["mean_expert_brier"] -
            value["losses"]["soft_vote_brier"] - value["losses"]["expert_disagreement_constant"]) < 1e-12
            for value in scores))
        checks.check("N8_production_scorer_refuses_fixture", scorer.score_full79(corpus, raw_a)["status"] == "UNESTABLISHED")
        checks.check("N8_production_paired_scorer_refuses_fixture",
                     scorer.score_paired_full79(corpus, raw_a, raw_b)["status"] == "UNESTABLISHED")
        sample = raw_a[0]
        case_id = sample.order[0]
        item = sample.predictions[case_id]
        prior_lineage = item["lineage_sha256"]
        item["lineage_sha256"] = "0" * 64
        try:
            checks.refuses("N6_actual_prediction_receipt_tamper", lambda: scorer.validate_engineering_predictions(corpus, raw_a))
        finally:
            item["lineage_sha256"] = prior_lineage
        original = sample.issued[case_id]
        prior_profile = original["profile_sha256"]
        original["profile_sha256"] = "0" * 64
        try:
            checks.refuses("N6_actual_owner_original_tamper", lambda: scorer.validate_engineering_predictions(corpus, raw_a))
        finally:
            original["profile_sha256"] = prior_profile
        old_location = sample.case_map[case_id]
        sample.case_map[case_id] = (old_location[0], old_location[1] + 100)
        try:
            checks.refuses("N6_actual_case_identity_tamper", lambda: scorer.validate_engineering_predictions(corpus, raw_a))
        finally:
            sample.case_map[case_id] = old_location
        removed = sample.predictions.pop(case_id)
        try:
            checks.refuses("N5_actual_missing_scored_case", lambda: scorer.validate_engineering_predictions(corpus, raw_a))
        finally:
            sample.predictions[case_id] = removed
        checks.check("N5_actual_missing_fold", scorer.score_engineering_full79(corpus, raw_a[:-1])["status"] == "UNESTABLISHED")
        over = session(0, protocol.CONDITIONS[0], "recorded_eeg")
        over_body = over.next_packet()
        over_id = json.loads(over_body)["case_id"]
        checks.refuses("N8_actual_budget_overrun", lambda: over.record_tool_accounting(
            over_id, cpu_seconds=121, peak_memory_bytes=1))
        checks.refuses("N8_actual_budget_failure_permanent", lambda: over.commit(
            case_id=over_id, packet_sha256=hashlib.sha256(over_body).hexdigest(), probability=0.5))
        checks.check("N7_actual_packets_no_owner_cues", packet_inventory_ok)
        corpus.case_data(1, 29)
        mutate_append("invented_corpus/eeg1.edf", b"X")
        checks.refuses("N2_cached_waveform_mutation_refusal", lambda: corpus.case_data(1, 29))
        return {"fixture_only": True, "authenticated_invented_assets": 82,
                "invented_infants": 79, "cases_per_arm_control": 80,
                "arms": list(protocol.CONDITIONS), "signal_conditions": list(protocol.SIGNAL_CONDITIONS),
                "folds": 5, "completed_sessions": 30, "committed_predictions": committed,
                "training_only_fits": {"prior": 5, "mask_prior": 5, "noise_moments": 5},
                "native_submitted_program_execution": False,
                "production_domain_admitted": False, "scientifically_qualified": False}
    finally:
        corpus.close()
