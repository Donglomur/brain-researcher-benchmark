"""Trusted operator admission; candidate programs cannot supply these records."""
import math
import os
from pathlib import Path
import stat
import time
from common import need, plain, read, decode, admit_pin

TASK_ID = "PAPER-FIND-003"
IMAGE = "sha256:01dfc25e93283a5f7f2031628236f95b59f4a3acd9e9e9894601fdaf60dba61d"
PUBLIC_NAMES = ("dd_ripple_during_learning_raw.csv", "INPUT_IDENTITY.json",
                "TASK.md", "DATA_AND_OUTPUT_CONTRACT.md", "RIGHTS_AND_LINEAGE.md")
HOST_BYTES = 536870912
VM_BYTES = 3221225472
MARGIN_BYTES = 1073741824

def exact(value, keys, code):
    need(type(value) is dict and set(value) == set(keys), code)

def descriptor(value, cap):
    exact(value, ("path", "bytes", "sha256"), "exact external descriptor")
    plain(value["path"])
    admit_pin({k:value[k] for k in ("bytes","sha256")}, cap)
    return value

def load(value, budget, cap):
    descriptor(value, cap)
    return read(value["path"], {k:value[k] for k in ("bytes","sha256")}, budget, cap)

def independent_paths(*values):
    paths = [plain(x) for x in values]
    for i, a in enumerate(paths):
        for b in paths[i+1:]:
            need(a != b and not a.is_relative_to(b) and not b.is_relative_to(a),
                 "distinct nonnested operator paths")
    return paths

def capacity(value, *, wall=None, monotonic=None):
    exact(value, ("observed_epoch", "observed_monotonic", "available_bytes",
                  "other_reserved_bytes", "memory_pressure", "pageout_growth",
                  "swapout_growth", "swap_used_growth", "logical_cpus",
                  "observed_cpu_cores", "other_selected_cpu_cores",
                  "roster_confirmed"), "complete current capacity")
    for key in ("available_bytes", "other_reserved_bytes", "memory_pressure",
                "pageout_growth", "swapout_growth", "swap_used_growth", "logical_cpus"):
        need(type(value[key]) is int and value[key] >= 0, "integer capacity "+key)
    for key in ("observed_epoch", "observed_monotonic", "observed_cpu_cores",
                "other_selected_cpu_cores"):
        need(type(value[key]) in (int,float) and math.isfinite(value[key])
             and value[key] >= 0, "finite capacity "+key)
    wall_age = (time.time() if wall is None else wall) - value["observed_epoch"]
    mono_age = (time.monotonic() if monotonic is None else monotonic) - value["observed_monotonic"]
    need(0 <= wall_age <= 60 and 0 <= mono_age <= 60 and abs(wall_age-mono_age) <= 2,
         "fresh joined capacity clocks")
    need(value["memory_pressure"] == 1 and value["pageout_growth"] == 0 and
         value["swapout_growth"] == 0 and value["swap_used_growth"] == 0 and
         value["roster_confirmed"] is True, "normal stable current roster")
    need(value["available_bytes"] >= HOST_BYTES + VM_BYTES + MARGIN_BYTES +
         value["other_reserved_bytes"], "complete host and VM headroom")
    need(value["logical_cpus"] >= 4 and value["observed_cpu_cores"] +
         value["other_selected_cpu_cores"] + 1.75 <= value["logical_cpus"],
         "complete CPU headroom")
    return value

def admit(request, preparation, runtime, cap, contract):
    exact(request, ("schema", "task_id", "selected", "output_root", "program",
                    "input_root", "preparation", "runtime", "capacity",
                    "source_manifest_sha256", "prior_known_seconds",
                    "operator_ceiling_seconds"), "exact operation request")
    need(request["schema"] == "human-ripple-program-request/v1" and
         request["task_id"] == TASK_ID and request["selected"] is True,
         "explicit single operator selection")
    for key in ("prior_known_seconds", "operator_ceiling_seconds"):
        need(type(request[key]) in (int,float) and math.isfinite(request[key]),
             "finite additive accounting")
    need(request["prior_known_seconds"] >= 1290 and
         request["operator_ceiling_seconds"] >= request["prior_known_seconds"] + 75,
         "preserved historical cost and prospective whole allowance")
    descriptor(request["program"],65536)
    exact(preparation, ("schema", "task_id", "condition", "public_files",
                        "private_bundle", "accepted_review_sha256"),
          "exact maintainer preparation")
    need(preparation["schema"] == "human-ripple-prepared-inputs/v1" and
         preparation["task_id"] == TASK_ID and preparation["condition"] ==
         "original_long_table_and_protocol", "original protocol condition")
    need(type(preparation["public_files"]) is dict and
         set(preparation["public_files"]) == set(PUBLIC_NAMES), "exact public roles")
    for name, value in preparation["public_files"].items():
        admit_pin(value,1200000 if name.endswith(".csv") else 32768)
    need(preparation["public_files"] == contract["public_files"],
         "exact original five-file preparation")
    for h in (preparation["accepted_review_sha256"],request["source_manifest_sha256"]):
        admit_pin({"bytes":0,"sha256":h},0)
    descriptor(preparation["private_bundle"],1048576)
    exact(runtime, ("schema", "image", "docker", "docker_physical",
                    "daemon_socket", "daemon_guard", "qualification_review_sha256"),
          "exact maintainer runtime")
    need(runtime["schema"] == "human-ripple-runtime-admission/v1" and
         runtime["image"] == IMAGE, "exact historical candidate image")
    admit_pin({"bytes":0,"sha256":runtime["qualification_review_sha256"]},0)
    plain(runtime["docker"]);plain(runtime["daemon_socket"])
    need(type(runtime["docker_physical"]) is list and len(runtime["docker_physical"]) == 7
         and all(type(x) is int for x in runtime["docker_physical"]),
         "complete executable physical identity")
    exact(runtime["daemon_guard"],("dev","inode","mode","uid","gid","nlink"),
          "complete socket identity")
    need(all(type(v) is int for v in runtime["daemon_guard"].values()),
         "integer socket identity")
    independent_paths(request["output_root"],request["input_root"],
                      request["program"]["path"],preparation["private_bundle"]["path"])
    output = plain(request["output_root"])
    need(not output.exists() and output.parent.is_dir(), "fresh output namespace")
    capacity(cap)
    return request

