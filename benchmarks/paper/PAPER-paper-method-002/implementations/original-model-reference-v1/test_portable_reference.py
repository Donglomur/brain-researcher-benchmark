"""Portable stdlib source/interface contracts; no scientific-library imports.

The recording/Fraction assertions derive from the previously passed private
contract campaign. This new unittest projection is not that 17-case harness;
it has nine methods and awaits hosted CI validation. Recording objects do not
emulate JAX/NumPy floating point, AD, model execution or memory use. No fixtures
or result files are written, and no private paths or target data are required.
"""
import argparse
import ast
import contextlib
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
import weakref

SOURCES = {
    "streamed_model_operation.py": (11582, "ec4a90cf49378d94192b081a362c01c2975e55f8dd8c16e141b49c499c4ec027"),
    "model_operation.py": (22947, "c74030ec288d451eb29c4b1febd5664896c508471df3dcefcaebe992c9934460"),
    "streamed_batch.py": (5927, "05914614e16aaad8209c8e93f259f450dd3d12207e829116983b9bf4eb660a1b"),
    "FIT_SOURCE_INVERSE.json": (2718, "b0e6dbd83e63b7f4c967ed2ae364e230f7bb99d97fb2bb8c43821abbe9caf23c"),
}
TARGET_MODULES = ("jax", "jaxlib", "numpy", "tensorflow", "jaxley", "optax", "jaxley_mech")


def need(ok, message):
    if not ok:
        raise AssertionError(message)

def expect_refusal(fn, classes=(ValueError, AssertionError, TypeError)):
    try:
        fn()
    except classes:
        return
    raise AssertionError("expected refusal")

def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

def qualified_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return qualified_name(node.value) + "." + node.attr
    return ""

class DType:
    kind = "f"
    str = "<f8"

DTYPE = DType()

class HostValue:
    def __init__(self, value, shape=(), dtype=DTYPE):
        self.value, self.shape, self.dtype = value, shape, dtype

class DeviceValue:
    def __init__(self, value, shape, tracker, role):
        self.value, self.shape, self.dtype = value, shape, DTYPE
        self.tracker, self.role = tracker, role
        tracker["weak"].append(weakref.ref(self))

    def copy(self, order="C"):
        need(order == "C", "host copy order")
        self.tracker["copies"] += 1
        self.tracker["events"].append(("copy", self.role))
        return HostValue(self.value, self.shape, self.dtype)

class ReadyValue(HostValue):
    def __init__(self, host, tracker):
        super().__init__(host.value, host.shape, host.dtype)
        self.tracker = tracker

    def block_until_ready(self):
        self.tracker["ready"] += 1
        self.tracker["events"].append(("ready", self.shape))
        return self

class HostMatrix:
    def __init__(self, shape, dtype):
        self.shape, self.dtype = shape, dtype
        self.rows = [None] * shape[0]

    def __setitem__(self, sl, value):
        need(sl.step is None and sl.stop == sl.start + 1, "single prediction row write")
        need(value.shape == (1, 147), "prediction row shape")
        self.rows[sl.start] = value.value

class FakeNP:
    def __init__(self, tracker):
        self.tracker = tracker

    def asarray(self, value):
        need(isinstance(value, (DeviceValue, HostValue)), "only recording arrays")
        return value

    def add(self, a, b, *, out):
        need(out is a and a.dtype is b.dtype, "source-dtype in-place host sum")
        out.value = a.value + b.value
        self.tracker["adds"] += 1
        self.tracker["events"].append(("add", self.tracker["calls"]))

    def divide(self, a, denominator, *, out):
        need(out is a and type(denominator) is int, "one actual batch denominator")
        out.value = a.value / denominator
        self.tracker["divides"].append((denominator, self.tracker["calls"]))
        self.tracker["events"].append(("divide", denominator))

    def empty(self, shape, *, dtype):
        need(shape[1] == 147 and dtype is DTYPE, "full147 assembly dtype")
        self.tracker["allocations"].append(shape)
        return HostMatrix(shape, dtype)

class FakeJNP:
    def __init__(self, tracker):
        self.tracker = tracker

    def asarray(self, host):
        need(isinstance(host, HostValue), "mean host return")
        return ReadyValue(host, self.tracker)

