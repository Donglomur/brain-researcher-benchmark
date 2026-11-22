#!/usr/bin/env python3
"""Generated metadata boundary tests; no neuroscience payload or model runtime."""
from __future__ import annotations


def main():
    import argparse
    import contextlib
    import copy
    import hashlib
    import importlib.abc
    import io
    import json
    from pathlib import Path
    import sys
    from types import ModuleType
    import unittest
    from unittest import mock

    HERE = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scratch', type=Path, help='Fresh generated-metadata directory; parent must exist.')
    ROOT = parser.parse_args().scratch.resolve()
    ROOT.mkdir(mode=0o700, parents=False, exist_ok=False)
    MAX_GENERATED_BYTES = 2 * 1024 * 1024


    class NoScientificImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"numpy","torch","safetensors","transformers","einops"}:
                raise RuntimeError("scientific import forbidden in metadata tests: " + fullname)


    sys.meta_path.insert(0, NoScientificImports())


    def no_payload_or_process(event, args):
        if event in {"subprocess.Popen","os.system","socket.connect","socket.getaddrinfo"}:
            raise RuntimeError("external operation forbidden in metadata tests")
        if event == "open" and isinstance(args[0], (str, bytes)):
            name = str(args[0])
            if name.endswith((".npy",".npz",".pt",".safetensors",".tar",".gz",".pdf")):
                raise RuntimeError("payload access forbidden in metadata tests: " + name)


    sys.addaudithook(no_payload_or_process)
    module_path = HERE / "metadata.py"
    metadata = ModuleType("_metadata_under_test")
    metadata.__file__ = str(module_path)
    exec(compile(module_path.read_bytes(), str(module_path), "exec"), metadata.__dict__)
    recipe = metadata._module("recipe")
    adapter = metadata._module("adapter")
    materials = adapter.materials_module()


    def canonical(obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


    def sha(raw):
        return hashlib.sha256(raw).hexdigest()


    def identity(obj):
        return sha(canonical(obj)[:-1])


    def write_new(name, raw):
        path = ROOT / name
        with path.open("xb") as stream:
            stream.write(raw)
        return path


    def manifest_fixture():
        records = []
        for person in range(1, 90):
            for offset, run in enumerate(materials.RUNS):
                count = 15 if person <= 70 else 16 if (person-71)*6+offset < 24 else 15
                records.append({
                    "participant": person, "run": run, "split": "train" if person <= 70 else "val",
                    "shape": [count,64,800], "sha256": "f"*64,
                    "event_ids": [f"S{person:03d}R{run:02d}-event{i:03d}" for i in range(count)],
                    "signal": f"signals/S{person:03d}R{run:02d}.npy",
                    "labels": [0 if run in (4,8,12) else 2]*count,
                })
        for index in range(1803):
            records.append({"split":"test","shape":[1,64,800],"sha256":"f"*64,
                            "event_ids":[f"trial-{index:032x}"],"signal":f"signals/query-{index:032x}.npy"})
        data = {
            "profile":materials.PROFILE,"units":"uV","dtype":"float64","sampling_hz":200,
            "channels":materials.CHANNELS,"class_order":["left_fist","right_fist","both_fists","feet"],
            "counts":{"train":6300,"val":1734,"test":1803},"records":records,
            "test_mapping_identity":"b"*64,"test_layout":"one_epoch_per_opaque_file_in_one_persisted_global_shuffle",
            "geometry":{"path":"positions.json","sha256":materials.POSITIONS_SHA256,"bytes":materials.POSITIONS_BYTES,
                        "electrodes_in_signal_channel_order":materials.ELECTRODES,
                        "coordinate_convention":"unchanged numeric coordinates in the pinned author bank"},
        }
        document = {
            "schema":"reve-candidate-materials-v1","condition":"paper_data","source_panel_identity":"a"*64,
            "source_commit":materials.SOURCE_COMMIT,"data_identity":identity(data),"data":data,
            "published_epoch_count":9837,"observed_epoch_count":9837,"published_epoch_count_matches":True,
            "paper":{"path":"paper.pdf","sha256":materials.PAPER_SHA256,"bytes":materials.PAPER_BYTES},
            "official_code":None,"test_labels_delivered":False,"historical_recipe_verified":False,
            "scientific_qualification":False,"limits":[
                "Trusted operator export; mount only this tree into a separately qualified candidate environment.",
                "Original annotations are publicly exposed; physical omission does not create a new secret holdout.",
                "Pretrained encoder weights are not included; identical pretrained access requires separate provision and admission.",
                "Full Table12 preprocessing, trained classifier and seed/run aggregation remain unresolved.",
            ],
        }
        document["materials_identity"] = identity(document)
        return document


    def fit_fixture(info):
        # A synthetic complete trace, not a model result. Monotonic BA makes the
        # expected scheduler/checkpoint/stop decisions explicit and independently
        # describes the 20 LP + 5 FT horizon.
        history, audit = [], []
        for stage, epochs, warmup in (("lp",20,5),("ft",5,0)):
            for epoch in range(epochs):
                value = 0.5 + epoch/100
                history.append({"stage":stage,"epoch":epoch,"save_best":True,
                                "step_scheduler":epoch>warmup,"scheduler_value":value,
                                "stop":epoch==epochs-1,"patience":0,
                                "accuracy":value,"balanced_accuracy":value})
                audit.append({"stage":stage,"epoch":epoch,"presentations":6300,"step_attempts":197,
                              "order_identity":"1"*64,"initial_rng":"2"*64,"final_rng":"3"*64})
        doc = {
            "selected_stage":"ft","selected_epoch":4,"history":history,"training_presentations":157500,
            "validation_panels":25,"historical_Table12_equivalent":False,"held_predictions_generated":0,
            "schema":"reve-matched-fit-receipt-v1","recipe":recipe.reference_spec(42),
            "materials_identity":info["materials_identity"],"data_identity":info["data_identity"],
            "checkpoint":{"bytes":1,"sha256":"4"*64},"audit":audit,"initial_rng":"2"*64,"final_rng":"3"*64,
            "attention_profile":"native_sdpa_dispatch",
            "runtime":{"torch":"synthetic","numpy":"synthetic","safetensors":"synthetic"},
            "initial_head_identity":"5"*64,
            "reuse_policy":"operator_reference_only_same_data_identity_across_both_primary_conditions",
            "historical_classifier_authenticated":False,"scientific_qualification":False,
        }
        doc["identity"] = identity(doc)
        return doc


    def call(arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = metadata.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()


    class MetadataTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.manifest = manifest_fixture()
            raw = canonical(cls.manifest)
            cls.manifest_path = write_new("materials.json", raw)
            cls.manifest_sha = sha(raw)
            cls.info_path = ROOT/"info.json"
            cls.prepare_args = ["prepare-info","--manifest",str(cls.manifest_path),
                                "--manifest-sha256",cls.manifest_sha,
                                "--materials-identity",cls.manifest["materials_identity"],
                                "--panel-identity",cls.manifest["source_panel_identity"],
                                "--output",str(cls.info_path)]
            status, stdout, stderr = call(cls.prepare_args)
            if status != 0:
                raise AssertionError(stderr)
            cls.prepared_result = json.loads(stdout)
            info_raw = cls.info_path.read_bytes()
            cls.info = json.loads(info_raw); cls.info_sha = sha(info_raw)
            cls.fit = fit_fixture(cls.info)
            cls.fit_path = write_new("fit.json", canonical(cls.fit))
            cls.check_args = ["check-fit","--info",str(cls.info_path),"--info-sha256",cls.info_sha,
                              "--fit-receipt",str(cls.fit_path),"--fit-identity",cls.fit["identity"]]

        def changed_prepare_args(self, option, value, output):
            args = list(self.prepare_args)
            args[args.index(option)+1] = value
            args[args.index("--output")+1] = str(ROOT/output)
            return args

        def test_complete_public_metadata_and_no_payload(self):
            counts = {split:sum(row["shape"][0] for row in self.info["records"] if row["split"]==split)
                      for split in ("train","val","test")}
            self.assertEqual(counts, {"train":6300,"val":1734,"test":1803})
            self.assertEqual(len(self.info["test_ids"]),1803)
            self.assertFalse(self.prepared_result["array_bodies_authenticated"])
            self.assertFalse(self.prepared_result["scientific_qualification"])
            self.assertFalse((ROOT/"signals").exists())

        def test_altered_file_hash_and_independent_identities(self):
            for option,value,name in (
                ("--manifest-sha256","0"*64,"bad-hash.json"),
                ("--materials-identity","0"*64,"bad-materials.json"),
                ("--panel-identity","0"*64,"bad-panel.json"),
            ):
                with self.subTest(option=option):
                    status, stdout, stderr = call(self.changed_prepare_args(option,value,name))
                    self.assertEqual(status,2); self.assertEqual(stdout,""); self.assertIn("refused",stderr)
                    self.assertFalse((ROOT/name).exists())

        def test_rehashed_semantically_altered_manifest_rejected(self):
            changed = copy.deepcopy(self.manifest)
            changed["data"]["units"] = "V"
            changed["data_identity"] = identity(changed["data"])
            changed.pop("materials_identity")
            changed["materials_identity"] = identity(changed)
            raw = canonical(changed)
            args = self.changed_prepare_args("--materials-identity",changed["materials_identity"],"bad-units.json")
            args[args.index("--manifest-sha256")+1] = sha(raw)
            with mock.patch.object(metadata,"_document",return_value=(changed,raw)):
                status, stdout, _ = call(args)
            self.assertEqual(status,2); self.assertEqual(stdout,"")
            self.assertFalse((ROOT/"bad-units.json").exists())

        def test_noncanonical_manifest_does_not_issue_wrong_physical_pin(self):
            raw = json.dumps(self.manifest,indent=2).encode()+b"\n"
            args = self.changed_prepare_args("--manifest-sha256",sha(raw),"noncanonical.json")
            with mock.patch.object(metadata,"_document",return_value=(self.manifest,raw)):
                status, _, stderr = call(args)
            self.assertEqual(status,2); self.assertIn("canonical",stderr)
            self.assertFalse((ROOT/"noncanonical.json").exists())

        def test_existing_output_is_preserved(self):
            before = self.info_path.read_bytes()
            status, _, _ = call(self.prepare_args)
            self.assertEqual(status,2)
            self.assertEqual(self.info_path.read_bytes(),before)

        def test_complete_fit_receipt_is_metadata_only(self):
            status, stdout, stderr = call(self.check_args)
            self.assertEqual(status,0,stderr)
            result = json.loads(stdout)
            self.assertEqual((result["selected_stage"],result["selected_epoch"]),("ft",4))
            self.assertFalse(result["training_execution_verified"])
            self.assertFalse(result["checkpoint_body_authenticated"])
            self.assertFalse(result["scientific_qualification"])

        def test_independent_fit_and_info_identity_rejections(self):
            for option in ("--info-sha256","--fit-identity"):
                args=list(self.check_args);args[args.index(option)+1]="0"*64
                with self.subTest(option=option):
                    status,stdout,_=call(args)
                    self.assertEqual(status,2);self.assertEqual(stdout,"")

        def test_incomplete_compatibility_changed_data_and_CPU_receipts_rejected(self):
            incomplete=copy.deepcopy(self.fit)
            incomplete["history"].pop();incomplete["audit"].pop()
            changed_data=copy.deepcopy(self.fit);changed_data["data_identity"]="c"*64
            cpu=copy.deepcopy(self.fit)
            cpu["recipe"]["schema"]="reve-matched-reference-recipe-v2"
            cpu["recipe"]["classification"]="prospective_cpu_reference"
            cpu["recipe"]["execution_profile"]={"name":"cpu-fp32-math"}
            cpu["attention_profile"]="cpu_sdpa_math"
            compatibility={"schema":"reve-trainer-cpu-batch-compatibility-v1","status":"PASS"}
            original_read=metadata._document
            for label,doc in (("incomplete",incomplete),("changed_data",changed_data),
                              ("cpu_profile",cpu),("compatibility",compatibility)):
                doc.pop("identity",None);doc["identity"]=identity(doc)
                args=list(self.check_args);args[args.index("--fit-identity")+1]=doc["identity"]
                def selected_read(path,expected_sha256=None):
                    return (doc,canonical(doc)) if Path(path)==self.fit_path else original_read(path,expected_sha256)
                with self.subTest(case=label),mock.patch.object(metadata,"_document",side_effect=selected_read):
                    status,stdout,_=call(args)
                    self.assertEqual(status,2);self.assertEqual(stdout,"")

        def test_strict_JSON_reader(self):
            for name,raw in (("duplicate.json",b'{"x":1,"x":2}'),("nan.json",b'{"x":NaN}'),
                             ("overflow.json",b'{"x":1e999}')):
                path=write_new(name,raw)
                with self.subTest(name=name),self.assertRaises(ValueError):
                    metadata._document(path)


    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MetadataTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    files=[p for p in ROOT.iterdir() if p.is_file()]
    generated_bytes=sum(p.stat().st_size for p in files)
    assert generated_bytes+16384 <= MAX_GENERATED_BYTES, "generated metadata exceeds selected2MiB ceiling"
    assert not any(name in sys.modules for name in ("torch","numpy","safetensors","transformers","einops"))
    report={"schema":"reve-metadata-cli-generated-tests-v1","status":"PASS" if result.wasSuccessful() else "FAIL",
            "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
            "generated_metadata_bytes_before_report":generated_bytes,"generated_artifact_limit_bytes":MAX_GENERATED_BYTES,
            "scientific_packages_imported":False,"signal_or_weight_reads":0,"training_or_model_execution":False,
            "synthetic_receipts_are_not_model_results":True}
    write_new("TEST_RESULTS.json",canonical(report))
    print(json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
