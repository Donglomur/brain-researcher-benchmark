"""Create-dispatch provenance and conservative durable closure semantics.

An empty name/namespace query is only a point-in-time observation. It cannot
settle a daemon mutation whose completion response was lost or interrupted.
No CLI error text is interpreted as a conclusive daemon-side rejection.
"""


def begin(name):
    return {"name": name, "state": "never_dispatched", "dispatch_may_have_occurred": False,
            "cid": None, "resolution_basis": None}


def mark_dispatch(record, sequence):
    if record["state"] != "never_dispatched":
        raise ValueError("one create dispatch only")
    record.update(state="dispatched_completion_unresolved", dispatch_may_have_occurred=True,
                  call_sequence=sequence, resolution_basis=None)


def reject_before_dispatch(record, reason):
    if record["state"] != "never_dispatched":
        raise ValueError("cannot rewrite a possibly dispatched mutation as rejected")
    record.update(state="definitively_rejected_before_dispatch", resolution_basis="local_pre_dispatch_admission",
                  reason=reason[:1024])


def acknowledge(record, cid, call_result, stdout):
    if record["state"] != "dispatched_completion_unresolved" or len(cid) != 64 or \
            not all(x in "0123456789abcdef" for x in cid):
        raise ValueError("one complete acknowledged create identity")
    record.update(state="acknowledged", cid=cid, resolution_basis="natural_complete_create_cli_success",
                  call_result=call_result, stdout=stdout)


def closure(record, observed_absent, errors):
    settled = record["state"] in ("never_dispatched", "definitively_rejected_before_dispatch", "acknowledged")
    complete = settled and observed_absent and not errors
    return {"create_state": record["state"], "observed_absent_at_probe": observed_absent,
            "lifecycle_complete": complete, "absent": complete,
            "dispatch_completion_known": settled,
            "quarantine_required": not settled,
            "lifecycle_status": "SETTLED_AND_ABSENCE_OBSERVED" if complete else
                "UNRESOLVED_CREATE_QUARANTINED" if not settled else "CLOSURE_NOT_ESTABLISHED"}


def inspect_journals(cust, root, token, count, image, docker_prefix):
    """Read only finite owned journals after controller group closure.

    Missing/partial/mismatched evidence cannot erase a prepared dispatch. An
    acknowledged resolution binds the complete natural CLI result and stdout.
    No dispatch journal is interpreted as never-dispatched only because trusted
    source writes that durable journal before Popen can dispatch a create.
    """
    cust.need(type(docker_prefix) is list and docker_prefix and
              all(type(x) is str and x for x in docker_prefix), "exact admitted Docker prefix")
    read_bytes, rows, errors = 0, [], []
    def read(path, cap, descriptor=None):
        nonlocal read_bytes
        cust.ordinary_path(path)
        n = path.lstat().st_size
        cust.need(n <= cap and read_bytes+n <= 1048576, "complete finite dispatch journal read allowance")
        if descriptor is None:
            import hashlib
            # Stable, ordinary, bounded original output. The computed pin is
            # retained, not substituted for the controller source trust anchor.
            import os, stat
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = os.fstat(fd)
                cust.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == n,
                          "ordinary complete dispatch journal")
                data = bytearray()
                while len(data) < n:
                    part = os.read(fd, min(65536, n-len(data))); cust.need(part, "journal EOF")
                    data.extend(part); read_bytes += len(part)
                cust.need(not os.read(fd, 1) and cust.stamp(before) == cust.stamp(os.fstat(fd)), "journal stable/tail")
                return bytes(data)
            finally:
                os.close(fd)
        # Reserve the entire selected extent before a checked read can fail.
        # A bad hash must not erase the bytes already consumed by that attempt.
        read_bytes += n
        return cust.exact(path, descriptor, cap)
    for index in range(count):
        name = token+"-%02d" % index
        base = "member-%02d" % index
        intent, dispatch, resolution = (root/(base+s) for s in (".intent.json", ".dispatch.json", ".creation.json"))
        row = begin(name)
        try:
            for p in (intent, dispatch, resolution):
                cust.ordinary_path(p)
            if not intent.exists():
                cust.need(not dispatch.exists() and not resolution.exists(), "orphan creation journal")
                rows.append(row); continue
            declared = cust.strict(read(intent, 8192))
            cust.need(declared["name"] == name and declared["owner"] == token and declared["image"] == image,
                      "exact predeclared creation identity")
            if dispatch.exists():
                d = cust.strict(read(dispatch, 4096))
                cust.need(d["name"] == name and d["state"] == "dispatched_completion_unresolved" and
                          d["dispatch_may_have_occurred"] is True, "durable pre-dispatch uncertainty journal")
                row = d
            if resolution.exists():
                final = cust.strict(read(resolution, 4096))
                cust.need(final["name"] == name, "same resolved create name")
                if final["state"] == "definitively_rejected_before_dispatch":
                    cust.need(not dispatch.exists() and final["dispatch_may_have_occurred"] is False and
                        final["resolution_basis"] == "local_pre_dispatch_admission", "definitive rejection only before dispatch")
                else:
                    cust.need(dispatch.exists() and final["state"] == "acknowledged" and
                        final["call_sequence"] == row["call_sequence"] and
                        final["resolution_basis"] == "natural_complete_create_cli_success", "resolved acknowledged dispatch")
                    cp, sp = final["call_result"], final["stdout"]
                    cust.need(cp["name"] == "call-%03d.result.json" % final["call_sequence"] and
                        sp["name"] == "call-%03d.stdout" % final["call_sequence"], "exact complete create result operands")
                    actual = cust.strict(read(root/cp["name"], 8192, cp))
                    out = read(root/sp["name"], 1024, sp)
                    c = actual["closure"]
                    cust.need(actual["issue"] is None and c["exit_code"] == 0 and c["reaped"] and
                        not c["errors"] and not c["signals_sent"] and actual["stdout_eof"] is True and
                        actual["stderr_eof"] is True and out.decode().strip() == final["cid"],
                        "complete acknowledged create response")
                    argv = actual["argv"]; boundary = len(docker_prefix)
                    cust.need(type(argv) is list and argv[:boundary] == docker_prefix and
                        len(argv) > boundary and argv[boundary] == "create",
                        "acknowledgement exact Docker prefix and create command boundary")
                    command = argv[boundary:]
                    cust.need(command.count("--name") == 1 and
                        command[command.index("--name")+1] == name,
                        "acknowledgement belongs to selected create command")
                row = final
            rows.append(row)
        except BaseException as exc:
            rows.append({"name": name, "state": "journal_or_dispatch_unknown", "dispatch_may_have_occurred": True})
            errors.append({"name": name, "type": type(exc).__name__, "reason": str(exc)[:512]})
    unknown = [r["name"] for r in rows if r["state"] not in
               ("never_dispatched", "definitively_rejected_before_dispatch", "acknowledged")]
    return {"rows": rows, "managed_journal_read_bytes": read_bytes, "errors": errors,
            "unresolved_names": unknown, "all_dispatch_completions_known": not errors and not unknown}
