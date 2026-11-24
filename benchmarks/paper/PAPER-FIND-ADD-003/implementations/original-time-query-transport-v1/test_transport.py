"""Only new generated transport seams; does not replay mapper tests or score."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("transport_under_test", HERE / "transport.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
MAPPING_PATH = None
FIXTURES = None
WRITE_LIMIT = 131072
WRITE_BYTES = 0
SECRET = bytes(range(32))  # Generated controls only.


def generated_roster():
    score = T.load_mapping(MAPPING_PATH).load_reference()
    sessions = []
    for animal in score.ANIMALS:
        for day in score.DAYS:
            delays = [0.0] * 140
            delays[2], delays[91] = 2.5, 5.0
            sessions.append({"animal": animal, "day": day, "condition_codes": [11]*140,
                             "recorded_delay_seconds": delays})
    return {"schema": "h_original_time_roster_v1", "input_sha256": T.SOURCE_INPUT_SHA256, "sessions": sessions}


def context():
    value = T.new_context("a"*64, "paper_data", "b"*64)
    value["run_nonce"] = "c"*64
    return value


def prepared(delivery, fold):
    binding = delivery.plan.operator_binding(fold)
    rows = []
    for actual in range(1, 8):
        rows.append({k: binding[k] for k in ("animal", "day", "cue", "control", "trial_index")})
        rows[-1].update(actual_bin=actual, features=[actual + 0.125, -actual / 8.0, 3])
    return {"input_sha256": T.SOURCE_INPUT_SHA256, "preparation_sha256": "b"*64,
            "roi_order_sha256": "d"*64, "roi_count": 3, "rows": list(reversed(rows))}


def response(packet, delivery):
    binding = delivery.plan.operator_binding(packet["fold_id"])
    pred = {q["query_id"]: 8-q["actual_bin"] for q in binding["queries"]}
    return {"schema": T.RESPONSE_SCHEMA, "fold_id": packet["fold_id"], "delivery_id": packet["delivery_id"],
            "packet_sha256": T.digest(packet),
            "predictions": [{"query_id": row["query_id"], "predicted_bin": pred[row["query_id"]]} for row in packet["queries"]]}


def all_rows(document):
    return [r for p in document["panels"] for r in p["trials"]]


class DeliveryTests(unittest.TestCase):
    counter = 0

    def new(self, changed=None):
        DeliveryTests.counter += 1
        path = FIXTURES / str(DeliveryTests.counter)
        ctx = context()
        if changed:
            ctx.update(changed)
        obj = T.SignalDelivery.create(path, generated_roster(), ctx, SECRET, mapping_path=MAPPING_PATH)
        return obj, obj.plan.operator_fold_ids()[0]

    def resume(self, obj, ctx=None, secret=SECRET):
        return T.SignalDelivery.resume(obj.root, generated_roster(), ctx or obj.context, secret, mapping_path=MAPPING_PATH)

    def test_exact_private_join_and_feature_only_public_packet(self):
        obj, fid = self.new()
        data = prepared(obj, fid)
        packet = obj.issue(fid, data)
        self.assertEqual(set(packet), {"schema", "delivery_id", "fold_id", "queries"})
        self.assertEqual(len(packet["queries"]), 7)
        self.assertEqual([q["query_id"] for q in packet["queries"]], [q["query_id"] for q in obj.plan.public_fold(fid)["queries"]])
        inv = {q["query_id"]: q["actual_bin"] for q in obj.plan.operator_binding(fid)["queries"]}
        for q in packet["queries"]:
            self.assertEqual(set(q), {"query_id", "features"})
            actual = inv[q["query_id"]]
            self.assertEqual(q["features"], [actual+0.125, -actual/8.0, 3])
        serialized = T.canonical(packet).decode()
        for forbidden in ("actual_bin", "trial_index", "animal", "day", "cue", "control", "CD217", "roi_order", "preparation", "candidate", "run_nonce"):
            self.assertNotIn(forbidden, serialized)
        # A caller cannot mutate retained commitment by mutating either input or packet.
        old = copy.deepcopy(packet)
        data["rows"][0]["features"][0] = 999
        packet["queries"][0]["features"][0] = 999
        self.assertEqual(self.resume(obj).resume_packet(fid, prepared(obj,fid)), old)

    def test_missing_duplicate_cross_trial_and_extra_timing_are_refused(self):
        obj, fid = self.new()
        changes = [lambda d:d["rows"].pop(), lambda d:d["rows"].__setitem__(0,copy.deepcopy(d["rows"][1])),
                   lambda d:d["rows"][0].update(trial_index=92), lambda d:d["rows"][0].update(time_seconds=2.5),
                   lambda d:d.update(raw_trial_labels=[1]), lambda d:d["rows"][0].update(features=[1,float("nan"),3]),
                   lambda d:d["rows"][0].update(features=[1,True,3]), lambda d:d.update(roi_count=4),
                   lambda d:d.update(preparation_sha256="e"*64), lambda d:d["rows"][0].update(actual_bin=True)]
        for mutate in changes:
            data=prepared(obj,fid); mutate(data)
            with self.assertRaises((ValueError,TypeError)):
                obj.issue(fid,data)
            self.assertFalse((obj.root/(fid+".issue.json")).exists())

    def test_content_roi_and_preparation_commitments_are_not_repairable(self):
        obj,fid=self.new(); packet=obj.issue(fid,prepared(obj,fid))
        for change in (lambda d:d["rows"][0]["features"].__setitem__(1,-123.0),lambda d:d.update(roi_order_sha256="e"*64)):
            data=prepared(obj,fid);change(data)
            with self.assertRaises(ValueError):self.resume(obj).resume_packet(fid,data)
        reordered=prepared(obj,fid);reordered["rows"].reverse()
        self.assertEqual(self.resume(obj).resume_packet(fid,reordered),packet)
        with self.assertRaises(FileExistsError):obj.issue(fid,prepared(obj,fid))

    def test_candidate_access_and_nonce_change_all_opaque_identities(self):
        original,fid=self.new()
        original_ids=set(original.plan.operator_fold_ids())
        for delta in ({"candidate_sha256":"e"*64},{"access_condition":"paper_data_author_code"},{"run_nonce":"f"*64}):
            changed,_=self.new(delta)
            self.assertTrue(original_ids.isdisjoint(changed.plan.operator_fold_ids()))
            ctx=dict(original.context);ctx.update(delta)
            with self.assertRaises(ValueError):self.resume(original,ctx)
        with self.assertRaises(ValueError):self.resume(original,secret=bytes(reversed(SECRET)))
        with self.assertRaises(FileExistsError):
            T.SignalDelivery.create(original.root,generated_roster(),original.context,SECRET,mapping_path=MAPPING_PATH)

    def test_stale_packet_hash_and_cross_fold_consume_first_final(self):
        for failure in ("hash","fold","delivery"):
            obj,fid=self.new();packet=obj.issue(fid,prepared(obj,fid));bad=response(packet,obj)
            if failure=="hash":bad["packet_sha256"]="0"*64
            if failure=="fold":bad["fold_id"]=obj.plan.operator_fold_ids()[1]
            if failure=="delivery":bad["delivery_id"]="d_"+"0"*64
            with self.assertRaises(ValueError):obj.submit(fid,bad)
            resumed=self.resume(obj)
            with self.assertRaises(ValueError):resumed.submit(fid,response(packet,obj))
            rows=all_rows(resumed.finish())
            self.assertEqual(sum(r["status"]=="failed" for r in rows),1)
            self.assertEqual(sum(r["status"]=="unstarted" for r in rows),175)

    def test_both_outcomes_and_access_conditions_restore_identical_source_support(self):
        documents = []
        for outcome in ("reproduction", "improvement"):
            for access in ("paper_data", "paper_data_author_code"):
                with self.subTest(outcome=outcome, access=access):
                    ctx = T.new_context("a"*64, access, "b"*64, outcome=outcome)
                    ctx["run_nonce"] = "c"*64  # Fixed only to isolate control differences.
                    obj, _ = self.new(ctx)
                    # Select the same scientific fold despite different opaque dispatch order.
                    score = obj.mapping.load_reference()
                    key = (score.ANIMALS[0], score.DAYS[0], "short", "real", 2)
                    fid = next(fid for fid in obj.plan.operator_fold_ids() if tuple(
                        obj.plan.operator_binding(fid)[k] for k in
                        ("animal", "day", "cue", "control", "trial_index")) == key)
                    packet = obj.issue(fid, prepared(obj, fid))
                    self.assertNotIn("outcome", packet)
                    obj.submit(fid, response(packet, obj))
                    document = self.resume(obj).finish()
                    self.assertEqual(len(document["panels"]), 176)
                    rows = all_rows(document)
                    self.assertEqual(len(rows), 176)
                    self.assertEqual([r["predicted_bins"] for r in rows if r["status"] == "finite"],
                                     [[7, 6, 5, 4, 3, 2, 1]])
                    self.assertEqual(sum(r["status"] == "unstarted" for r in rows), 175)
                    documents.append(document)
        self.assertTrue(all(document == documents[0] for document in documents))

    def test_outcome_separates_identity_and_cannot_relabel_durable_store(self):
        original, fid = self.new()
        packet = original.issue(fid, prepared(original, fid))
        changed, other = self.new({"outcome": "reproduction"})
        self.assertEqual(context()["outcome"], "improvement")  # Existing caller compatibility.
        self.assertTrue(set(original.plan.operator_fold_ids()).isdisjoint(changed.plan.operator_fold_ids()))
        ctx = dict(original.context, outcome="reproduction")
        with self.assertRaisesRegex(ValueError, "authentication"):
            self.resume(original, ctx)
        changed.issue(other, prepared(changed, other))
        with self.assertRaises(ValueError):
            changed.submit(other, response(packet, original))
        failed = [r for r in all_rows(self.resume(changed).finish()) if r["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        # The original store is still usable only with its original outcome/context.
        original.submit(fid, response(packet, original))
        self.assertEqual(sum(r["status"] == "finite" for r in all_rows(self.resume(original).finish())), 1)

    def test_unsupported_outcome_cannot_create_a_store(self):
        for outcome in ("", "reproduce", "combined", None, True):
            with self.subTest(outcome=outcome):
                path = FIXTURES / ("invalid-outcome-" + str(outcome))
                ctx = T.new_context("a"*64, "paper_data", "b"*64, outcome=outcome)
                with self.assertRaisesRegex(ValueError, "outcome|context"):
                    T.SignalDelivery.create(path, generated_roster(), ctx, SECRET, mapping_path=MAPPING_PATH)
                self.assertFalse(path.exists())

    def test_first_final_survives_restart_and_restores_existing_collector(self):
        obj,fid=self.new();packet=obj.issue(fid,prepared(obj,fid));obj.submit(fid,response(packet,obj))
        resumed=self.resume(obj)
        with self.assertRaises(ValueError):resumed.submit(fid,response(packet,obj))
        result=resumed.finish();rows=all_rows(result)
        self.assertEqual(len(result["panels"]),176)
        self.assertEqual(len(rows),176)
        self.assertEqual([r["predicted_bins"] for r in rows if r["status"]=="finite"],[[7,6,5,4,3,2,1]])
        self.assertEqual(sum(r["status"]=="unstarted" for r in rows),175)
        self.assertEqual(self.resume(obj).finish(),result)
        other=obj.plan.operator_fold_ids()[1]
        with self.assertRaises(ValueError):self.resume(obj).issue(other,prepared(obj,other))

    def test_interrupted_claim_is_failed_without_retry_or_prediction(self):
        obj,fid=self.new();packet=obj.issue(fid,prepared(obj,fid))
        original=obj._validate_response
        def interrupted(*args):raise RuntimeError("generated interruption after durable claim")
        obj._validate_response=interrupted
        with self.assertRaises(RuntimeError):obj.submit(fid,response(packet,obj))
        obj._validate_response=original
        resumed=self.resume(obj)
        with self.assertRaises(ValueError):resumed.submit(fid,response(packet,obj))
        failed=[r for r in all_rows(resumed.finish()) if r["status"]=="failed"]
        self.assertEqual(len(failed),1)
        self.assertNotIn("predicted_bins",failed[0])
        self.assertIn("interrupted",failed[0]["reason"])

    def test_record_authentication_blocks_cross_fold_file_replay(self):
        obj,fid=self.new();other=obj.plan.operator_fold_ids()[1]
        obj.issue(fid,prepared(obj,fid));obj.issue(other,prepared(obj,other))
        path=obj.root/(fid+".issue.json"); raw=(obj.root/(other+".issue.json")).read_bytes()
        fixture_write(path,raw)  # Deliberate generated corruption, charged cumulatively.
        with self.assertRaisesRegex(ValueError,"authentication"):
            self.resume(obj).resume_packet(fid,prepared(obj,fid))

    def test_truncated_durable_record_is_not_repaired(self):
        obj,fid=self.new();packet=obj.issue(fid,prepared(obj,fid));obj.submit(fid,response(packet,obj))
        fixture_write(obj.root/(fid+".result.json"),b'{')
        with self.assertRaises(ValueError):self.resume(obj).finish()
        with self.assertRaises(ValueError):self.resume(obj).submit(fid,response(packet,obj))

    def test_busy_store_and_operator_failure_do_not_create_new_attempt(self):
        obj,fid=self.new();obj.issue(fid,prepared(obj,fid));resumed=self.resume(obj)
        with obj._locked():
            with self.assertRaises(BlockingIOError):resumed.fail(fid,"busy")
        self.assertFalse((obj.root/(fid+".claim.json")).exists())
        obj.fail(fid,"Generated candidate failure")
        self.assertEqual(sum(r["status"]=="failed" for r in all_rows(self.resume(obj).finish())),1)

    def test_leaf_symlink_is_rejected_without_following_target(self):
        obj,fid=self.new();obj.issue(fid,prepared(obj,fid))
        target=obj.root/(fid+".claim.json")
        charge(len("MANIFEST.json"))
        os.symlink("MANIFEST.json",target)
        with self.assertRaises(ValueError):self.resume(obj).fail(fid,"no retry")
        with self.assertRaises(OSError):self.resume(obj).finish()


def charge(count):
    global WRITE_BYTES
    if WRITE_BYTES+count>WRITE_LIMIT:raise RuntimeError("Generated fixture logical write bound exceeded")
    WRITE_BYTES+=count


def fixture_write(path,raw):
    charge(len(raw));path.write_bytes(raw)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixtures",type=Path,required=True)
    parser.add_argument("--mapping-path",type=Path)
    args=parser.parse_args()
    MAPPING_PATH=args.mapping_path;FIXTURES=args.fixtures
    FIXTURES.mkdir(mode=0o700)  # Fresh retained fixtures; no deletion or reset.
    original_write=T.SignalDelivery._write
    def budgeted_write(self,name,payload):
        envelope={"payload":payload,"hmac":"0"*64}
        charge(len(T.canonical(envelope)))
        return original_write(self,name,payload)
    T.SignalDelivery._write=budgeted_write
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"fixture_cumulative_written_bytes":WRITE_BYTES,"fixture_write_limit":WRITE_LIMIT,
                      "test_methods":result.testsRun,"scoring_calls":0,"authentic_data_reads":0},sort_keys=True))
    sys.exit(not result.wasSuccessful())