class FakeTree:
    @staticmethod
    def tree_flatten(value):
        need(type(value) is tuple and len(value) == 3, "three fake raw leaves")
        return list(value), ("three-leaf-contract-tree",)

    @staticmethod
    def tree_unflatten(structure, leaves):
        need(structure == ("three-leaf-contract-tree",) and len(leaves) == 3, "unchanged fake tree")
        return tuple(leaves)

    @staticmethod
    def tree_leaves(value):
        return list(value)

class Rows:
    def __init__(self, name, count, columns):
        self.name, self.shape = name, (count, columns)

    def __getitem__(self, sl):
        need(type(sl) is slice and sl.step is None and sl.stop == sl.start + 1, "singleton source slice")
        return (self.name, sl.start, sl.stop)

def tracker():
    return {"weak": [], "copies": 0, "events": [], "ready": 0, "calls": 0,
            "adds": 0, "divides": [], "allocations": [], "order": []}

def stats():
    return {"training_singletons_completed": 0, "last_training_batch_completed_rows": 0,
            "completed_original_gradient_batches": 0, "last_global_mean_denominator": None,
            "validation_singletons_completed": 0, "last_validation_batch_completed_rows": 0,
            "completed_original_validation_batches": 0}

def recorded_gradient(t, opt, initial, count, fail_at=None, drift_at=None):
    def call(a, b, c, currents, labels, mask, state):
        i = t["calls"]
        need((a is opt[0] and b is opt[1] and c is opt[2] and state is initial), "fixed opt/init state")
        need(currents == ("current", i, i + 1) and labels == ("label", i, i + 1)
             and mask == ("mask", i, i + 1), "emitted row order and original operands")
        need(all(w() is None for w in t["weak"]), "prior device row remains live before next call")
        need(t["copies"] == 4 * i, "every prior loss/leaf copied before next call")
        t["calls"] += 1
        t["order"].append(i)
        if fail_at == i:
            raise RuntimeError("selected synthetic row refusal")
        loss = DeviceValue(Fraction(i), (), t, "loss")
        grads = (DeviceValue(Fraction(i + 1), (1,), t, "p0"),
                 DeviceValue(Fraction(2 * i - 3), (2,) if drift_at == i else (1,), t, "p1"),
                 DeviceValue(Fraction((-1) ** i), (1,), t, "p2"))
        return loss, grads
    return call

def gradient_contract(helper, count, fail_at=None, drift_at=None):
    t, s = tracker(), stats()
    opt, initial = (object(), object(), object()), object()
    check_events = []
    def check(stage):
        check_events.append((stage, s["training_singletons_completed"]))
    fn = recorded_gradient(t, opt, initial, count, fail_at, drift_at)
    invoke = lambda: helper["streamed_gradient"](fn, opt, Rows("current", count, 287),
        Rows("label", count, 147), Rows("mask", count, 147), initial,
        np=FakeNP(t), jnp=FakeJNP(t), tree_util=FakeTree, check=check, stats=s)
    if fail_at is not None or drift_at is not None:
        expect_refusal(invoke, (RuntimeError, ValueError))
        need(not t["divides"] and s["completed_original_gradient_batches"] == 0,
             "failure cannot return a partial mean batch")
        expected_completed = fail_at if fail_at is not None else drift_at
        need(s["training_singletons_completed"] == expected_completed, "failure-inclusive row counter")
        return {"rows": count, "refused_at": expected_completed, "complete_batches": 0}
    loss, gradients = invoke()
    need(loss.value == Fraction(count - 1, 2), "global loss mean")
    expected = (Fraction(count + 1, 2), Fraction(count - 4), Fraction(0 if count % 2 == 0 else 1, count))
    need(tuple(g.value for g in gradients) == expected, "global raw-gradient means including zero sum")
    need(t["order"] == list(range(count)), "exact full original order")
    need(t["divides"] == [(count, count)] * 4, "all divisions after every row with actual denominator")
    need(t["copies"] == 4 * count and t["adds"] == 4 * (count - 1), "bounded copy/sum trace")
    need(t["ready"] == 4 and all(w() is None for w in t["weak"]), "completed mean return and released row outputs")
    need(s["training_singletons_completed"] == count and s["completed_original_gradient_batches"] == 1
         and s["last_global_mean_denominator"] == count, "single logical batch accounting")
    need(len(check_events) == 2 * count, "before/after checkpoint per row")
    return {"rows": count, "calls": t["calls"], "copies": t["copies"], "mean_denominator": count,
            "mean_divisions_after_all_rows": 4, "zero_sum_retained": count % 2 == 0}

