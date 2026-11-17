"""Actual pre-data F source authoring; compose as nlb.predata_authoring.

Only model exchanges and source-syntax workers are dispatched.  This module
does not create independent reviews, execute submitted programs, or read data.
"""

import base64
import copy
import math
import time

from .contracts import (Budget, Custody, Store, canonical, closed, descriptor,
                        diagnostic, digest, integer, need, parse, relative)
from .programme import P4H, allowed_references, expected_groups, group_id
from .authoring_syntax import POLICY, SOURCE_CAP, DIAGNOSTIC_CAP
from .openai_gateway import OpenAIExecutor, OpenAIProcessModel
from .openai_protocol import assistant_message


REQUEST_CAP = 8 * 2**20
CONTEXT_CAP = 4 * 2**20
SOURCE_MEMBER_CAP = 32 * 2**20
RECORD_CAP = 16 * 2**20
TERMINAL_CAP = 8 * 2**20
MODEL_KEYS = {"runtime", "model_identity", "configuration", "prompt",
              "tokenizer", "service_qualification"}
CONTEXT_ROLES = {"licensed_primary", "method_description", "schema", "tool_API",
                 "exposure_disclosure", "curated_author_code", "code_license"}
PROMPT_KEYS = {"schema", "system", "neutral_system", "authoring_instruction",
               "neutral_authoring_instruction", "investigation_instruction",
               "neutral_investigation_instruction"}

PROJECTIONS = {
    "intact": "Full selected training/query fields in the source schema.",
    "within_condition_shuffle": "The query observed-input pool is already transformed; only the delivered pool is available. No donor map or intact copy is provided. Training-only state may be reused only with its original lineage; query-dependent state must use the delivered pool.",
    "context_only": "Training permits train_counts_heldout, train_trial_ids, heldout_unit_ids, train_condition_ids, bin_left_edges_ms. Query permits eval_trial_ids, heldout_unit_ids, eval_condition_ids, bin_left_edges_ms, eval_valid_mask. No observed-input arrays or states fitted from them.",
    "training_rate_only": "Training permits per-withheld-unit totals, total bin opportunities and heldout_unit_ids. Query permits eval_trial_ids, heldout_unit_ids, bin_left_edges_ms, eval_valid_mask. No trial-resolved training counts, condition IDs or observed-input arrays/states.",
    "metadata_neutral": "Full selected training/query fields in the source schema.",
}


def _group(group):
    rows = {group_id(row): row for row in expected_groups()}
    need(group in rows, "complete registered group identity")
    return rows[group]


