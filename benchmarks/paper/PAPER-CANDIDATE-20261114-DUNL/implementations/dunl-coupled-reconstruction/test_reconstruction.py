import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import signal
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("dunl_reconstruction_under_test",
                                            Path(__file__).with_name("reconstruction.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def encode(records):
    return b"".join(M.canonical(x) + b"\n" for x in records)


def fixture(neurons=10, trials=50):
    roster = [{"case_id": f"n{n}-t{t}", "neuron_id": f"n{n}", "trial_id": f"t{t}"}
              for n in range(neurons) for t in range(trials)]
    header = dict(M.FIXED, schema="dunl_reconstruction_owner_v1", cohort_id="invented",
                  source_cohort_sha256="1"*64, response_samples=27, roster=roster)
    kernel = [0.6, -0.8] + [0.0]*23
    code, baseline = [1.0, 2.0, 0.0], -0.2
    # Independently written forward-convolution expected values; not M.decode.
    eta = [0.4, 0.2, -1.8] + [-0.2]*24
    response = [1.0/(1.0+math.exp(-x)) for x in eta]
    sub_header = {"schema": "dunl_reconstruction_submission_v1", "arm": "paper_data",
                  "context_id": M.context_id(header), "kernel": kernel,
                  "method_manifest_sha256": "2"*64}
    owner = [header] + [{"case_id": item["case_id"], "y": [0.2,0.4,0.6]*9}
                        for item in roster]
    sub = [sub_header] + [{"case_id": item["case_id"], "code": code[:],
                         "baseline": baseline, "eta": eta[:], "p": response[:]}
                        for item in roster]
    return owner, sub


def score(owner, sub):
    raw = encode(owner)
    return M.score_streams(io.BytesIO(raw), io.BytesIO(encode(sub)),
                           hashlib.sha256(raw).hexdigest(), sub[0]["arm"])


class ReconstructionTests(unittest.TestCase):
    def test_complete_500_cases_both_arms_and_independent_loss(self):
        owner, sub = fixture()
        expected = math.fsum(math.log1p(math.exp(a))-b*a
                             for a,b in zip(sub[1]["eta"],owner[1]["y"]))/27
        result = score(owner, sub)
        self.assertEqual((result["cases"],result["neurons"],result["scored_values"]),
                         (500,10,13500))
        self.assertAlmostEqual(result["normalized_response_loss"],expected,places=12)
        self.assertEqual(result["positive_code_entries"],1000)
        self.assertEqual(result["code_entries_including_zeros"],1500)
        self.assertFalse(result["scientific_qualification"])
        sub[0]["arm"]="paper_data_official_code"
        self.assertEqual(score(owner,sub)["normalized_response_loss"],
                         result["normalized_response_loss"])

    def test_convolution_orientation_boundary_and_scalar_baseline(self):
        owner,sub=fixture(1,1)
        self.assertEqual(len(M.decode(sub[0]["kernel"],sub[1]["code"],-.2)),27)
        for actual,expected in zip(M.decode(sub[0]["kernel"],sub[1]["code"],-.2),sub[1]["eta"]):
            self.assertAlmostEqual(actual,expected,places=14)
        sub[1]["baseline"]=[-.2]*27
        with self.assertRaises(M.Refusal):score(owner,sub)

    def test_uncoupled_identity_response_is_rejected(self):
        owner,sub=fixture(1,1)
        sub[1]["p"]=owner[1]["y"][:]
        with self.assertRaisesRegex(M.Refusal,"inverse-link"):score(owner,sub)

    def test_uncoupled_logits_and_scale_ambiguity_rejected(self):
        owner,sub=fixture(1,1)
        sub[1]["eta"][0]+=0.1
        with self.assertRaisesRegex(M.Refusal,"logits"):score(owner,sub)
        owner,sub=fixture(1,1)
        sub[0]["kernel"]=[2*x for x in sub[0]["kernel"]]
        sub[1]["code"]=[x/2 for x in sub[1]["code"]]
        with self.assertRaisesRegex(M.Refusal,"unit-L2"):score(owner,sub)

    def test_missing_extra_reordered_and_duplicate_cases(self):
        owner,sub=fixture(2,2)
        for rows in [sub[:-1],sub+[sub[-1]],sub[:1]+[sub[2],sub[1]]+sub[3:],sub[:2]+sub[1:2]+sub[3:]]:
            with self.subTest(rows=len(rows)),self.assertRaises(M.Refusal):score(owner,rows)
        owner[0]["roster"][1]=copy.deepcopy(owner[0]["roster"][0])
        with self.assertRaises(M.Refusal):score(owner,sub)

    def test_invalid_values_and_boolean_numbers(self):
        for key,value in [("code",[-1,2,0]),("eta",[float("inf")]*27),
                          ("p",[1.1]*27),("baseline",True)]:
            owner,sub=fixture(1,1);sub[1][key]=value
            if key=="eta":
                with self.assertRaises(ValueError):encode(sub)
            else:
                with self.assertRaises(M.Refusal):score(owner,sub)
        owner,sub=fixture(1,1);owner[1]["y"][0]=True
        with self.assertRaises(M.Refusal):score(owner,sub)

    def test_units_are_fixed_and_not_hertz(self):
        owner,sub=fixture(1,1);owner[0]["bin_period_us"]=1000
        with self.assertRaises(M.Refusal):score(owner,sub)
        owner,sub=fixture(1,1);sub[1]["p"]=[200*x for x in sub[1]["p"]]
        with self.assertRaises(M.Refusal):score(owner,sub)

    def test_context_excludes_targets_but_owner_hash_does_not(self):
        owner,sub=fixture(1,1);before=M.context_id(owner[0]);raw=encode(owner)
        owner[1]["y"][0]=0.8
        self.assertEqual(M.context_id(owner[0]),before)
        with self.assertRaisesRegex(M.Refusal,"owner file identity"):
            M.score_streams(io.BytesIO(encode(owner)),io.BytesIO(encode(sub)),
                            hashlib.sha256(raw).hexdigest(),"paper_data")

    def test_operator_pins_arm_independently_of_candidate(self):
        owner,sub=fixture(1,1);raw=encode(owner)
        sub[0]["arm"]="paper_data_official_code"
        with self.assertRaisesRegex(M.Refusal,"operator-selected arm mismatch"):
            M.score_streams(io.BytesIO(raw),io.BytesIO(encode(sub)),
                            hashlib.sha256(raw).hexdigest(),"paper_data")

    def test_duplicate_keys_nonfinite_and_truncated_records(self):
        for raw in [b'{"x":1,"x":2}\n',b'{"x":NaN}\n',b'{"x":1}',b'\xff\n']:
            with self.subTest(raw=raw),self.assertRaises(M.Refusal):M.Lines(io.BytesIO(raw)).read()
        with self.assertRaises(M.Refusal):M.Lines(io.BytesIO(b' '*M.LINE_LIMIT+b'\n')).read()

    def test_explicit_utf8_rejects_other_json_encodings(self):
        for encoding in ['utf-16-be','utf-16-le','utf-32-be','utf-32-le']:
            raw='{"x":1}'.encode(encoding)+b'\n'
            with self.subTest(encoding=encoding),self.assertRaises(M.Refusal):
                M.Lines(io.BytesIO(raw)).read()
        self.assertEqual(M.Lines(io.BytesIO('{"x":"é"}\n'.encode('utf-8'))).read(),{'x':'é'})

    def test_oversized_json_integer_is_structured_refusal(self):
        raw=b'{"x":'+b'1'*5000+b'}\n'
        with self.assertRaises(M.Refusal):M.Lines(io.BytesIO(raw)).read()

    def test_fifo_is_refused_without_waiting_for_a_writer(self):
        def alarm(signum,frame):raise AssertionError('FIFO open blocked')
        with tempfile.TemporaryDirectory(prefix='dunl-invented-fifo-') as tmp:
            fifo=Path(tmp)/'input';os.mkfifo(fifo)
            previous=signal.signal(signal.SIGALRM,alarm)
            try:
                signal.alarm(1)
                with self.assertRaises(M.Refusal):M.open_input(fifo)
            finally:
                signal.alarm(0);signal.signal(signal.SIGALRM,previous)

    def test_extreme_logits_stable_loss_and_no_tolerance_score_gain(self):
        self.assertEqual(M.normalized_loss(1000,1),0)
        self.assertEqual(M.normalized_loss(-1000,0),0)
        self.assertEqual(M.normalized_loss(1000,0),1000)
        owner,sub=fixture(1,1);before=score(owner,sub)
        sub[1]["eta"][0]+=1e-8;sub[1]["p"][0]+=1e-8
        after=score(owner,sub)
        self.assertEqual(after["normalized_response_loss"],before["normalized_response_loss"])
        self.assertEqual(after["normalized_response_mse"],before["normalized_response_mse"])

    def test_unequal_neuron_case_weighting(self):
        owner,sub=fixture(2,2)
        del owner[0]["roster"][-1];del owner[-1];del sub[-1]
        owner[3]["y"]=[1.0]*27
        sub[0]["context_id"]=M.context_id(owner[0])
        result=score(owner,sub)
        self.assertNotEqual(result["normalized_response_loss"],result["equal_neuron_loss"])
        self.assertEqual([x["cases"] for x in result["per_neuron"]],[2,1])

    def test_owner_roster_and_whole_work_capacity(self):
        owner,sub=fixture(1,1)
        owner[0]["kernel_samples"]=True
        with self.assertRaises(M.Refusal):score(owner,sub)
        owner,sub=fixture();owner[0]["response_samples"]=4096
        with self.assertRaisesRegex(M.Refusal,"work ceiling"):score(owner,sub)

    def test_cli_complete_and_create_only_output_no_score_stdout(self):
        owner,sub=fixture()
        with tempfile.TemporaryDirectory(prefix="dunl-invented-control-") as tmp:
            root=Path(tmp);a=root/'owner.jsonl';b=root/'candidate.jsonl';out=root/'score.json'
            raw=encode(owner);a.write_bytes(raw);b.write_bytes(encode(sub))
            args=['--owner',str(a),'--owner-sha256',hashlib.sha256(raw).hexdigest(),
                  '--submission',str(b),'--arm','paper_data','--output',str(out)]
            stdout,stderr=io.StringIO(),io.StringIO()
            with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                self.assertEqual(M.main(args),0)
                before=out.read_bytes();self.assertEqual(M.main(args),2)
            self.assertEqual(out.read_bytes(),before)
            self.assertNotIn('normalized_response_loss',stdout.getvalue())
            self.assertEqual(json.loads(before)["cases"],500)
            self.assertEqual(out.stat().st_mode & 0o777,0o600)

    def test_cli_refuses_symlink_and_owner_hash_without_output(self):
        owner,sub=fixture(1,1)
        with tempfile.TemporaryDirectory(prefix="dunl-invented-control-") as tmp:
            root=Path(tmp);a=root/'owner.jsonl';b=root/'candidate.jsonl';out=root/'score.json'
            a.write_bytes(encode(owner));b.write_bytes(encode(sub))
            link=root/'owner-link.jsonl';link.symlink_to(a)
            args=['--owner',str(link),'--owner-sha256','0'*64,'--submission',str(b),
                  '--arm','paper_data','--output',str(out)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(M.main(args),2);args[1]=str(a);self.assertEqual(M.main(args),2)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
