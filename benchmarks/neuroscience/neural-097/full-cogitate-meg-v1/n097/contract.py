"""Read frozen design metadata without importing scientific implementations."""
from pathlib import Path
from .io import need, read_json, read, identity

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("SIGNAL", "PRE", "NUISANCE", "SIGNAL_NUISANCE", "PRE_NUISANCE")
ACCESS = ("A", "B")
MODES = ("F", "I")
SEEDS = (97097, 97098, 97099)
RELEVANCES = ("Irrelevant", "Relevant non-target")
DURATIONS = ("500ms", "1000ms", "1500ms")
ORIENTATIONS = ("Center", "Left", "Right")
CHANNELS = ("MEG1931", "MEG2121", "MEG2331", "MEG1921", "MEG2111", "MEG2341")
# PUB-N097-02: the exact ordered roster is an unpublished protected input.
# Its immutable whole-source identity preserves the accepted selector/order.
PROTECTED_ROSTER_SOURCE = {"bytes": 4038, "sha256": "ba7474f57ddb2c62b35c91ee09cfe898c65a5865cd723c54b22a06680b01c0ff"}

class _ProtectedRoster:
    __slots__ = ("_values",)
    def __init__(self):
        self._values = None
    def _get(self):
        need(self._values is not None, "Exact protected roster has not been admitted")
        return self._values
    def __iter__(self): return iter(self._get())
    def __len__(self): return len(self._get())
    def __getitem__(self, key): return self._get()[key]
    def index(self, value): return self._get().index(value)

ROSTER = _ProtectedRoster()

def bind_protected_roster(descriptor):
    """Trusted future operator only; no execution/import of protected source.

    No environment or automatic path fallback. Cannot run in this disabled
    release. Never pass this descriptor or its body to a candidate process.
    """
    require_deployment()
    need(ROSTER._values is None, "Protected roster already bound; no rebinding")
    need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"}, "Exact protected dependency descriptor")
    need({k: descriptor[k] for k in ("bytes", "sha256")} == PROTECTED_ROSTER_SOURCE, "Exact accepted whole-source roster anchor")
    need(type(descriptor["path"]) is str and descriptor["path"], "Protected dependency path required")
    try:
        import ast
        body = read(descriptor["path"], 4038, PROTECTED_ROSTER_SOURCE)
        tree = ast.parse(body)
        assignments = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ROSTER" for t in n.targets)]
        need(len(assignments) == 1, "Unique protected selector")
        values = ast.literal_eval(assignments[0].value)
        need(type(values) is tuple and len(values) == 33 and all(type(x) is str and x for x in values) and len(set(values)) == 33, "Exact complete protected selector type")
    except Exception:
        from .io import Refusal
        raise Refusal("Protected roster source unavailable or invalid") from None
    ROSTER._values = values

METRICS = ("balanced_accuracy", "legacy_logloss", "balanced_logloss", "balanced_brier")
FEATURE_PAIRS = (("SIGNAL","PRE"),("SIGNAL","NUISANCE"),("SIGNAL_NUISANCE","NUISANCE"),("SIGNAL_NUISANCE","PRE_NUISANCE"))
DEPLOYMENT_ENABLED = False

def load():
    pins = read_json(ROOT / "contracts/PINS.json", 100_000)
    out = {}
    for name, row in pins.items():
        need(row["portable"] == "contracts/" + name, "Selected portable contract path")
        body = read(ROOT / row["portable"], 2_000_000, row["original"])
        if name.endswith(".json"):
            from .io import parse
            out[name] = parse(body)
    c = out["SCIENTIFIC_CONTRACT.json"]; e = out["ESTIMAND_REPORTING_CONTRACT.json"]
    need(c["cohort"]["selected_person_count"] == 33 and c["outer_split"]["folds"] == 66, "Full33/66 contract")
    need(c["conditions"]["arms"] == list(ARMS) and c["conditions"]["seeds"] == list(SEEDS), "Fixed conditions")
    need(e["inherited_scope"]["candidate_outputs"] == 3960, "Complete campaign")
    need(all(x["scientifically_closed"] is False for x in out["GATES.json"]["gates"]), "Original gates remain open")
    binding = {
        "scientific": pins["SCIENTIFIC_CONTRACT.json"]["original"],
        "estimand_reporting": pins["ESTIMAND_REPORTING_CONTRACT.json"]["original"],
    }
    return out, binding

def require_deployment():
    need(DEPLOYMENT_ENABLED, "Scientific deployment disabled; independent runtime/data/native/exposure/reference qualification and separate selection required")

def condition(access, mode, seed):
    need(access in ACCESS and mode in MODES and type(seed) is int and seed in SEEDS, "Exact condition")
    return f"{access}-{mode}-{seed}"

def case_job(access, mode, seed, person_index, half, arm):
    condition(access, mode, seed)
    need(type(person_index) is int and 0 <= person_index < 33 and half in (0,1) and arm in ARMS, "Exact fold/arm")
    return f"{access}-{mode}-{seed}/p{person_index:02d}/h{half}/{arm}"

def plan(binding):
    jobs = []
    for access in ACCESS:
        for mode in MODES:
            for seed in SEEDS:
                for p in range(33):
                    for h in (0,1):
                        for arm in ARMS:
                            jobs.append({"id": case_job(access,mode,seed,p,h,arm),
                                         "condition": condition(access,mode,seed),
                                         "access": access,"mode":mode,"seed":seed,
                                         "person_index":p,"half":h,"arm":arm})
    need(len(jobs)==3960 and len({x["id"]for x in jobs})==3960, "Full job union")
    return {"schema":"n097-campaign-plan-v1","task_id":"NEURAL-097","contract":binding,
            "jobs":jobs,"query_expansion":"Requires complete admitted authentic panel; counts not invented",
            "reference_jobs":[{"id":f"{ref}/p{p:02d}/h{h}/{arm}","reference":ref,"person_index":p,"half":h,"arm":arm,"seed":97097}
                              for ref in ("R0","R1","R2","R3","R4")for p in range(33)for h in (0,1)for arm in ARMS],
            "interpretation_jobs":[condition(a,m,s)for a in ACCESS for m in MODES for s in SEEDS],
            "scientific_execution_authorized":False}