def render_context_messages(context_store, prompt_store, *, public_context,
                            prompt, group, context_programme):
    """Render the same authenticated source context for F and I.

    Caller supplies original budgeted Stores rooted at the selected context and
    prompt stores.  The returned messages contain no empirical input reads.
    PDF bytes are inline original files, never a lossy transcription or URL.
    """
    row = _group(group)
    descriptor(public_context)
    descriptor(prompt)
    context = context_store.json(public_context, CONTEXT_CAP)
    closed(context, {"schema", "programme", "view", "members",
                     "cross_task_exposure", "publication_permission"})
    need(context["schema"] == "NLB017_private_context_v1" and
         context["programme"] == context_programme and
         context["view"] == row["code_view"] and
         context["publication_permission"] is False,
         "exact private pre-existing study context; no future campaign identity")
    prompt_doc = prompt_store.json(prompt, 2**20)
    closed(prompt_doc, PROMPT_KEYS)
    need(prompt_doc["schema"] == "NLB017_selected_prompt_v1", "selected prompt")
    for key in PROMPT_KEYS - {"schema"}:
        need(type(prompt_doc[key]) is str and prompt_doc[key].strip(),
             "explicit complete prompt strings")
    neutral = row["condition"] == "metadata_neutral"
    system_key = "neutral_system" if neutral else "system"
    instruction = "authoring_instruction" if row["mode"] == "F" else "investigation_instruction"
    if neutral:
        instruction = "neutral_" + instruction
    need(type(context["members"]) is list and context["members"],
         "complete nonempty source context")
    content = [{"type": "input_text", "text": prompt_doc[instruction]}]
    # Existing metadata-neutral contract keeps papers/code and source identities;
    # only selected task framing changes.  It is not anonymized biology.
    binding = {"schema": "NLB017_source_prompt_binding_v1", "group": group,
               "mode": row["mode"], "code_view": row["code_view"],
               "seed": row["agent_seed"], "public_context": public_context,
               "prompt": prompt, "context_programme": context_programme,
               "framing": "neutral" if neutral else "ordinary", "members": []}
    content.append({"type": "input_text", "text": canonical({
        "code_view": row["code_view"], "seed": row["agent_seed"],
        "context_programme": context_programme,
        "cross_task_exposure": context["cross_task_exposure"],
        "input_projection": PROJECTIONS[row["condition"]],
        "available_reference_handles": list(allowed_references(row["condition"])),
    }).decode("utf-8")})
    names = set()
    roles = set()
    allowed = CONTEXT_ROLES if row["code_view"] == "B" else CONTEXT_ROLES - {
        "curated_author_code", "code_license"}
    for member in context["members"]:
        closed(member, {"name", "role", "source", "copied", "provenance"})
        relative(member["name"])
        need(member["name"] not in names and member["role"] in allowed,
             "unique source-only member admitted for this A/B view")
        names.add(member["name"])
        roles.add(member["role"])
        for key in ("source", "copied"):
            descriptor(member[key])
        need(member["source"]["bytes"] == member["copied"]["bytes"] and
             member["source"]["sha256"] == member["copied"]["sha256"],
             "unchanged source copy")
        raw = context_store.read(member["copied"], SOURCE_MEMBER_CAP)
        content.append({"type": "input_text", "text": canonical({
            "source_member": member}).decode("utf-8")})
        if raw.startswith(b"%PDF-"):
            # This is a transport alias only. Original name, source/copy pins and
            # provenance stay in the preceding exact metadata and binding.
            filename = "source-%d-%s.pdf" % (len(binding["members"]), member["copied"]["sha256"])
            content.append({"type": "input_file", "filename": filename,
                            "file_data": "data:application/pdf;base64," +
                            base64.b64encode(raw).decode("ascii")})
            encoding = "original_inline_pdf"
        else:
            filename = None
            content.append({"type": "input_text", "text": raw.decode("utf-8")})
            encoding = "exact_utf8"
        binding["members"].append({**member, "rendering": encoding,
                                   "transport_filename": filename})
    need({"licensed_primary", "exposure_disclosure"} <= roles,
         "full paper and exposure disclosure retained")
    if row["code_view"] == "B":
        need("curated_author_code" in roles, "actual complete paper-plus-code view")
    messages = [{"role": "system", "content": prompt_doc[system_key]},
                {"role": "user", "content": content}]
    need(len(canonical(messages)) <= REQUEST_CAP, "complete source prompt fits original request cap")
    binding["messages_sha256"] = digest(canonical(messages))
    return {"messages": messages, "binding": binding}


def _same_budget(actual, expected):
    need(actual == expected, "actual original counters equal sealed publication projection")


def _publication(store, record, terminal, prefix):
    """Seal original counters including the actual two final durable writes.

    Terminal is published last.  The record refers to its precomputed exact
    bytes.  A failed write is never replaced, rolled back or called complete.
    """
    base = store.budget.snapshot()
    need(not base["stops"] and not any(base["held"].values()) and
         base["child_accounting"]["unknown_or_unresolved"] == 0,
         "original processes and costs completely joined before publication")
    sizes = (0, 0)
    for _ in range(64):
        projected = copy.deepcopy(base)
        for field in ("used", "reserved"):
            projected[field]["write_bytes"] += sum(sizes)
            projected[field]["created_files"] += 2
        terminal["resources"] = projected
        terminal_raw = canonical(terminal)
        terminal_pin = {"path": prefix + "/TERMINAL.json", "bytes": len(terminal_raw),
                        "sha256": digest(terminal_raw)}
        record["original_terminal"] = terminal_pin
        record["resource_snapshot"] = projected
        record_raw = canonical(record)
        current = (len(record_raw), len(terminal_raw))
        if current == sizes:
            break
        sizes = current
    else:
        raise ValueError("bounded final publication accounting did not converge")
    need(len(record_raw) <= RECORD_CAP and len(terminal_raw) <= TERMINAL_CAP,
         "original consumer record/terminal caps")
    for key in Budget.KEYS:
        need(max(projected["used"][key], projected["reserved"][key]) <= base["limits"][key],
             "final original publication fits remaining resource envelope")
    record_pin = store.write(prefix + "/RECORD.json", record_raw, RECORD_CAP)
    actual_terminal = store.write(terminal_pin["path"], terminal_raw, TERMINAL_CAP)
    need(actual_terminal == terminal_pin, "exact terminal bytes published last")
    _same_budget(store.budget.snapshot(), projected)
    return record_pin, terminal_pin, projected