def prediction_contract(helper, count, wrong_sites=False):
    t, s, opt = tracker(), stats(), object()
    def predict(got_opt, currents):
        i = t["calls"]
        need(got_opt is opt and currents == ("current", i, i + 1), "prediction fixed opt/order")
        need(all(w() is None for w in t["weak"]), "prior prediction remains live")
        need(t["copies"] == i, "prediction copied before next call")
        t["calls"] += 1
        sites = 146 if wrong_sites else 147
        values = tuple(Fraction(i * 1000 + site) for site in range(sites))
        return DeviceValue(values, (1, sites), t, "prediction")
    invoke = lambda: helper["streamed_prediction"](predict, opt, Rows("current", count, 287),
        np=FakeNP(t), check=lambda stage: None, stats=s)
    if wrong_sites:
        expect_refusal(invoke, (ValueError,))
        need(s["completed_original_validation_batches"] == 0, "bad site count cannot complete")
        return {"rows": count, "refused_sites": 146}
    result = invoke()
    need(result.shape == (count, 147) and t["allocations"] == [(count, 147)], "one full output assembly")
    for i, row in enumerate(result.rows):
        need(row == tuple(Fraction(i * 1000 + site) for site in range(147)), "row-major all-site values")
    need(t["copies"] == count and t["calls"] == count and all(w() is None for w in t["weak"]), "synchronous row release")
    need(s["validation_singletons_completed"] == count and s["completed_original_validation_batches"] == 1,
         "one validation batch accounting")
    return {"rows": count, "sites": 147, "calls": count, "output_allocations": 1}

def portable_cli_contract(source_text):
    """Reusable text-based guards; no package paths or target imports."""
    tree = ast.parse(source_text)
    fs = functions(tree)
    env = {"argparse": argparse, "__doc__": "data-free portable interface control"}
    selected = [fs[name] for name in ("require", "parse_args", "run_prepared")]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), "portable-selected-stdlib-interface", "exec"), env)
    argv = ["--mode", "fit-source-defaults-streamed-v1", "--arrays", "arrays.npz", "--metadata", "meta.json",
            "--morphology-prefix", "morph", "--output", "out"]
    args = env["parse_args"](argv)
    need(vars(args) == {"mode":"fit-source-defaults-streamed-v1", "arrays":"arrays.npz", "metadata":"meta.json",
                       "morphology_prefix":"morph", "output":"out"}, "exact portable path routing")
    refusal_bytes = 0
    for bad in ([], [*argv[:1], "fit-source-defaults", *argv[2:]], [*argv, "--seconds", "600"]):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(err):
            expect_refusal(lambda bad=bad:env["parse_args"](bad), (SystemExit,))
        text = err.getvalue()
        need(len(text.encode()) <= 8192, "bounded generated parser diagnostic")
        refusal_bytes += len(text.encode())
    arrays, metadata, out, result = object(), object(), object(), object()
    events = []
    def loader(a, m):
        events.append(("load", a, m)); return arrays, metadata
    def fit(a, m, morphology, target):
        need(a is arrays and m is metadata and target is out, "unaltered objects forwarded")
        events.append(("fit", morphology)); return result
    got = env["run_prepared"](args, out, loader=loader, fit=fit)
    need(got is result and events == [("load", "arrays.npz", "meta.json"), ("fit", "morph")], "one actual loader then fit call")
    wrong = argparse.Namespace(**{**vars(args), "mode":"qualify-first-training-row"})
    events.clear()
    expect_refusal(lambda:env["run_prepared"](wrong,out,loader=loader,fit=fit), (ValueError,))
    need(not events, "wrong mode refused before loader")
    def broken_loader(a, m):
        raise LookupError("selected synthetic loader error")
    expect_refusal(lambda:env["run_prepared"](args,out,loader=broken_loader,fit=fit), (LookupError,))
    need(not events, "loader error cannot invoke fit")
    def broken_fit(*unused):
        raise RuntimeError("selected synthetic fit error")
    expect_refusal(lambda:env["run_prepared"](args,out,loader=loader,fit=broken_fit), (RuntimeError,))
    return {"parser_refusals":3,"captured_parser_bytes":refusal_bytes,"loader_then_fit_calls":2,
            "wrong_mode_and_failures_preserved":True,"target_imports":0}

