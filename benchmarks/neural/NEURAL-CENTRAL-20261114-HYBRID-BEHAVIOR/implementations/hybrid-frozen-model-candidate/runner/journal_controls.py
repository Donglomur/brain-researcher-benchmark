"""Production create-journal regressions; invented receipts only, no Docker call.

The real owner writer and lifecycle begin/dispatch/acknowledge/inspect functions
compose here. Consistent changed-prefix receipts isolate the command-boundary
check from ordinary hash/custody failures.
"""
import hashlib
import time
import donor_checked_source as custody
import donor_create_lifecycle as lifecycle
import donor_process_closure as closer
from episode_owner_base import Owner
from consumer import ContractError


def run_journal_controls(source, output, plan):
    output.mkdir(mode=0o700); rows = []
    for mode in ("prefixed_acknowledgement", "changed_endpoint", "changed_config", "wrong_command"):
        directory = output / mode; directory.mkdir(mode=0o700)
        token = "invented-create-journal-" + mode; name = token + "-00"; cid = "a" * 64
        owner = Owner(custody, closer, directory, source, plan, plan["source_lock_sha256"],
                      time.monotonic() + 60, [], token, lifecycle=lifecycle, cli_group_mode="controller")
        owner.write("member-00.intent.json", {"name": name, "owner": token, "image": plan["image"]})
        record = lifecycle.begin(name); record["journal_base"] = "member-00"
        lifecycle.mark_dispatch(record, 1); owner.write("member-00.dispatch.json", record, 4096)
        prefix = list(plan["docker_prefix"])
        if mode == "changed_endpoint":
            prefix[prefix.index("--host") + 1] = "unix:///invented-wrong-endpoint.sock"
        if mode == "changed_config":
            prefix[prefix.index("--config") + 1] = "/invented-wrong-config"
        command = "inspect" if mode == "wrong_command" else "create"
        # The late 'create' operand makes a loose argv search incorrectly pass.
        argv = prefix + [command, "--name", name, plan["image"]]
        if mode == "wrong_command": argv.append("create")
        stdout = (cid + "\n").encode()
        custody.write_new(directory / "call-001.stdout", stdout, 1024)
        sp = {"name": "call-001.stdout", "bytes": len(stdout), "sha256": hashlib.sha256(stdout).hexdigest()}
        actual = {"argv": argv, "issue": None, "stdout_eof": True, "stderr_eof": True,
                  "closure": {"exit_code": 0, "reaped": True, "errors": [], "signals_sent": []}}
        cp = owner.write("call-001.result.json", actual, 8192)
        lifecycle.acknowledge(record, cid, cp, sp); owner.write("member-00.creation.json", record, 4096)
        checked = lifecycle.inspect_journals(custody, directory, token, 1, plan["image"], plan["docker_prefix"])
        positive = mode == "prefixed_acknowledgement"
        if positive:
            if not checked["all_dispatch_completions_known"] or checked["errors"] or checked["rows"][0]["cid"] != cid:
                raise ContractError("production exact prefixed create acknowledgement refused")
        else:
            if checked["all_dispatch_completions_known"] or len(checked["errors"]) != 1 or checked["rows"][0]["state"] != "journal_or_dispatch_unknown":
                raise ContractError("changed production create prefix/command accepted")
            if checked["errors"][0]["reason"] != "acknowledgement exact Docker prefix and create command boundary":
                raise ContractError("production prefix control failed at unrelated stage")
        owner.write("JOURNAL_CONTROL_RESULT.json", {"mode": mode, "pass": True, "inspection": checked,
            "invented_receipts": True, "docker_calls": owner.calls})
        if owner.calls != 0: raise ContractError("journal control must not dispatch Docker")
        rows.append({"name": "production_journal_" + mode, "pass": True, "result": str(directory / "JOURNAL_CONTROL_RESULT.json")})
    return rows