def _checker_template(executor, job, selection, group):
    """Admit every static checker operand before any model dispatch."""
    slot = executor.selected[job]
    need(slot["stage"] == "S01" and slot["role"] == "source_syntax" and
         slot["parent_group"] == group, "same original source-checking slot")
    policy = closed(slot["dynamic_input_policy"], {"schema", "manifest_path", "authority"})
    need(policy["schema"] == "NLB017_F_checker_dynamic_input_v1", "fixed checker-only binder")
    descriptor(policy["authority"])
    need(policy["authority"] in list(executor.authority.input_pins), "selected original authority input")
    relative(policy["manifest_path"])
    need(policy["manifest_path"].startswith(selection["groups"][group]["output_prefix"] + "/"),
         "checker input manifest belongs to this original group")
    sandbox = slot["sandbox"]
    need(sandbox["runtime_profile"] == "reference_producer", "source checker nonparticipant profile")
    argv = slot["argv"]
    need(type(argv) is list and len(argv) == 4 and type(argv[0]) is str and
         argv[0].startswith("/") and argv[1:] == ["-B", "-m", "nlb.authoring_syntax"],
         "selected fixed source checker executable")
    authority_guest = "/inputs/" + policy["authority"]["path"]
    need(any(m["guest"] == authority_guest and m["role"] == "operator_authority" and
             m["access"] == "ro" for m in sandbox["mounts"]), "original authority mount")
    need(all(m["role"] in {"engine_source", "operator_authority"} and m["access"] == "ro"
             or m["guest"] == "/output" and m["access"] == "rw"
             for m in sandbox["mounts"]), "checker has only source, authority and its output")
    need(any(m["role"] == "engine_source" for m in sandbox["mounts"]),
         "actual source checker engine mount")
    return slot, policy


def _checker_binding(executor, job, candidate, selection, group, store, seen):
    """Bind only this immediately produced source into its original check slot."""
    need(job not in seen and job not in executor.attempt_custodies and
         job not in executor.originals, "one original checker input binding")
    seen.add(job)
    slot, policy = _checker_template(executor, job, selection, group)
    sandbox = slot["sandbox"]
    manifest = {"schema": "NLB017_input_mount_set_v1", "programme": selection["context_programme"],
                "job": job, "files": [{"role": "authoring_source", "source": candidate}]}
    pin = store.write(policy["manifest_path"], canonical(manifest), CONTEXT_CAP)
    mount = {"host": str(store.path(candidate["path"])), "guest": "/inputs/" + candidate["path"],
             "access": "ro", "role": "authoring_source", "manifest": pin,
             "member": candidate["path"]}
    need(all(m["guest"] != mount["guest"] for m in sandbox["mounts"]), "fresh exact source mount")
    original = copy.deepcopy(slot)
    selected = copy.deepcopy(slot)
    selected["input_manifests"].append(pin)
    selected["sandbox"]["mounts"].append(mount)
    executor.selected[job] = selected
    binding = {"programme": selection["context_programme"], "job": job,
               "role": "source_syntax", "source": selected["source"],
               "inputs": selected["input_manifests"]}
    payload = {"schema": "NLB017_worker_request_v2", "job": job,
               "source": selected["source"], "role": "source_syntax", "stage": "S01",
               "body": {"candidate_source": candidate, "syntax_policy": selection["syntax_policy"]},
               "declared_inputs": [candidate], "input_root": "/inputs", "output_root": "/output",
               "deadline": store.budget.deadline, "authority": policy["authority"],
               "expected_root_source": selection["root_source"], "bindings": binding}
    return payload, {"original_slot": original, "bound_slot": copy.deepcopy(selected),
                     "input_manifest": pin, "candidate_source": candidate}


