"""Portable operator API for the recovered NEURAL-093 four-arm score.

No candidate execution or data discovery. The caller owns authentication of the
original panel, plan and operator commitment and supplies a protected reader.
All recovered modules are byte-pinned; no historical workspace is needed.
"""
import builtins
import hashlib
from pathlib import Path
from types import ModuleType


PINS = {
    "parent_validation": (5959, "71cd007b9a91bd02e3b32ad81f19f864ab8be686d19a07d72a799095110925a7"),
    "controls": (8831, "ab65c260b0661c36b883573fff01acc3e9266fe2f3aa8d2c42d69c64d6de87cc"),
    "comparison": (10734, "6d9a66530d219b8b8391f5b373613081f735e296a6182a6986c0c2a39b917e3d"),
    "score_core": (9603, "42fb4d454098e919e92dde979f1c4209676c56b0016bdc4e198b62a1e8ebffa2"),
    "trusted_metrics": (6746, "2cb24293b729f8a5ac07531a664d68e199501de5793fbc34953a2eb797ae65f7"),
    "packet_plan": (4045, "d6cd62be4fa2838037da8c84e8375096c203191aac6a5468632393acabaaadb1"),
}


def load_sources():
    """Authenticate the entire small source closure before executing any of it."""
    root = Path(__file__).resolve().parent / "recovered"
    raw = {}
    for name, (size, digest) in PINS.items():
        path = root / (name + ".py")
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise ValueError("recovered source extent: " + name)
        with path.open("rb") as stream:
            body = stream.read(size + 1)
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("recovered source digest: " + name)
        raw[name] = body
    captured = {}
    deps = ModuleType("_neural093_portable_deps")
    deps.load = lambda: dict(captured)

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name == "deps":
            return deps
        if level == 0 and name in PINS:
            return captured[name]
        return builtins.__import__(name, globals, locals, fromlist, level)

    for name in PINS:
        module = ModuleType("_neural093_recovered_" + name)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": importing}
        exec(compile(raw[name], "recovered/" + name + ".py", "exec"), module.__dict__)
        captured[name] = module
    return captured


def verify_plan(panel, plan, sources):
    """Retain the original controller's whole-plan gate at the portable API.

    The recovered kernel assumes its controller has checked plan length before
    zip(). Here a shortened plan must fail before the first protected read.
    This validates joins; it does not authenticate the operator supplying them.
    """
    c, m = sources["controls"], sources["comparison"]
    sessions = m._scope(panel)
    c.need(plan["schema"] == "neural093_four_arm_operator_plan_v1"
           and plan["packet_count"] == 312 and plan["prediction_count"] == 156
           and type(plan["sessions"]) is list and len(plan["sessions"]) == 39,
           "complete 312-packet plan before protected reads")
    for session, planned in zip(sessions, plan["sessions"], strict=True):
        c.need(planned["ordinal"] == session["ordinal"]
               and planned["session_token"] == session["session_token"]
               and set(planned["packets"]) == set(c.ARMS), "ordered complete plan identity")
        descriptor = planned["private_mapping"]
        m.fields(descriptor, ("path", "bytes", "sha256"), "protected descriptor fields")
        m.descriptor({k: descriptor[k] for k in ("bytes", "sha256")})
        c.need(descriptor["bytes"] <= 2097152 and type(descriptor["path"]) is str
               and bool(descriptor["path"]), "bounded protected descriptor")
        for arm in c.ARMS:
            c.need(set(planned["packets"][arm]) == set(c.PHASES), "both packet phases")
            for phase in c.PHASES:
                raw = (session["original_manifest_bytes"] if arm in c.ORIGINAL_ARMS
                       else session["control_manifest_bytes"])[arm][phase]
                packet = planned["packets"][arm][phase]
                doc = c.parse(raw, c.MAX_MANIFEST)
                c.need(packet["manifest"] == c.pin(raw)
                       and set(packet["files"]) == set(doc["files"]), "exact packet file allowlist")
                for name, item in packet["files"].items():
                    c.need(all(item[k] == doc["files"][name][k] for k in ("bytes", "sha256")),
                           "exact packet file identity")


def score_study(panel, plan, commit, raw_outputs, private_reader, np):
    """Score all 156 captured outputs, then read all 39 protected mappings.

    A malformed final output prevents *every* protected callback. Source APIs
    and output schemas remain in recovered/. np is an operator-supplied NumPy.
    Returned session/mouse records are operator evidence, not participant data.
    """
    sources = load_sources()
    verify_plan(panel, plan, sources)
    summary = sources["trusted_metrics"].score(
        panel, plan, commit, raw_outputs, private_reader, np)
    return {
        "schema": "neural093_current_absolute_score_v1",
        "primary": {
            "arm": "neural_wheel_plus_context", "metric": "natural_log_loss",
            "direction": "lower", "units": "nats_per_query",
            "value": summary["equal_mouse_absolute_metrics"]["neural_wheel_plus_context"]["natural_log_loss"],
        },
        "required_companion": "neural_increment_given_wheel_context / natural_log_loss",
        "recovered_four_arm_summary": summary,
        "operator_authentication_performed": False,
        "participant_runtime_qualified": False,
        "scientific_result_established": False,
    }
