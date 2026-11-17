"""Pure admission arithmetic for the single NIDER private44 caller.

No probes, processes, files, clocks or scientific modules are accessed here.
The 8 GiB potential file-cache budget is an operator planning heuristic,
not a guarantee of instantaneous reclamation or a kernel memory limit.
"""
import base64
from decimal import Decimal
import hashlib
import re

GIB = 1024 ** 3
PROBES = (
    ("sysctl-cores", ("/usr/sbin/sysctl", "-n", "hw.logicalcpu")),
    ("sysctl-memory", ("/usr/sbin/sysctl", "-n", "hw.memsize")),
    ("pressure-1", ("/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level")),
    ("vm-stat-1", ("/usr/bin/vm_stat",)),
    ("ps-cpu-1", ("/bin/ps", "-A", "-o", "%cpu=")),
    ("pressure-2", ("/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level")),
    ("vm-stat-2", ("/usr/bin/vm_stat",)),
    ("ps-cpu-2", ("/bin/ps", "-A", "-o", "%cpu=")),
)
REQUIRED_VM = ("Pages free", "Pages inactive", "Pages speculative",
               "File-backed pages", "Pageouts", "Swapouts")


def need(value, reason):
    if not value:
        raise ValueError(reason)


def integer(text, label):
    need(re.fullmatch(r"[0-9]+\n?", text) is not None, label)
    value = int(text)
    need(value <= 2 ** 64 - 1, label + "_range")
    return value


def receipt(row, name, argv):
    need(type(row) is dict and row.get("name") == name, "probe_name")
    need(row.get("argv") == list(argv), "probe_argv")
    need(row.get("invocations") == 1 and type(row.get("invocations")) is int,
         "probe_invocations")
    need(row.get("complete") is True and row.get("failure") is None,
         "probe_incomplete")
    need(type(row.get("returncode")) is int and row["returncode"] == 0,
         "probe_exit")
    need(row.get("reaped") is True and row.get("new_session") is True,
         "probe_reap")
    cleanup = row.get("group_cleanup", {})
    need(cleanup.get("complete") is True and cleanup.get("explicit_ESRCH") is True,
         "probe_group_absence")
    for clock in ("monotonic", "wall"):
        for bound in ("started", "ended"):
            value = row.get(bound + "_" + clock + "_ns")
            need(type(value) is str and re.fullmatch(r"[0-9]+", value) is not None,
                 "probe_timestamp")
    start = int(row["started_monotonic_ns"])
    end = int(row["ended_monotonic_ns"])
    need(0 < start <= end and end - start < 5_000_000_000, "probe_timing")
    active = row.get("active_ended_monotonic_ns")
    need(type(active) is str and re.fullmatch(r"[0-9]+", active) is not None,
         "active_timestamp")
    need(start <= int(active) <= end and int(active)-start <= 3_000_000_000,
         "probe_active_timing")
    # Wall-clock changes do not determine elapsed time or sample ordering.
    elapsed = row.get("elapsed_seconds")
    need(type(elapsed) in (int, float) and Decimal(str(elapsed)).is_finite()
         and elapsed >= 0, "probe_elapsed")
    need(abs(Decimal(str(elapsed)) - Decimal(end-start) / Decimal(10**9))
         <= Decimal("0.000001"), "elapsed_join")
    outputs = {}
    for stream in ("stdout", "stderr"):
        need(row.get(stream + "_EOF") is True, "probe_EOF")
        b = base64.b64decode(row.get(stream + "_base64", ""), validate=True)
        need(len(b) < 65536 and row.get(stream + "_bytes") == len(b),
             "probe_stream_size")
        need(hashlib.sha256(b).hexdigest() == row.get(stream + "_sha256"),
             "probe_stream_hash")
        outputs[stream] = b.decode("ascii")
    need(outputs["stderr"] == "", "probe_stderr")
    return outputs["stdout"]


def vm_snapshot(text, memory):
    lines = text.splitlines()
    need(lines and re.fullmatch(
        r"Mach Virtual Memory Statistics: \(page size of ([0-9]+) bytes\)",
        lines[0]) is not None, "vm_header")
    page = int(re.search(r"([0-9]+) bytes", lines[0]).group(1))
    need(page in (4096, 16384), "vm_page_size")
    values = {}
    for label in REQUIRED_VM:
        hits = re.findall(r"^" + re.escape(label) + r":\s+([0-9]+)\.\s*$",
                          text, flags=re.MULTILINE)
        need(len(hits) == 1, "vm_field_" + label)
        values[label] = integer(hits[0], label)
    for label in REQUIRED_VM[:4]:
        need(values[label] * page <= memory, "vm_resident_bounds")
    free = values["Pages free"] * page
    file_backed = values["File-backed pages"] * page
    potential = free + file_backed
    need(potential <= memory, "vm_headroom_bounds")
    return {
        "page_bytes": page, "immediate_free_bytes": free,
        "pageable_file_backed_bytes": file_backed,
        "potential_headroom_bytes": potential,
        "legacy_free_inactive_speculative_bytes":
            (values["Pages free"] + values["Pages inactive"]
             + values["Pages speculative"]) * page,
        "pageouts": values["Pageouts"], "swapouts": values["Swapouts"],
    }