def portable_inverse_contract(source_text, inverse, donor_text):
    tree, donor_tree = ast.parse(source_text), ast.parse(donor_text)
    fs, donor_fs = functions(tree), functions(donor_tree)
    derived = ast.get_source_segment(source_text, fs[inverse["derived_function"]]) + "\n"
    donor = ast.get_source_segment(donor_text, donor_fs[inverse["donor_function"]]) + "\n"
    need(hashlib.sha256(derived.encode()).hexdigest() == inverse["derived_function_sha256"], "exact derived full-fit function")
    need(hashlib.sha256(donor.encode()).hexdigest() == inverse["donor_function_sha256"], "exact donor full-fit function")
    restored = derived
    for item in reversed(inverse["exact_ordered_replacements"]):
        need(restored.count(item["after"]) == 1, "unique portable source replacement")
        restored = restored.replace(item["after"], item["before"], 1)
    need(restored == donor, "six inverse replacements restore exact full-fit function")
    fit = fs[inverse["derived_function"]]
    gradient = [n for n in ast.walk(fit) if isinstance(n,ast.Call) and qualified_name(n.func)=="streamed_gradient"]
    nonlinear = [n for n in ast.walk(fit) if isinstance(n,ast.Call) and qualified_name(n.func) in {"l2_norm","optimizer.update","optax.apply_updates"}]
    need(len(gradient)==1 and nonlinear and all(n.lineno>gradient[0].lineno for n in nonlinear), "one mean before unchanged optimizer block")
    def test_assignment(function):
        return next(n for n in ast.walk(function) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="test_predictions" for t in n.targets))
    need(ast.dump(test_assignment(fit),include_attributes=False)==ast.dump(test_assignment(donor_fs[inverse["donor_function"]]),include_attributes=False), "final128 vectorized call untouched")
    imports = [n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    need(not any(n.module in {"real_batch_operation","streamed_real_batch_operation"} for n in imports), "no private diagnostic driver imported")
    need(not any(isinstance(n,(ast.Global,ast.Nonlocal)) for n in ast.walk(tree)), "no global monkeypatch declarations")
    main_call = next(n for n in ast.walk(fs["main"]) if isinstance(n,ast.Call) and qualified_name(n.func)=="run_prepared")
    bindings = {kw.arg:qualified_name(kw.value) for kw in main_call.keywords}
    need(bindings=={"loader":"load_packet","fit":"fit_source_defaults_streamed_v1"}, "production CLI supplies original loader and streamed fit")
    return {"exact_inverse_replacements":6,"full_fit_function_restored":True,
            "original_optimizer_and_selection_preserved":True,"final128_vectorized_AST_identical":True,
            "final128_memory_or_numerical_qualification":False}

def portable_guard_contract(source_text):
    tree = ast.parse(source_text); fs = functions(tree)
    env = {"COMPONENT":"jaxley-original-model-reference-streamed-v1"}
    selected = [fs[name] for name in ("require","new_streaming_statistics","fit_source_defaults_streamed_v1")]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),"portable-selected-contract-wrapper","exec"),env)
    calls=[]; sentinel=object()
    def fake_fit(arrays,meta,morph,out,checkpoint,statistics):
        need(callable(checkpoint),"effective checkpoint callable")
        checkpoint("recording-contract-only")
        calls.append((arrays,meta,morph,out,checkpoint))
        statistics.update(training_singletons_completed=12185*21,validation_singletons_completed=3047*21,
                          completed_original_gradient_batches=48*21,completed_original_validation_batches=3*21)
        return {"sentinel":sentinel}
    env["_fit_source_defaults_streamed"]=fake_fit
    arrays={"currents":types.SimpleNamespace(shape=(15360,287))}
    returned=env["fit_source_defaults_streamed_v1"](arrays,"meta","morph","out")
    need(returned["sentinel"] is sentinel and len(calls)==1,"single prepared-fit call")
    need(returned["floating_point_equivalence_qualified"] is False and returned["resource_and_full_fit_qualification_from_source"] is False,"source cannot claim qualification")
    observed=[]
    env["fit_source_defaults_streamed_v1"](arrays,"meta","morph","out",checkpoint=observed.append)
    need(observed==["recording-contract-only"],"optional exact checkpoint forwarding")
    before=len(calls)
    expect_refusal(lambda:env["fit_source_defaults_streamed_v1"]({"currents":types.SimpleNamespace(shape=(15360,286))},None,None,None),(ValueError,))
    expect_refusal(lambda:env["fit_source_defaults_streamed_v1"](arrays,None,None,None,checkpoint=False),(ValueError,))
    need(len(calls)==before,"support/callback refusal before fit")
    def incomplete(*arguments): return {}
    env["_fit_source_defaults_streamed"]=incomplete
    expect_refusal(lambda:env["fit_source_defaults_streamed_v1"](arrays,None,None,None),(ValueError,))
    return {"declared_train_rows":12185*21,"declared_validation_rows":3047*21,"updates":1008,
            "validation_batches":63,"incomplete_fake_count_refused":True,"fake_fit_not_model_execution":True}

class PortableReferenceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target_modules_before = {name for name in sys.modules
            if any(name == root or name.startswith(root + ".") for root in TARGET_MODULES)}
        root = Path(__file__).resolve().parent
        cls.texts = {}
        for filename, (size, digest) in SOURCES.items():
            with (root / filename).open("rb") as stream:
                body = stream.read(size + 1)
            need(len(body) == size and hashlib.sha256(body).hexdigest() == digest,
                 "exact selected public source identity: " + filename)
            cls.texts[filename] = body.decode("utf-8")
        cls.helper_tree = ast.parse(cls.texts["streamed_batch.py"])
        need(all(isinstance(n, ast.FunctionDef) or
                 (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                  and isinstance(n.value.value, str)) for n in cls.helper_tree.body),
             "helper top-level definitions/docstring only")
        cls.helper = {"__name__": "portable_recording_contract_helper"}
        exec(compile(cls.helper_tree, "selected-public-streamed-helper", "exec"), cls.helper)
        cls.portable = cls.texts["streamed_model_operation.py"]
        cls.inverse = json.loads(cls.texts["FIT_SOURCE_INVERSE.json"])
        cls.donor = cls.texts["model_operation.py"]

    @classmethod
    def tearDownClass(cls):
        target_modules_after = {name for name in sys.modules
            if any(name == root or name.startswith(root + ".") for root in TARGET_MODULES)}
        need(target_modules_after <= cls.target_modules_before,
             "source contracts must not add target-library imports")

    def test_cli_and_prepared_forwarding(self):
        portable_cli_contract(self.portable)
        main = functions(ast.parse(self.portable))["main"]
        mkdir = [n for n in ast.walk(main) if isinstance(n, ast.Call)
                 and qualified_name(n.func) == "out.mkdir"]
        self.assertEqual(len(mkdir), 1)
        keywords = {n.arg: ast.literal_eval(n.value) for n in mkdir[0].keywords}
        self.assertEqual(keywords, {"mode": 0o700, "exist_ok": False})
        dispatch = next(n for n in ast.walk(main) if isinstance(n, ast.Call)
                        and qualified_name(n.func) == "run_prepared")
        self.assertLess(mkdir[0].lineno, dispatch.lineno)

    def test_exact_fit_inverse_and_final_test_route(self):
        portable_inverse_contract(self.portable, self.inverse, self.donor)

    def test_full_workload_wrapper_guards(self):
        # Only the outer support/count/report wrapper is called with a recorder;
        # the full-fit function, solver and target-library stack never execute.
        portable_guard_contract(self.portable)

    def test_original_shapes_and_refusals(self):
        for rows, kind in ((153, "training"), (256, "training"),
                           (999, "validation"), (1024, "validation")):
            self.assertEqual(self.helper["singleton_slices"](rows, kind),
                             tuple((i, i + 1) for i in range(rows)))
        for rows, kind in ((1, "training"), (128, "training"), (999, "training"),
                           (256, "validation"), (1025, "validation"),
                           (True, "training"), (153, "other")):
            expect_refusal(lambda r=rows, k=kind: self.helper["singleton_slices"](r, k))
        for rows in (153, 256):
            self.assertEqual(self.helper["training_shape_contract"](
                (rows, 287), (rows, 147), (rows, 147)), rows)
        for current, labels, mask in (
                ((256, 286), (256, 147), (256, 147)),
                ((256, 287), (256, 146), (256, 147)),
                ((153, 287), (153, 147), (256, 147)),
                ((256,), (256, 147), (256, 147))):
            expect_refusal(lambda c=current, l=labels, m=mask:
                           self.helper["training_shape_contract"](c, l, m))

    def test_gradient_full_batch_fixed_state_and_mean(self):
        gradient_contract(self.helper, 256)

    def test_gradient_tail_fixed_state_and_mean(self):
        gradient_contract(self.helper, 153)

    def test_gradient_failure_and_structure_refusals(self):
        gradient_contract(self.helper, 153, fail_at=7)
        gradient_contract(self.helper, 153, drift_at=1)

    def test_ordered_validation_predictions_and_refusal(self):
        prediction_contract(self.helper, 1024)
        prediction_contract(self.helper, 999)
        prediction_contract(self.helper, 999, wrong_sites=True)

    def test_helper_reduction_and_release_structure(self):
        fs = functions(self.helper_tree)
        gradient, prediction = fs["streamed_gradient"], fs["streamed_prediction"]
        calls = [qualified_name(n.func) for n in ast.walk(self.helper_tree)
                 if isinstance(n, ast.Call)]
        forbidden = {"jit", "vmap", "l2_norm", "optimizer.update", "optax.clip", "optax.sgd"}
        need(not any(name in forbidden or "random" in name or "corrcoef" in name
                     for name in calls), "no helper normalization/update/RNG/JIT/scoring")
        loop = next(n for n in gradient.body if isinstance(n, ast.For))
        self.assertFalse(any(isinstance(n, ast.Call) and qualified_name(n.func) == "np.divide"
                             for n in ast.walk(loop)))
        divides = [n for n in ast.walk(gradient) if isinstance(n, ast.Call)
                   and qualified_name(n.func) == "np.divide"]
        self.assertEqual(len(divides), 2)
        need(all(isinstance(n.args[1], ast.Name) and n.args[1].id == "rows" for n in divides),
             "one actual original-row denominator")
        deletes = {n.id for node in ast.walk(loop) if isinstance(node, ast.Delete)
                   for n in ast.walk(node) if isinstance(n, ast.Name)}
        need({"loss_device", "gradients_device", "device_leaves", "host_leaves",
              "loss_host", "leaf", "accumulator"} <= deletes, "row/leaf references released")
        call = next(n for n in ast.walk(loop) if isinstance(n, ast.Call)
                    and qualified_name(n.func) == "gradient")
        need(isinstance(call.args[0], ast.Starred) and isinstance(call.args[0].value, ast.Name)
             and call.args[0].value.id == "opt" and isinstance(call.args[-1], ast.Name)
             and call.args[-1].id == "init_states", "fixed source opt and initial state")
        self.assertEqual(sum(isinstance(n, ast.Call) and qualified_name(n.func) == "gradient"
                             for n in ast.walk(gradient)), 1)
        p_loop = next(n for n in prediction.body if isinstance(n, ast.For))
        p_del = {n.id for node in ast.walk(p_loop) if isinstance(node, ast.Delete)
                 for n in ast.walk(node) if isinstance(n, ast.Name)}
        need({"device_prediction", "host_prediction"} <= p_del, "prediction references released")


if __name__ == "__main__":
    unittest.main()