def _diagnostic(value, candidate, policy):
    closed(value, {"schema", "candidate_source", "syntax_policy", "valid", "diagnostic",
                   "candidate_imported", "candidate_executed", "empirical_inputs_read"})
    need(value["schema"] == "NLB017_source_syntax_diagnostic_v1" and
         value["candidate_source"] == candidate and value["syntax_policy"] == policy and
         type(value["valid"]) is bool and value["candidate_imported"] is False and
         value["candidate_executed"] is False and value["empirical_inputs_read"] is False,
         "exact original syntax diagnostic")
    if value["valid"]:
        need(value["diagnostic"] is None, "valid syntax has no parser failure")
    else:
        d = closed(value["diagnostic"], {"type", "message", "lineno", "offset", "end_lineno", "end_offset", "text"})
        need(d["type"] == "SyntaxError" and type(d["message"]) is str, "actual parser diagnostic")
        need(d["text"] is None or type(d["text"]) is str, "original parser source line")
        for key in ("lineno", "offset", "end_lineno", "end_offset"):
            need(d[key] is None or type(d[key]) is int, "original parser position")
    return value


def _admit(selection, authority, executor, outer_store):
    closed(selection, {"schema", "root_source", "driver_source", "model", "clock_domain",
                       "clock_review", "context_roots", "code_views", "context_programme",
                       "syntax_policy", "groups", "outer_output_prefix"})
    need(selection["schema"] == "NLB017_F_authoring_production_selection_v1",
         "fixed complete pre-data authoring selection")
    need(type(executor) is OpenAIExecutor and executor.authority is authority and
         executor.source == selection["root_source"] and
         authority.root_source == selection["root_source"] and
         executor.store.root == outer_store.root,
         "actual selected model-aware Executor and original source/root authority")
    authority.check("S01", "model_exchange")
    authority.check("S01", "source_syntax")
    closed(selection["model"], MODEL_KEYS)
    closed(selection["code_views"], {"A", "B"})
    closed(selection["context_roots"], {"A", "B"})
    for pin in [selection["driver_source"], selection["clock_review"],
                *selection["model"].values(), *selection["code_views"].values()]:
        descriptor(pin)
        need(pin in list(authority.input_pins), "genuine selected source/model/context input")
    need(type(selection["clock_domain"]) is str and selection["clock_domain"].strip() and
         type(selection["context_programme"]) is str and selection["context_programme"].strip(),
         "explicit current monotonic domain and prior context study identity")
    closed(selection["syntax_policy"], {"schema", "python_version"})
    need(selection["syntax_policy"]["schema"] == POLICY and
         type(selection["syntax_policy"]["python_version"]) is str,
         "explicit selected source-parser identity")
    expected = {group_id(row): row for row in expected_groups() if row["mode"] == "F"}
    closed(selection["groups"], expected)
    relative(selection["outer_output_prefix"])
    jobs, prefixes = set(), set()
    for gid, item in selection["groups"].items():
        closed(item, {"seed", "code_view", "public_context", "limits", "wall_seconds",
                      "exchange_slots", "checker_slots", "exchange_token_caps", "output_prefix"})
        original = expected[gid]
        integer(item["seed"], 1, 5)
        need(item["seed"] == original["agent_seed"] and
             item["code_view"] == original["code_view"] and
             item["public_context"] == selection["code_views"][original["code_view"]],
             "exact full condition/code-view/seed roster")
        closed(item["limits"], Budget.KEYS)
        need(item["limits"]["cpu_seconds"] == P4H["cpu_seconds"] and
             item["limits"]["model_tokens"] == P4H["model_tokens"] and
             item["wall_seconds"] == P4H["wall_seconds"], "unchanged full matched F envelope")
        for key, value in item["limits"].items():
            if key == "cpu_seconds":
                need(type(value) in (int, float) and math.isfinite(value) and value > 0,
                     "explicit finite CPU envelope")
            else:
                integer(value, 1)
        models, checks, caps = (item["exchange_slots"], item["checker_slots"], item["exchange_token_caps"])
        need(type(models) is list and type(checks) is list and type(caps) is list and
             1 <= len(models) <= 1024 and len(models) == len(checks) == len(caps),
             "operator-selected finite iterative authoring slots; no default turn count")
        relative(item["output_prefix"])
        need(item["output_prefix"] not in prefixes and
             item["output_prefix"].startswith(selection["outer_output_prefix"] + "/"),
             "separate original group publication prefix")
        prefixes.add(item["output_prefix"])
        for index, (model_job, checker_job, cap) in enumerate(zip(models, checks, caps)):
            integer(cap, 1, P4H["model_tokens"])
            for job, role in ((model_job, "model_exchange"), (checker_job, "source_syntax")):
                need(type(job) is str and job not in jobs and job in executor.selected,
                     "unique actual precommitted invocation slot")
                jobs.add(job)
                slot = executor.selected[job]
                need(slot["stage"] == "S01" and slot["role"] == role and
                     slot["parent_group"] == gid, "same original group source-only worker")
                descriptor(slot["source"])
                if role == "source_syntax":
                    _checker_template(executor, job, selection, gid)
            need(executor.selected[model_job]["source"] == executor.selected[models[0]]["source"],
                 "one exact model source producer through original group")
    need(jobs == set(executor.selected) and not executor.originals and
         not executor.attempt_custodies and not executor.model_attempts,
         "fresh complete pre-data executor, no unrelated or replayed jobs")
    need(all(not a.startswith(b + "/") for a in prefixes for b in prefixes if a != b),
         "no nested group output alias")
    return expected


