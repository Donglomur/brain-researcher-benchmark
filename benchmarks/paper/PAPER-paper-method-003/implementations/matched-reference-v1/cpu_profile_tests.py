#!/usr/bin/env python3
"""Generated profile/CLI controls; no scientific imports, arrays or checkpoints.

Native dispatch is replaced by an inert recorder in CLI tests. A mocked lstat
stands in for checkpoint existence; no checkpoint file is created or opened.
These checks cannot establish native execution, a completed fit or performance.
"""
from __future__ import annotations


def main():
    import argparse
    import contextlib
    import copy
    import importlib.abc
    import io
    import json
    from pathlib import Path
    import stat
    import sys
    from types import ModuleType, SimpleNamespace
    import unittest
    from unittest import mock

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path, help="Fresh generated-metadata directory; parent must exist.")
    root = parser.parse_args().scratch.resolve()
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    here = Path(__file__).resolve().parent
    scientific = {"numpy", "torch", "safetensors", "transformers", "tokenizers", "einops"}
    if scientific.intersection(sys.modules):
        raise RuntimeError("profile tests require a fresh process without scientific imports")
    sys.dont_write_bytecode = True

    class NoScientificImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in scientific:
                raise RuntimeError("scientific import forbidden in profile tests: " + fullname)

    sys.meta_path.insert(0, NoScientificImports())

    def no_payload_or_process(event, args):
        if event in {"subprocess.Popen", "os.system", "socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("external operation forbidden in profile tests")
        if event == "open" and isinstance(args[0], (str, bytes)):
            if str(args[0]).endswith((".npy", ".npz", ".pt", ".safetensors", ".tar", ".gz", ".pdf")):
                raise RuntimeError("payload access forbidden in profile tests: " + str(args[0]))

    sys.addaudithook(no_payload_or_process)

    def source(name, filename):
        path = here / filename
        module = ModuleType(name)
        module.__file__ = str(path)
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        return module

    recipe = source("_profile_test_recipe", "recipe.py")
    native = source("_profile_test_native", "native.py")
    cli = source("_profile_test_cli", "run.py")
    info = {"data_identity": "a" * 64}

    def repin(document):
        document.pop("identity", None)
        document["identity"] = recipe.identity(document)
        return document

    def fit_fixture(profile):
        # Independently described complete generated trace. Each stage improves
        # at every epoch, so LP runs 20 epochs and FT runs five, selecting FT4.
        history, audit = [], []
        for stage, epochs, warmup in (("lp", 20, 5), ("ft", 5, 0)):
            for epoch in range(epochs):
                value = 0.5 + epoch / 100
                history.append({"stage": stage, "epoch": epoch, "save_best": True,
                                "step_scheduler": epoch > warmup, "scheduler_value": value,
                                "stop": epoch == epochs - 1, "patience": 0,
                                "accuracy": value, "balanced_accuracy": value})
                audit.append({"stage": stage, "epoch": epoch, "presentations": 6300,
                              "step_attempts": 197, "order_identity": "1" * 64,
                              "initial_rng": "2" * 64, "final_rng": "3" * 64})
        cpu = profile == recipe.CPU_PROFILE
        return repin({
            "selected_stage": "ft", "selected_epoch": 4, "history": history,
            "training_presentations": 157500, "validation_panels": 25,
            "historical_Table12_equivalent": False, "held_predictions_generated": 0,
            "schema": "reve-matched-fit-receipt-v1",
            "recipe": recipe.reference_spec(42, profile=profile),
            "materials_identity": "b" * 64, "data_identity": info["data_identity"],
            "checkpoint": {"bytes": 1, "sha256": "4" * 64}, "audit": audit,
            "initial_rng": "2" * 64, "final_rng": "3" * 64,
            "attention_profile": "cpu_sdpa_math" if cpu else "native_sdpa_dispatch",
            "runtime": ({key: recipe.CPU_RUNTIME_VERSIONS[key]
                         for key in ("torch", "numpy", "safetensors")} if cpu else
                        {key: "generated" for key in ("torch", "numpy", "safetensors")}),
            "initial_head_identity": "5" * 64,
            "reuse_policy": "operator_reference_only_same_data_identity_across_both_primary_conditions",
            "historical_classifier_authenticated": False, "scientific_qualification": False,
        })

    def write_new(name, body):
        path = root / name
        with path.open("xb") as stream:
            stream.write(body)
        return path

    info_path = write_new("info.json", b'{"data_identity":"generated-dispatch-only"}\n')
    receipt_path = write_new("receipt.json", b'{"identity":"generated-dispatch-only"}\n')
    parsed_info = json.loads(info_path.read_text())
    parsed_receipt = json.loads(receipt_path.read_text())

    def arguments(command, name, *, profile=None, overlay=True):
        args = [command, "--info", str(info_path), "--packet", str(root / "unopened-packet"),
                "--author-source", str(root / "unopened-author"), "--output", str(root / name)]
        if profile is not None:
            args += ["--profile", profile]
        if profile == recipe.CPU_PROFILE and overlay:
            args += ["--overlay", str(root / "unopened-overlay")]
        if command == "predict":
            args += ["--checkpoint", str(root / "unopened-checkpoint.pt"),
                     "--fit-receipt", str(receipt_path), "--fit-identity", "6" * 64]
        else:
            args += ["--encoder", str(root / "unopened-encoder.safetensors"), "--seed", "42"]
        return args

    def call(args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = cli.main(args)
        return status, out.getvalue(), err.getvalue()

    def recorder():
        return SimpleNamespace(
            fit_reference=mock.Mock(return_value={"kind": "inert-fit"}),
            predict_selected=mock.Mock(return_value={"kind": "inert-predictions"}),
            training_compatibility=mock.Mock(return_value={"kind": "inert-compatibility"}),
        )

    @contextlib.contextmanager
    def inert_dispatch(fake, output, *, checkpoint_regular=True):
        original_lstat = Path.lstat

        def checkpoint_stat(path, *args, **kwargs):
            if path == output / "classifier.pt":
                return SimpleNamespace(st_mode=stat.S_IFREG if checkpoint_regular else stat.S_IFLNK)
            return original_lstat(path, *args, **kwargs)

        with mock.patch.object(cli, "_native_module", return_value=fake), \
                mock.patch.object(Path, "lstat", checkpoint_stat):
            yield

    class ProfileControls(unittest.TestCase):
        def test_default_cuda_recipe_identity_is_preserved(self):
            default = recipe.reference_spec(42)
            self.assertEqual(default, recipe.reference_spec(42, profile=recipe.CUDA_PROFILE))
            self.assertEqual(default["recipe_identity"],
                             "602dc098a4ce5e80f24444c869e06d3df4f85e07fc1bef6b5c1f5525d9d88085")

        def test_cpu_identity_preserves_endpoint_and_declares_numerical_change(self):
            cuda = recipe.reference_spec(42)
            cpu = recipe.reference_spec(42, profile=recipe.CPU_PROFILE)
            self.assertNotEqual(cpu["recipe_identity"], cuda["recipe_identity"])
            for key in ("source_commit", "data_profile", "participants", "recordings", "epochs",
                        "batch_size", "drop_last", "stages", "optimizer", "selection", "test_feedback_during_fit"):
                self.assertEqual(cpu[key], cuda[key], key)
            self.assertEqual(cpu["execution_profile"]["attention"], "cpu_sdpa_math")
            self.assertEqual(cpu["execution_profile"]["dtype"], "float32")
            self.assertFalse(cpu["execution_profile"]["autocast"])
            self.assertFalse(cpu["scientific_execution_admitted"])
            self.assertFalse(cpu["historical_Table12_equivalent"])
            self.assertIn("physical_CPU_profile", cpu["scientific_budget_fields_required"])
            self.assertNotIn("physical_GPU_profile", cpu["scientific_budget_fields_required"])

        def test_unknown_profile_and_cpu_without_overlay_refuse(self):
            with mock.patch.object(native, "prepare_environment") as prepare:
                for profile, overlay in (("foreign", None), (recipe.CPU_PROFILE, None),
                                         (recipe.CUDA_PROFILE, root / "overlay")):
                    with self.subTest(profile=profile, overlay=overlay), self.assertRaises(ValueError):
                        native.prepare_profile(profile, overlay)
                prepare.assert_not_called()
            with self.assertRaises(ValueError):
                recipe.reference_spec(42, profile="foreign")

        def test_default_native_calls_keep_installation_refusal_before_payload(self):
            with mock.patch.object(native, "file_pin", side_effect=AssertionError("payload read")), \
                    mock.patch.object(native, "load_source", side_effect=AssertionError("author load")):
                for operation in (
                    lambda: native.NativeReference(source="", encoder_path="", packet_root="", fit_rows=[], seed=42),
                    lambda: native.fit_reference(info={}, packet_root="", source="", encoder_path="", seed=42,
                                                 checkpoint_output=""),
                    lambda: native.predict_selected(info={}, packet_root="", source="", checkpoint_path="",
                                                    fit_receipt={}, expected_fit_identity=""),
                ):
                    with self.assertRaises(ValueError):
                        operation()

        def test_complete_cpu_receipt_metadata_acceptance_is_profile_specific(self):
            document = fit_fixture(recipe.CPU_PROFILE)
            self.assertIs(recipe.validate_fit_receipt(document, info, document["identity"],
                                                     profile=recipe.CPU_PROFILE), document)
            self.assertFalse(document["scientific_qualification"])

        def test_cpu_and_cuda_fit_receipts_cannot_cross_profiles(self):
            for source_profile, selected_profile in ((recipe.CPU_PROFILE, recipe.CUDA_PROFILE),
                                                      (recipe.CUDA_PROFILE, recipe.CPU_PROFILE)):
                document = fit_fixture(source_profile)
                with self.subTest(source=source_profile), self.assertRaises(ValueError):
                    recipe.validate_fit_receipt(document, info, document["identity"], profile=selected_profile)

        def test_cpu_runtime_attention_and_independent_identity_are_required(self):
            for change in ("runtime", "attention", "identity"):
                document = fit_fixture(recipe.CPU_PROFILE)
                if change == "runtime":
                    document["runtime"]["torch"] = "foreign"
                elif change == "attention":
                    document["attention_profile"] = "native_sdpa_dispatch"
                repin(document)
                expected = "0" * 64 if change == "identity" else document["identity"]
                with self.subTest(change=change), self.assertRaises(ValueError):
                    recipe.validate_fit_receipt(document, info, expected, profile=recipe.CPU_PROFILE)

        def test_cpu_receipt_requires_complete_fit_and_no_qualification_claim(self):
            for change in ("incomplete", "scientific_qualification", "held_predictions_generated"):
                document = fit_fixture(recipe.CPU_PROFILE)
                if change == "incomplete":
                    document["history"].pop()
                    document["audit"].pop()
                else:
                    document[change] = True if change == "scientific_qualification" else 1
                repin(document)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    recipe.validate_fit_receipt(document, info, document["identity"], profile=recipe.CPU_PROFILE)

        def test_compatibility_pass_cannot_be_admitted_as_fit(self):
            document = repin({"schema": "reve-trainer-cpu-batch-compatibility-v1", "status": "PASS",
                              "profile": recipe.CPU_PROFILE, "batch_sizes": [32, 28],
                              "training_presentations": 92, "completed_training_epochs": 0})
            with self.assertRaises(ValueError):
                recipe.validate_fit_receipt(document, info, document["identity"], profile=recipe.CPU_PROFILE)

    class CLIControls(unittest.TestCase):
        def test_explicit_cpu_and_overlay_required_before_info_or_native_access(self):
            variants = [arguments("compatibility", "implicit-compat"),
                        arguments("compatibility", "cuda-compat", profile=recipe.CUDA_PROFILE),
                        arguments("compatibility", "no-overlay", profile=recipe.CPU_PROFILE, overlay=False),
                        arguments("fit", "cpu-fit-no-overlay", profile=recipe.CPU_PROFILE, overlay=False)]
            with mock.patch.object(cli, "_read_json", side_effect=AssertionError("info read")), \
                    mock.patch.object(cli, "_native_module", side_effect=AssertionError("native load")):
                for args in variants:
                    with self.subTest(command=args[0]), contextlib.redirect_stderr(io.StringIO()), \
                            self.assertRaises(SystemExit) as error:
                        cli.main(args)
                    self.assertEqual(error.exception.code, 2)
                    self.assertFalse(Path(args[args.index("--output") + 1]).exists())

        def test_compatibility_and_alias_dispatch_only_diagnostic(self):
            for command in ("compatibility", "compat"):
                output = root / ("dispatch-" + command)
                fake = recorder()
                with self.subTest(command=command), inert_dispatch(fake, output):
                    status, stdout, stderr = call(arguments(command, output.name, profile=recipe.CPU_PROFILE))
                self.assertEqual(status, 0, stderr)
                fake.training_compatibility.assert_called_once()
                fake.fit_reference.assert_not_called()
                fake.predict_selected.assert_not_called()
                passed = fake.training_compatibility.call_args.kwargs
                self.assertEqual((passed["profile"], passed["seed"]), (recipe.CPU_PROFILE, 42))
                self.assertEqual(passed["info"], parsed_info)
                self.assertEqual(passed["checkpoint_output"], output / "classifier.pt")
                self.assertEqual(json.loads(stdout)["result"], str(output / "compatibility.json"))
                self.assertFalse((output / "fit.json").exists())
                self.assertFalse((output / "classifier.pt").exists())

        def test_fit_dispatch_defaults_cuda_and_preserves_explicit_cpu(self):
            for selected in (None, recipe.CPU_PROFILE):
                output = root / ("dispatch-fit-" + (selected or "default"))
                fake = recorder()
                with self.subTest(profile=selected), inert_dispatch(fake, output):
                    status, _, stderr = call(arguments("fit", output.name, profile=selected))
                self.assertEqual(status, 0, stderr)
                fake.fit_reference.assert_called_once()
                fake.training_compatibility.assert_not_called()
                fake.predict_selected.assert_not_called()
                passed = fake.fit_reference.call_args.kwargs
                self.assertEqual(passed["profile"], selected or recipe.CUDA_PROFILE)
                self.assertEqual(passed["seed"], 42)
                self.assertEqual(passed["overlay"], root / "unopened-overlay" if selected else None)
                self.assertTrue((output / "fit.json").is_file())

        def test_prediction_forwards_selected_receipt_identity_and_profile(self):
            for selected in (None, recipe.CPU_PROFILE):
                output = root / ("dispatch-predict-" + (selected or "default"))
                fake = recorder()
                with self.subTest(profile=selected), inert_dispatch(fake, output):
                    status, _, stderr = call(arguments("predict", output.name, profile=selected))
                self.assertEqual(status, 0, stderr)
                fake.predict_selected.assert_called_once()
                fake.fit_reference.assert_not_called()
                fake.training_compatibility.assert_not_called()
                passed = fake.predict_selected.call_args.kwargs
                self.assertEqual(passed["expected_fit_identity"], "6" * 64)
                self.assertEqual(passed["fit_receipt"], parsed_receipt)
                self.assertEqual(passed["profile"], selected or recipe.CUDA_PROFILE)
                self.assertNotIn("seed", passed)
                self.assertNotIn("encoder_path", passed)
                self.assertTrue((output / "predictions.json").is_file())

        def test_existing_output_refuses_without_dispatch_or_overwrite(self):
            output = root / "existing-output"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_text("preserve this existing result\n")
            fake = recorder()
            with inert_dispatch(fake, output):
                status, stdout, _ = call(arguments("fit", output.name))
            self.assertEqual((status, stdout), (2, ""))
            fake.fit_reference.assert_not_called()
            self.assertEqual(sentinel.read_text(), "preserve this existing result\n")
            self.assertFalse((output / "fit.json").exists())

        def test_native_failure_does_not_publish_success_json(self):
            output = root / "native-refusal"
            fake = recorder()
            fake.fit_reference.side_effect = ValueError("inert native refusal")
            with inert_dispatch(fake, output):
                status, stdout, stderr = call(arguments("fit", output.name))
            self.assertEqual((status, stdout), (2, ""))
            self.assertIn("inert native refusal", stderr)
            self.assertFalse((output / "fit.json").exists())

        def test_nonregular_checkpoint_output_refuses_success(self):
            output = root / "nonregular-checkpoint"
            with inert_dispatch(recorder(), output, checkpoint_regular=False):
                status, stdout, stderr = call(arguments("fit", output.name))
            self.assertEqual((status, stdout), (2, ""))
            self.assertIn("ordinary file", stderr)
            self.assertFalse((output / "fit.json").exists())

        def test_json_reader_rejects_duplicate_nonfinite_nonobject_and_symlink(self):
            for name, body in (("duplicate", b'{"x":1,"x":2}'), ("nan", b'{"x":NaN}'),
                               ("overflow", b'{"x":1e999}'), ("array", b'[]')):
                path = write_new(name + ".json", body)
                with self.subTest(case=name), self.assertRaises(ValueError):
                    cli._read_json(path)
            link = root / "metadata-link.json"
            link.symlink_to(info_path.name)
            with self.assertRaises(OSError):
                cli._read_json(link)
            with mock.patch.object(cli, "MAX_JSON_BYTES", 2), self.assertRaises(ValueError):
                cli._read_json(info_path)

        def test_json_writer_refuses_overwrite_nonfinite_and_oversized_result(self):
            existing = write_new("writer-existing.json", b'{"preserve":true}\n')
            with self.assertRaises(OSError):
                cli._write_json(existing, {"replace": True})
            self.assertEqual(existing.read_bytes(), b'{"preserve":true}\n')
            for name, value in (("writer-nan.json", {"bad": float("nan")}),
                                 ("writer-array.json", [])):
                path = root / name
                with self.subTest(case=name), self.assertRaises(ValueError):
                    cli._write_json(path, value)
                self.assertFalse(path.exists())
            path = root / "writer-large.json"
            with mock.patch.object(cli, "MAX_JSON_BYTES", 2), self.assertRaises(ValueError):
                cli._write_json(path, {"too_large": True})
            self.assertFalse(path.exists())

    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ProfileControls),
                                unittest.defaultTestLoader.loadTestsFromTestCase(CLIControls)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    generated = sum(path.stat().st_size for path in root.rglob("*")
                    if path.is_file() and not path.is_symlink())
    assert generated + 16384 <= 256 * 1024, "generated metadata exceeded 256 KiB ceiling"
    assert not scientific.intersection(sys.modules), "scientific package imported"
    report = {"schema": "reve-cpu-profile-generated-tests-v1", "status": "PASS" if result.wasSuccessful() else "FAIL",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "generated_metadata_bytes_before_report": generated, "generated_artifact_limit_bytes": 256 * 1024,
              "scientific_packages_imported": False, "signal_or_checkpoint_reads": 0,
              "checkpoint_files_written": 0, "native_model_execution": False,
              "generated_receipts_are_not_model_results": True}
    write_new("TEST_RESULTS.json", (json.dumps(report, sort_keys=True) + "\n").encode())
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
