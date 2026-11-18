"""Generated metadata only; no data files, mounts or scientific execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from suns2_benchmark import paired_materials as m


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fixture():
    members, readable = [], []
    for i, video in enumerate(m.VIDEO_IDS):
        for kind, name in (("video", video + ".h5"),
                           ("mask", "GT Masks/FinalMasks_" + video + ".mat")):
            row = dict(name=name, bytes=30001400 if kind == "video" else 100,
                       sha256=digest(name.encode()), source_object_id=49636131)
            members.append(row)
            if kind == "video":
                readable.append(dict(row, role="video", schema=dict(
                    shape=[6000, 50, 50], selected_name="mov",
                    dtype={"description": "uint16"}),
                    readability={"elements_read": 15000000}))
    members.append(dict(name="1P_spike_tempolate.h5", bytes=2048,
                        sha256="f"*64, source_object_id=49636131))
    code = [dict(path="LICENSE" if i == 0 else "SUNS2/LICENSE" if i == 1
                 else "module" + str(i) + ".py",
                 bytes=721009 if i == 0 else 1, sha256=digest(str(i).encode()))
            for i in range(89)]
    papers = [dict(role=role, original=dict(path="/fake/" + name,
               bytes=size, sha256=digest(name.encode())))
              for (role, name), size in zip(m._PAPERS, (4490621, 3716214, 1479478))]
    rows = [dict(name=r["name"], bytes=r["bytes"], sha256=r["sha256"],
                 v3_sha256=r["sha256"], expanded_sha256_equal=True,
                 role="quarantined_template" if r["name"].startswith("1P_")
                 else "ground_truth" if r["name"].startswith("GT Masks/") else "movie")
            for r in members]
    return dict(
        zip_stage={"result": dict(status="complete_original_input_ZIP_authenticated",
                    members=members, archive_sha256="a"*64,
                    archive_md5="e4aaf274478253cfea21580594ab2e36")},
        hdf5_stage={"result": dict(status="complete_schema_and_readability",
                      video_order=list(m.VIDEO_IDS), files=readable)},
        input_chain={"stage_and_process_pins": {}},
        input_acceptance=dict(schema="suns2-original-nine-input-acceptance/v1",
            decision="Accept authenticated current-v3 complete input bank and saved readability qualification; no method or benchmark-readiness claim"),
        code_bank=dict(schema="suns2-private-code-bank/v3", release="v1.2.0",
            commit="128eb4738e026b89a341a6013e7bd7b6dc7c3216", files_completed=code),
        code_acceptance=dict(schema="suns2-semantic-role-acceptance/v1", files=89,
            bytes=721097, decision="Accept as method-source artifacts; no embedded answer/weight payloads observed. Public result constants/links disclosed."),
        papers=dict(schema="suns2-protected-paper-originals/v1",
            status="three_original_PDF_bodies_authenticated", originals=papers),
        parity_result=dict(schema="suns2-v2-v3-hash-only-comparison/v1",
            status="complete_equal", all_19_equal=True, template_quarantined=True,
            members=rows),
        parity_closure=dict(status="selected_19_file_snapshot_parity_verified",
            facts=dict(matching_movies=9, matching_manual_masks=9,
                       matching_quarantined_template=1, different_members=0)))


def seal(d):
    d = copy.deepcopy(d)
    for name in ("zip", "hdf5"):
        d["input_chain"]["stage_and_process_pins"][name] = {
            "stage": {"sha256": digest(encoded(d[name + "_stage"]))}}
    d["input_acceptance"]["native_chain"] = {"sha256": digest(encoded(d["input_chain"]))}
    d["code_acceptance"]["bank_manifest_sha256"] = digest(encoded(d["code_bank"]))
    d["parity_result"]["v3_reference_receipt_sha256"] = digest(encoded(d["zip_stage"]))
    d["parity_closure"]["result"] = {"sha256": digest(encoded(d["parity_result"]))}
    raw = {k: encoded(v) for k, v in d.items()}
    return raw, {k: digest(v) for k, v in raw.items()}


def bindings(protocol_digest):
    return [dict(extension_id=m.EXTENSION_ID, campaign_id="trial1",
                 common_protocol_digest=protocol_digest, condition=arm,
                 procedure_digest=str(i + 1)*64, fold_index=j, held_video=video,
                 fresh_state_id=str(i) + "-" + str(j))
            for i, arm in enumerate(m.ASSISTANCE_CONDITIONS)
            for j, video in enumerate(m.VIDEO_IDS)]


class PairedMaterialsTests(unittest.TestCase):
    def test_census_and_join_refusals(self):
        good = bindings("a"*64)
        self.assertEqual(m.validate_campaign_bindings(good[::-1]), good)
        for field, value in (("fresh_state_id", good[9]["fresh_state_id"]),
                             ("fold_index", True), ("held_video", "other"),
                             ("common_protocol_digest", "b"*64),
                             ("procedure_digest", "3"*64)):
            bad = copy.deepcopy(good); bad[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate_campaign_bindings(bad)
        for mode in ("duplicate_readability", "bad_parity", "code_weight", "rejected"):
            d = fixture()
            if mode == "duplicate_readability":
                d["hdf5_stage"]["result"]["files"].append(d["hdf5_stage"]["result"]["files"][0])
            elif mode == "bad_parity":
                d["parity_result"]["members"][1]["v3_sha256"] = "0"*64
            elif mode == "code_weight":
                d["code_bank"]["files_completed"][0]["path"] = "weights/answer.py"
            else:
                d["input_acceptance"]["decision"] = "Reject"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                m.join_materials(*seal(d))

    def test_common_support_and_private_state_gate(self):
        bundle = m.join_materials(*seal(fixture()))
        protocol = dict(schema="suns2-paired-common-protocol/v1",
            join_digest=bundle["join_digest"], questions_digest="a"*64,
            budget_digest="b"*64, feedback_policy="all36_before_protected_feedback",
            validation_policy="active_training8_only")
        raw = encoded(protocol); states = bindings(digest(raw)); plans = []
        for arm, index in ((m.ASSISTANCE_CONDITIONS[0], 0), (m.ASSISTANCE_CONDITIONS[1], 9)):
            a = dict(binding=states[index], join_digest=bundle["join_digest"],
                     template_policy="active_training8_only", **{k: True for k in m._CUSTODY})
            data = encoded(a)
            plans.append(m.plan_fold(bundle, states, arm, 0, data, digest(data),
                                     common_protocol_bytes=raw))
        self.assertEqual(plans[0]["data_files"], plans[1]["data_files"])
        self.assertEqual(plans[0]["papers"], plans[1]["papers"])
        self.assertEqual([len(p["code_files"]) for p in plans], [0, 89])
        self.assertEqual(len(plans[0]["data_files"]), 17)
        self.assertFalse(plans[0]["runtime_isolation_verified"])
        self.assertNotIn("GT Masks/FinalMasks_" + m.VIDEO_IDS[0] + ".mat",
                         [r["path"] for r in plans[0]["data_files"]])
        for mode in ("state", "template", "protocol"):
            bad = copy.deepcopy(a); bad_raw = raw; bad_states = states
            if mode == "state": bad["fresh_context_files_caches"] = False
            elif mode == "template": bad["template_policy"] = "historical"
            else:
                p = dict(protocol, join_digest="0"*64); bad_raw = encoded(p)
                bad_states = bindings(digest(bad_raw)); bad["binding"] = bad_states[9]
            data = encoded(bad)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                m.plan_fold(bundle, bad_states, arm, 0, data, digest(data),
                            common_protocol_bytes=bad_raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)