def _produce_group(selection, gid, row, *, authority, executor, outer_store,
                   clock_pin, bound_checks, owner):
    item = selection["groups"][gid]
    original_started = time.monotonic()
    deadline = min(original_started + item["wall_seconds"], outer_store.budget.deadline)
    budget = Budget(item["limits"], deadline, parent=outer_store.budget, custody=owner)
    store = Store(outer_store.root, budget, owner)
    owner.facts["original_started"] = original_started
    owner.facts["original_deadline"] = deadline
    owner.original_budget = budget
    context_store = Store(selection["context_roots"][item["code_view"]], budget, owner)
    rendered = render_context_messages(context_store, store,
        public_context=item["public_context"], prompt=selection["model"]["prompt"],
        group=gid, context_programme=selection["context_programme"])
    prefix = item["output_prefix"]
    initial = store.write(prefix + "/INITIAL_MESSAGES.json", canonical(rendered), REQUEST_CAP)
    model_spec = selection["model"]
    plan = {"schema": "NLB017_pre_exposure_F_authoring_plan_v1", "group": gid,
            "seed": item["seed"], "model": model_spec["model_identity"],
            "configuration": model_spec["configuration"], "prompt": model_spec["prompt"],
            "tokenizer": model_spec["tokenizer"], "runtime": model_spec["runtime"],
            "service_qualification": model_spec["service_qualification"],
            "code_view": item["code_view"], "public_context": item["public_context"],
            "feedback_policy": "source_syntax_static_schema_only_no_empirical_execution",
            "clock_identity": clock_pin, "created_before_activity": True}
    plan_pin = store.write(prefix + "/PLAN.json", canonical(plan), CONTEXT_CAP)
    model = OpenAIProcessModel(executor, model_spec["model_identity"],
                              model_spec["configuration"], model_spec["prompt"],
                              model_spec["tokenizer"], model_spec["service_qualification"])
    messages = rendered["messages"]
    exchanges, feedback, rounds, process_pins = [], [], [], []
    owner.facts.update(initial_messages=initial, plan=plan_pin, rounds=rounds)
    captured = None
    for index, (job, check_job, requested) in enumerate(zip(
            item["exchange_slots"], item["checker_slots"], item["exchange_token_caps"])):
        budget.admit()
        remaining = min(requested, budget.available("model_tokens"))
        integer(remaining, 1)
        request_preview = {"schema": "NLB017_actual_model_request_v1",
                           "model": model_spec["model_identity"],
                           "configuration": model_spec["configuration"],
                           "prompt": model_spec["prompt"], "tokenizer": model_spec["tokenizer"],
                           "seed": item["seed"], "messages": messages,
                           "max_remaining_total_tokens": remaining}
        need(len(canonical(request_preview)) <= REQUEST_CAP,
             "complete original conversation fits consumer cap; no truncation")
        envelope_bound = {"schema": "NLB017_executor_worker_envelope_v2", "job": job,
                          "source": executor.selected[job]["source"],
                          "io_limits": {key: 2**63 - 1 for key in Budget.IO_KEYS},
                          "receipt_limits": executor.selected[job]["worker_receipt_limits"],
                          "deadline": deadline, "payload": request_preview}
        need(len(canonical(envelope_bound)) <= REQUEST_CAP,
             "complete original model stdin fits unchanged consumer cap")
        round_state = {"index": index, "model_job": job, "checker_job": check_job,
                       "state": "model_attempt", "candidate_source": None, "diagnostic": None}
        rounds.append(round_state)
        reply, receipt = model.exchange(job, "S01", messages, item["seed"], budget, remaining)
        attempt = executor.model_attempts[job]
        original = executor.originals[job]
        need(attempt.original is original and attempt.original_request == request_preview,
             "same actual model request and caller-owned process")
        request_pin = store.write(prefix + "/request-%04d.json" % index,
                                  canonical(attempt.original_request), REQUEST_CAP)
        exchange_row = {"index": index, "request": request_pin,
                        "exchange": receipt["exchange"], "process": receipt["original_process"],
                        "worker_result": original.persistence["worker_result"]}
        exchanges.append(exchange_row)
        process_pins.append(exchange_row["process"])
        round_state["exchange"] = exchange_row
        need(type(reply["content"]) is str and reply["tool_calls"] == [] and
             attempt.original_exchange["assistant"]["content"] == reply["content"] and
             attempt.original_exchange["assistant"]["tool_calls"] == [],
             "actual complete source response; no model-selected tool execution")
        raw = reply["content"].encode("utf-8")
        need(len(raw) <= SOURCE_CAP, "complete final response source cap; no extraction or rewriting")
        candidate = store.write(prefix + "/candidate-%04d.py" % index, raw, SOURCE_CAP)
        round_state["candidate_source"] = candidate
        payload, original_binding = _checker_binding(executor, check_job, candidate,
            selection, gid, store, bound_checks)
        binding_pin = store.write(prefix + "/checker-binding-%04d.json" % index,
                                  canonical(original_binding), CONTEXT_CAP)
        round_state["checker_binding"] = binding_pin
        round_state["state"] = "syntax_attempt"
        observed = executor.invoke(check_job, "S01", "source_syntax", payload, budget)
        need(observed is executor.originals[check_job], "same actual syntax worker observation")
        owner.fail(None, "original_source_syntax_worker", observed.custody)
        owner.raise_if_failed()
        result = executor.product(observed)
        closed(result["products"], {"diagnostic", "trace"})
        value = _diagnostic(store.json(result["products"]["diagnostic"], DIAGNOSTIC_CAP),
                            candidate, selection["syntax_policy"])
        check_row = {"kind": "source_syntax", "process": observed.persistence["process"],
                     "source": executor.selected[check_job]["source"]}
        feedback.append(check_row)
        process_pins.append(check_row["process"])
        round_state.update(diagnostic=result["products"]["diagnostic"],
                           worker_result=result["original_worker_result"],
                           state="valid_syntax" if value["valid"] else "invalid_syntax")
        if value["valid"]:
            captured = candidate
            break
        # Replay the complete original assistant items through the fixed gateway
        # helper, then the actual source-only diagnostic.  No empirical feedback.
        messages = messages + [assistant_message(reply), {"role": "user", "content": canonical({
            "schema": "NLB017_original_source_syntax_feedback_v1",
            "diagnostic": value, "original_process": check_row["process"],
            "instruction": "Revise the complete source using this syntax diagnostic. Return only the complete Python source; no tools.",
        }).decode("utf-8")}]
    need(captured is not None, "all explicitly selected authoring rounds exhausted without valid syntax")
    # The consumer orders all model processes, then all feedback processes.
    process_pins = [row["process"] for row in exchanges] + [row["process"] for row in feedback]
    source_producer = executor.selected[item["exchange_slots"][0]]["source"]
    record = {"schema": "NLB017_original_F_authoring_v1", "group": gid,
              "plan": plan_pin, "clock_identity": clock_pin, "captured_source": captured,
              "model_exchanges": exchanges, "engineering_feedback": feedback,
              "original_terminal": None, "resource_snapshot": None,
              "original_started": original_started, "original_deadline": deadline,
              "source_producer": source_producer}
    terminal = {"schema": "NLB017_original_F_authoring_terminal_v1", "group": gid,
                "plan": plan_pin, "captured_source": captured, "processes": process_pins,
                "original_started": original_started, "original_deadline": deadline,
                "resources": None, "complete": True, "first_error": None,
                "unresolved": [], "closed_before_empirical_activity": True}
    # No group-specific write may follow these two accounted publications.
    record_pin, terminal_pin, snapshot = _publication(store, record, terminal, prefix)
    owner.complete = True
    return {"state": "pending_independent_review", "record": record_pin,
            "plan": plan_pin, "clock_identity": clock_pin, "captured_source": captured,
            "original_terminal": terminal_pin, "initial_messages": initial,
            "original_started": original_started, "original_deadline": deadline,
            "resource_snapshot": snapshot, "rounds": rounds,
            "independent_review": None, "scientific_qualification": False}