def cpu_cores(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    need(lines and all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", x) for x in lines),
         "cpu_shape")
    nums = [Decimal(x) for x in lines]
    need(all(x.is_finite() and x >= 0 for x in nums), "cpu_values")
    return sum(nums, Decimal(0)) / Decimal(100)


def evaluate(rows, disk_free_bytes):
    need(type(rows) is list and len(rows) == len(PROBES), "probe_population")
    values = {}
    for row, (name, argv) in zip(rows, PROBES):
        values[name] = receipt(row, name, argv)
    for previous, current in zip(rows, rows[1:]):
        need(int(previous["ended_monotonic_ns"])
             <= int(current["started_monotonic_ns"]), "probe_order")
    need(int(rows[5]["started_monotonic_ns"])
         - int(rows[4]["ended_monotonic_ns"]) >= 200_000_000,
         "sample_separation")
    cores = integer(values["sysctl-cores"], "logical_cores")
    memory = integer(values["sysctl-memory"], "hardware_memory")
    need(memory > 0, "hardware_memory")
    pressure = [integer(values["pressure-" + str(i)], "pressure") for i in (1, 2)]
    need(all(x in (1, 2, 4) for x in pressure), "unknown_pressure_dispatch_level")
    snapshots = [vm_snapshot(values["vm-stat-" + str(i)], memory) for i in (1, 2)]
    need(snapshots[0]["page_bytes"] == snapshots[1]["page_bytes"], "page_changed")
    for label in ("pageouts", "swapouts"):
        need(snapshots[1][label] >= snapshots[0][label], "counter_reset_" + label)
    need(type(disk_free_bytes) is int and disk_free_bytes >= 0, "disk")
    cpu = [cpu_cores(values["ps-cpu-" + str(i)]) for i in (1, 2)]
    checks = {
        "actual_14cores": cores == 14,
        "both_pressure_NORMAL_dispatch1": pressure == [1, 1],
        "potential_headroom_at_least8GiB":
            min(s["potential_headroom_bytes"] for s in snapshots) >= 8 * GIB,
        "no_observed_swapout_increase":
            snapshots[1]["swapouts"] == snapshots[0]["swapouts"],
        "no_observed_pageout_increase":
            snapshots[1]["pageouts"] == snapshots[0]["pageouts"],
        "CPU_with_selected6fits": max(cpu) + 6 <= cores,
        "disk_at_least128MiB": disk_free_bytes >= 128 * 1024 ** 2,
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "actual_logical_cores": cores, "hardware_memory_bytes": memory,
        "pressure_dispatch_levels": pressure, "snapshots": snapshots,
        "cpu_samples_cores": [str(v) for v in cpu],
        "sample_plus_roster_cores": str(max(cpu) + 6),
        "disk_free_bytes": disk_free_bytes,
        "workload_reservation_bytes": 512 * 1024 ** 2,
        "minimum_potential_cushion_after_workload_bytes":
            min(s["potential_headroom_bytes"] for s in snapshots) - 512 * 1024 ** 2,
        "interpretation": "Planning heuristic only. File-backed pages may need I/O or be reused. "
                          "No inactive, speculative, purgeable or compressed credit is added; "
                          "no instantaneous availability or future pressure guarantee.",
    }


def physical_closure(admissions, receipts):
    """Account for every admitted probe, including interrupted capture paths."""
    need(type(admissions) is list and type(receipts) is list, "closure_shape")
    names = [x.get("name") for x in admissions]
    need(all(type(n) is str for n in names) and len(names) == len(set(names)),
         "closure_admission_names")
    receipt_names = [x.get("name") for x in receipts]
    need(len(receipt_names) == len(set(receipt_names)), "closure_receipt_names")
    lookup = {x["name"]: x for x in receipts}
    physical = []
    capture = []
    for admission in admissions:
        no_spawn = admission.get("spawn_attempted") is False
        pid = admission.get("pid")
        returned = admission.get("spawn_returned") is True and type(pid) is int and pid > 0
        closed = no_spawn or (returned and admission.get("reaped") is True
                              and admission.get("group_absent") is True)
        physical.append(closed)
        receipt_row = lookup.get(admission["name"])
        capture.append(admission.get("receipt_recorded") is True and
                       type(receipt_row) is dict and
                       receipt_row.get("pid") == pid)
    no_extras = set(receipt_names) <= set(names)
    return {
        "admitted_probes": len(admissions),
        "spawn_attempts": sum(x.get("spawn_attempted") is True for x in admissions),
        "returned_process_handles": sum(x.get("spawn_returned") is True for x in admissions),
        "all_probe_groups_absent": all(physical),
        "complete_receipt_population": all(capture) and no_extras,
        "unresolved_physical_names": [n for n, ok in zip(names, physical) if not ok],
        "missing_or_mismatched_capture_names": [n for n, ok in zip(names, capture) if not ok],
    }