def produce_all(selection, *, authority, executor, outer_store):
    """Produce all 50 F sources, then stop for genuine independent reviews.

    This is an executable future entry, not a build-time model invocation.
    Required output directories, exact jobs/rootfs/source pins and both original
    resource pools are supplied by the concrete coordinator.  No defaults or
    automatic fresh-budget retry exist.  Returned failure rows keep full roster.
    """
    expected = _admit(selection, authority, executor, outer_store)
    outer_store.budget.admit()
    prefix = selection["outer_output_prefix"]
    begin = outer_store.write(prefix + "/BEGIN.json", canonical({
        "schema": "NLB017_original_F_authoring_begin_v1", "selection": selection,
        "source": selection["driver_source"], "started": time.monotonic(),
        "full_group_order": list(expected), "no_empirical_stage_selected": True,
    }), RECORD_CAP)
    # Read the genuine supplied currentness review; never manufacture its verdict.
    outer_store.read(selection["clock_review"], 2**20)
    clock_pin = outer_store.write(prefix + "/CLOCK.json", canonical({
        "schema": "NLB017_current_authoring_clock_domain_v1",
        "monotonic_domain": selection["clock_domain"],
        "current_operator_source": selection["root_source"],
        "independent_currentness_review": selection["clock_review"],
    }), 2**20)
    rows = {gid: {"state": "not_attempted", "independent_review": None,
                  "scientific_qualification": False} for gid in expected}
    bound_checks = set()
    failure = None
    for gid, row in expected.items():
        owner = Custody("original_F_authoring:" + gid)
        outer_store.custody.resources.append(owner)
        try:
            rows[gid] = _produce_group(selection, gid, row, authority=authority,
                executor=executor, outer_store=outer_store, clock_pin=clock_pin,
                bound_checks=bound_checks, owner=owner)
        except BaseException as original:
            owner.capture(original, "original_F_authoring")
            original_budget = getattr(owner, "original_budget", None)
            if original_budget is not None:
                original_budget.stop("failed original F authoring " + gid)
            outer_store.budget.stop("failed original F authoring " + gid)
            rows[gid] = {"state": "failed", "first_error": diagnostic(owner.first_error),
                         "custody": owner.snapshot(), "independent_review": None,
                         "scientific_qualification": False}
            failure = owner
            break
    result = {"schema": "NLB017_original_F_authoring_pending_v1", "begin": begin,
              "clock_identity": clock_pin, "group_order": list(expected), "groups": rows,
              "status": "pending_independent_reviews" if failure is None else "incomplete_original_failure",
              "complete_scope": failure is None, "reviews_produced": False,
              "scientific_qualification": False, "all_empirical_stages_unentered": True}
    # This is outer preparation metadata, explicitly charged outside sealed group
    # snapshots.  A failed write propagates with originals still owned in custody.
    if failure is not None:
        outer_store.custody.fail(None, "original_F_authoring", failure)
    publication = Custody("original_F_authoring_pending_publication")
    writer = Store(outer_store.root, outer_store.budget, publication)
    pin = None
    try:
        pin = writer.write(prefix + "/PENDING_REVIEW.json", canonical(result), RECORD_CAP)
    except BaseException as original:
        publication.capture(original, "pending_publication")
    finally:
        outer_store.custody.fail(None, "pending_publication", publication)
        if pin is not None:
            outer_store.custody.facts["original_F_authoring_pending"] = pin
    outer_store.custody.raise_if_failed()
    return pin, result
