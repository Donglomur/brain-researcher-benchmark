"""Trusted composition of captured OpenBMI source and the adaptive-only broker.

Globals are injected only by the source-authenticating loader. Neither review
flags nor supplied receipts create execution/spending/target authority.
"""
import copy
import hashlib
import os
import json
import math
from pathlib import Path

PANELS = ("frozen_program", "case_adaptive", "reference")
OUTPUT_VOLUMES = {"fit": 553648128, "infer": 8388608}
# Trusted caller retains this module through terminal cleanup. Never exposed to candidates.
active_state = None


def schedule(panel):
    ordinal = 0
    for name in PANELS:
        for case in panel["cases"]:
            for setting in contracts.SETTINGS:
                for arm in contracts.ARMS:
                    yield {"panel": name, "case": case["case"], "setting": setting,
                           "arm": arm, "ordinal": ordinal}
                    ordinal += 1
    c.need(ordinal == 3888, "Three complete original panels")


def context_key(item):
    return (item["case"], item["setting"], item["arm"])


def context_id(item):
    return c.pin(c.encoded({key: item[key] for key in ("case", "setting", "arm")}))["sha256"]


def tool_protocol_pin():
    return c.pin(c.encoded({"schema": "neural083_model_python_finish_protocol_v1",
                           "reused_framing": broker_factory.PINS,
                           "entry": c.pin(source_bodies["adaptive_entry.py"]),
                           "client": c.pin(source_bodies["openbmi_agent_tools.py"])}))["sha256"]


def capture_operand(row, budget):
    c.need(type(row) is dict and set(row) == {"path", "bytes", "sha256"}, "Exact captured operator operand")
    c.need(type(row["bytes"]) is int and 0 < row["bytes"] <= 1048576, "Ordinary bounded metadata operand")
    return c.capture(row["path"], 1048576, c.only_pin(row), budget.tick, budget.read)


def prepare(selection, source, program, pairing, budget):
    global active_state
    c.need(active_state is None or active_state.active_context is None,
           "Unresolved model context retained; external cleanup required before a new attempt")
    fields = {"schema", "incumbent_source", "plan", "authoring_receipt", "instructions",
              "model_config", "broker_limits", "method_review"}
    c.need(type(pairing) is dict and set(pairing) == fields and
           pairing["schema"] == "neural083_paired_source_selection_v1", "Exact paired operator selection")
    c.need(pairing["incumbent_source"] == incumbent_source, "Exact incumbent dependency")
    raw = {name: capture_operand(pairing[name], budget) for name in fields - {"schema", "incumbent_source"}}
    value = {name: c.parse(body) for name, body in raw.items()}
    canonical_raw = c.capture(selection["canonical"]["path"], 4000000,
                              c.only_pin(selection["canonical"]), budget.tick, budget.read)
    panel = contracts.canonical(c.parse(canonical_raw))
    plan = paired_policy.validate_plan(value["plan"], panel)
    c.need(plan["frozen_program"]["artifact"] == c.pin(program), "Same globally frozen numerical program")
    authoring = paired_policy.validate_authoring_usage(value["authoring_receipt"], plan)
    config = agent_driver.instructions(value["instructions"])
    spec = value["model_config"]
    c.need(type(spec) is dict and spec.get("model_revision") == plan["model"]["identity"] and
           c.pin(c.encoded(spec))["sha256"] == plan["model"]["configuration_sha256"], "Fixed trusted model configuration")
    c.need(hashlib.sha256(config["system_prompt"].encode("utf8")).hexdigest() == plan["model"]["prompt_sha256"] and
           c.pin(source_bodies["agent_driver.py"])["sha256"] == plan["model"]["procedure_sha256"] and
           tool_protocol_pin() == plan["model"]["tool_protocol_sha256"], "Captured prompt, procedure and tool protocol")
    # This checks declared supported values, not actual containment or total RSS.
    for phase in ("fit", "infer"):
        cap = plan["condition_limits"]["frozen_program"][phase]
        c.need(cap["cpu_count"] == 1 and cap["memory_bytes"] == selection["memory_bytes"] and
               cap["storage_bytes"] == OUTPUT_VOLUMES[phase] and
               cap["wall_seconds"] == selection[phase + "_seconds"] + 130,
               "Explicit ceilings must match the unchanged supported native profile")
    limits_rows = value["broker_limits"]
    c.need(type(limits_rows) is dict and set(limits_rows) == {"schema", "contexts"} and
           limits_rows["schema"] == "neural083_broker_allocations_v1" and
           type(limits_rows["contexts"]) is list and len(limits_rows["contexts"]) == 1296, "Complete broker allocations")
    dependency_reads = sum(size for size, _sha in broker_factory.PINS.values()) + len(broker_factory.PINS)
    budget.read(dependency_reads)
    modules = broker_factory.load_dependencies()
    modules["morse_broker"].validate_model_spec(spec)
    limits = {}
    for allocation, row in zip(plan["adaptive_allocations"], limits_rows["contexts"]):
        c.need(type(row) is dict and set(row) == {"case", "setting", "arm", "limits"} and
               context_key(row) == context_key(allocation), "Identical context allocations before staging")
        selected = row["limits"]
        modules["morse_broker"].exact(selected, broker_factory.MODEL_LIMITS + broker_factory.EXTRA_LIMITS, "Broker limits")
        modules["morse_broker"].validate_broker_limits({k: selected[k] for k in broker_factory.MODEL_LIMITS})
        for key in broker_factory.EXTRA_LIMITS:
            modules["morse_broker"].integer(selected[key], key)
        c.need(selected["max_calls"] == allocation["calls"] and
               selected["input_tokens"] + selected["output_tokens"] == allocation["tokens"] and
               selected["native_receipt_bytes"] >= broker_factory.minimum_receipt_bytes(selected),
               "Exact positive model split and full transcript capture reservation")
        limits[context_key(row)] = copy.deepcopy(selected)
    # All additional stream/receipt/source reads and writes are prospectively
    # reserved before data staging. Failed/retired stages remain charged.
    extra_receipts = 3 * sum(row["native_receipt_bytes"] for row in limits.values()) + 1048576
    extra_streams = 2 * sum(row["stdout_bytes"] + row["stderr_bytes"] + 131072 for row in limits.values())
    extra_model_reads = 2 * sum(row["max_calls"] * (spec["response_max_bytes"] +
                               spec["stderr_max_bytes"] + 131072) for row in limits.values())
    old = contracts.numerical_work()
    for field, components in (("writes", ("training_numeric_copy_bytes", "query_numeric_copy_bytes", "all_model_capture_max_bytes",
                                          "native_receipt_cap_bytes", "condition_metadata_cap_bytes", "prediction_cap_bytes", "phase_intent_cap_bytes")),):
        minimum = sum(3 * old[key] // 2 for key in components) + extra_receipts
        c.need(selection["limits"][field] >= minimum, "Whole three-panel construction and transcript allowance")
    minimum_reads = (3 * old["native_reply_reservation_bytes"] // 2 +
                     9 * (old["training_numeric_copy_bytes"] + old["query_numeric_copy_bytes"]) // 2 +
                     3 * old["all_model_capture_max_bytes"] + extra_streams + extra_model_reads + extra_receipts + 1296 * dependency_reads)
    c.need(selection["limits"]["reads"] >= minimum_reads and
           selection["limits"]["retained"] >= 3 * old["retained_upper_components_bytes"] // 2 + extra_receipts,
           "Complete native, broker, source and retained-output allowances")
    review = value["method_review"]
    config_binding = c.pin(c.encoded({"selection": selection,
                                     "pairing": {k: v for k, v in pairing.items() if k != "method_review"}}))
    c.need(type(review) is dict and review.get("schema") == "neural083_paired_method_admission_v1" and
           review.get("source") == source and review.get("configuration") == config_binding,
           "Exact externally selected paired method review")
    for name in ("execution_authorized", "authoring_usage_authenticated", "model_provider_and_token_bound_admitted",
                 "three_panel_native_and_resource_admitted", "training_only_semantics_reviewed", "cross_context_reset_reviewed"):
        c.need(review.get(name) is True, "Separate paired admission remains required: " + name)
    c.need(review.get("mounts_prove_no_query_fitting") is False and token_admission is not None,
           "No semantic guarantee from mounts; actual trusted token-bound admission required")
    token_admission.require_model_bound(spec)
    state = PairingState(selection, source, panel, plan, spec, raw["instructions"], limits, authoring,
                         {name: c.pin(body) for name, body in raw.items()}, dependency_reads)
    state.current_budget = budget
    state.broker_digest = modules["morse_broker"].digest
    active_state = state
    return state


class PairingState:
    def __init__(self, selection, source, panel, plan, spec, instructions_raw, limits, authoring, operands, dependency_reads):
        self.selection, self.source, self.panel, self.plan = selection, source, panel, plan
        self.spec, self.instructions_raw, self.limits, self.authoring = spec, instructions_raw, limits, authoring
        self.dependency_reads = dependency_reads
        self.driver_pin = c.pin(source_bodies["agent_driver.py"])
        self.commitment = {"schema": "neural083_pairing_commitment_v1", "operands": operands,
                           "driver": self.driver_pin, "model_configuration": c.pin(c.encoded(spec)),
                           "frozen_runtime_model_calls": 0, "allocations_fixed_before_staging": True,
                           "native_profile": {"producer_cpus": 1, "output_volumes": OUTPUT_VOLUMES,
                              "producer_tmpfs_bytes": 33554432, "producer_shm_bytes": 16777216,
                              "holder_ready_bytes": 4096, "holder_shm_bytes": 16777216,
                              "holder_memory_bytes": {"fit": 4294967296, "infer": 134217728}, "holder_cpus": 1}}
        self.closed = []
        self.active_context = None

    def stage_program(self, root, budget):
        path = root / "adaptive_program.py"
        c.save(path, source_bodies["agent_driver.py"], 1048576, budget.tick, budget.write)
        c.readable(path, budget.tick)
        return path

    def stage_trusted(self, root, budget):
        path = root / "adaptive_trusted"
        path.mkdir(mode=0o700)
        names = ("holder.py", "adaptive_entry.py", "openbmi_agent_tools.py", "morse_bootstrap.py", "morse_protocol.py")
        for name in names:
            c.save(path / name, source_bodies[name], 1048576, budget.tick, budget.write)
            c.readable(path / name, budget.tick)
        c.save(path / "AGENT_INSTRUCTIONS.json", self.instructions_raw, 1048576, budget.tick, budget.write)
        c.readable(path / "AGENT_INSTRUCTIONS.json", budget.tick)
        os.chmod(path, 0o555)
        c.sync_dir(path, budget.tick)
        return path

    def schedule(self, panel):
        c.need(panel == self.panel, "Same pre-staging canonical panel")
        return schedule(panel)

    def select(self, item, submitted, reference, adaptive_program, submitted_pin, reference_pin):
        name = item["panel"]
        if name == "frozen_program":
            return submitted, submitted_pin, None
        if name == "reference":
            return reference, reference_pin, None
        c.need(name == "case_adaptive", "Declared adaptive panel")
        # Charged before the constructor's exact dependency reread.
        c.need(self.active_context is None, "Previous model context must close before a fresh case")
        self.current_budget.read(self.dependency_reads)
        broker = broker_factory.ContextBroker(self.spec, context_id(item), self.limits[context_key(item)], token_admission)
        self.active_context = broker
        return adaptive_program, self.driver_pin, broker

    def receipt_cap(self, item):
        return self.limits[context_key(item)]["native_receipt_bytes"] if item["panel"] == "case_adaptive" else 262144

    def phase(self, item, context, selection, trusted, current, program, model, directory, kind,
              ordinal, source, budget, deadline, native):
        if item["panel"] == "case_adaptive":
            c.need(context is not None and context.context_id == context_id(item), "Exact adaptive context")
            return adaptive_native.phase(selection, trusted, current, program, model, directory, kind,
                                         ordinal, source, budget, deadline, context)
        c.need(context is None, "No model broker in frozen numerical/reference phases")
        return native.phase(selection, trusted, current, program, model, directory, kind,
                            ordinal, source, budget, deadline)

    def close_context(self, item, context, folder, budget):
        if item["panel"] != "case_adaptive":
            c.need(context is None, "No numerical runtime model usage")
            return None
        receipt = context.final_receipt()
        c.need(receipt["complete"] is True and receipt["engine_path"] == "real_future_https_child" and
               receipt["context_id"] == context_id(item), "Both real model stages closed")
        pin = c.save(folder / "AGENT_USAGE.json", c.encoded(receipt), self.receipt_cap(item), budget.tick, budget.write)
        self.closed.append({"condition": item, "usage": pin, "reserved": receipt["reserved"]})
        c.need(self.active_context is context, "Same retained active broker")
        self.active_context = None
        return pin

    def finish(self, root, budget):
        c.need(len(self.closed) == 1296 and len({context_key(x["condition"]) for x in self.closed}) == 1296,
               "Complete adaptive accounting without duplicate contexts")
        calls = sum(x["reserved"]["max_calls"] for x in self.closed)
        tokens = sum(x["reserved"]["input_tokens"] + x["reserved"]["output_tokens"] for x in self.closed)
        ceiling = self.plan["frozen_program"]["authoring_ceiling"]
        c.need(calls <= ceiling["calls"] and tokens <= ceiling["tokens"], "Shared aggregate model ceilings")
        report = {"schema": "neural083_paired_model_accounting_v1", "authoring": self.authoring,
                  "adaptive_reserved_calls": calls, "adaptive_reserved_tokens": tokens,
                  "contexts": self.closed, "ceiling_each_strategy": ceiling,
                  "equal_actual_compute_claimed": False, "frozen_runtime_model_calls": 0,
                  "runtime_qualified": False, "scientific_qualified": False}
        return c.save(root / "MODEL_ACCOUNTING.json", c.encoded(report), 1048576, budget.tick, budget.write)

    def admit_commitment(self, done, root, get):
        """Join captured selection to outputs before any protected labels open."""
        c.need(done["pairing"] == self.commitment and done["adaptive"] == self.driver_pin,
               "Same prospectively fixed adaptive source/configuration")
        commitment = get(root / "COMMITMENT.json")
        c.need(commitment.get("pairing") == self.commitment, "Initial and terminal paired commitment")
        value = get(root / "MODEL_ACCOUNTING.json", done["model_accounting"], 1048576)
        c.need(type(value) is dict and set(value) == {"schema", "authoring", "adaptive_reserved_calls",
               "adaptive_reserved_tokens", "contexts", "ceiling_each_strategy", "equal_actual_compute_claimed",
               "frozen_runtime_model_calls", "runtime_qualified", "scientific_qualified"} and
               value["schema"] == "neural083_paired_model_accounting_v1" and
               value["authoring"] == self.authoring and value["ceiling_each_strategy"] ==
               self.plan["frozen_program"]["authoring_ceiling"], "Same captured authoring accounting")
        c.need(type(value["contexts"]) is list and len(value["contexts"]) == 1296,
               "Every adaptive context accounted")
        for key in ("equal_actual_compute_claimed", "runtime_qualified", "scientific_qualified"):
            c.need(value[key] is False, "No source-only qualification or equal-actual-compute claim")
        c.need(type(value["frozen_runtime_model_calls"]) is int and value["frozen_runtime_model_calls"] == 0,
               "Frozen programme has no runtime model budget")
        self._accounting = value
        self._admitted_contexts = []

    def admit_native(self, item, kind, value):
        if item["panel"] != "case_adaptive":
            c.need("broker" not in value, "No numerical/reference broker receipt")
            return
        ident = context_id(item)
        limits = self.limits[context_key(item)]
        record = value["broker"]
        c.need(record["schema"] == "openbmi-adaptive-stage-broker-v1" and
               record["context_id"] == ident and record["kind"] == kind and
               record["native_qualified"] is False, "Exact adaptive stage identity")
        c.need(record["stream_read_reservation_bytes"] == limits["stdout_bytes"] + limits["stderr_bytes"] + 131072 and
               record["model_child_read_reservation_bytes"] == limits["max_calls"] *
               (self.spec["response_max_bytes"] + self.spec["stderr_max_bytes"] + 131072),
               "All stage model/stream reservations")
        attached = record["attached"]
        for key in ("success", "client_reaped", "owned_group_absence_observed", "cleanup_complete",
                    "cleanup_before_original_cutoff"):
            c.need(attached.get(key) is True, "Complete attached process closure")
        c.need(attached.get("schema") == "openbmi-adaptive-attached-v1" and
               attached.get("error_type") is None and attached.get("cancel_error") is None and
               attached.get("leader_exited_with_group_alive") is False, "No attached process error")
        pump = attached["pump"]
        c.need(pump["success"] is True and pump["error_code"] is None and
               type(pump["attach_exit_code"]) is int and pump["attach_exit_code"] == 0 and
               pump["broker_thread_terminal"] is True and pump["broker_cancel_error"] is None,
               "Natural complete framed broker exchange")
        for key in ("stdout_bytes", "stderr_bytes"):
            c.need(type(pump[key]) is int and 0 <= pump[key] <= limits[key], "Bounded captured worker stream")
        summary = record["phase_record"]
        phase = {"fit": "train", "infer": "query"}[kind]
        c.need(summary["kind"] == kind and summary["phase"] == phase and
               summary["context_id"] == ident and summary["successful"] is True and
               summary["model_child_terminal"] is True and summary["broker_thread_terminal"] is True and
               summary["cancel_error"] is None,
               "Closed phase-bound model child")
        usage, transcript = summary["usage"], summary["private_transcript"]
        for obj in (usage, transcript):
            c.need(obj["context_id"] == ident and obj["phase"] == phase and
                   obj["engine_path"] == "real_future_https_child" and
                   obj["model_revision"] == self.spec["model_revision"] and
                   obj["model_spec_sha256"] == self.broker_digest(self.spec), "Exact trusted model context")
        c.need(type(usage["calls"]) is int and usage["calls"] > 0, "Investigator must actually request a model action")
        storage_hash = hashlib.sha256(json.dumps(transcript, sort_keys=True, separators=(",", ":"),
                                                 allow_nan=False).encode()).hexdigest()
        c.need(summary["transcript_storage_sha256"] == storage_hash, "Stable complete private transcript storage pin")
        c.need(usage["failed"] is False and usage["model_child_terminal"] is True and
               usage["cancelled"] is True, "No failed or unclosed model request")
        for key, bound in (("calls", "max_calls"), ("input_tokens_reserved", "input_tokens"),
                           ("output_tokens_reserved", "output_tokens")):
            c.need(type(usage[key]) is int and 0 <= usage[key] <= limits[bound], "Typed phase model budget")
        traces, calls = usage["traces"], transcript["calls"]
        c.need(type(traces) is list and type(calls) is list and len(traces) == len(calls) == usage["calls"],
               "No omitted model request in complete transcript")
        sums = {key: 0 for key in ("input_reserved", "output_reserved", "input_tokens", "output_tokens")}
        for sequence, (trace, call) in enumerate(zip(traces, calls)):
            c.need(type(trace["seq"]) is int and trace["seq"] == sequence and
                   type(call["seq"]) is int and call["seq"] == sequence and
                   trace["status"] == call["status"] == "complete", "Complete ordered successful model calls")
            response = call["response"]
            c.need(response["seq"] == sequence and response["ok"] is True and
                   response["result"]["usage"] == trace["usage"], "Same actual response usage")
            for key in ("input_reserved", "output_reserved"):
                c.need(type(trace[key]) is int and trace[key] > 0, "Positive dispatched token reservation")
                sums[key] += trace[key]
            for key, reservation in (("input_tokens", "input_reserved"), ("output_tokens", "output_reserved")):
                number = trace["usage"][key]
                c.need(type(number) is int and 0 <= number <= trace[reservation], "Reported usage within reservation")
                sums[key] += number
        c.need(sums["input_reserved"] == usage["input_tokens_reserved"] and
               sums["output_reserved"] == usage["output_tokens_reserved"] and
               sums["input_tokens"] == usage["input_tokens_reported"] and
               sums["output_tokens"] == usage["output_tokens_reported"], "Summed phase budget and reported usage")

    def admit_context(self, item, closed, fit, inferred, folder, get):
        if item["panel"] != "case_adaptive":
            c.need(closed.get("agent_usage") is None, "No numerical context model usage")
            return
        receipt = get(folder / "AGENT_USAGE.json", closed["agent_usage"], self.receipt_cap(item))
        c.need(receipt["context_id"] == context_id(item) and receipt["mode"] == "case_adaptive" and
               receipt["engine_path"] == "real_future_https_child" and receipt["complete"] is True and
               type(receipt["unresolved_model_children"]) is int and receipt["unresolved_model_children"] == 0 and
               type(receipt["unobserved_broker_thread_phases"]) is list and not receipt["unobserved_broker_thread_phases"] and
               receipt["limits"] == self.limits[context_key(item)] and
               receipt["model_spec_sha256"] == self.broker_digest(self.spec), "Complete matching context receipt")
        spec_storage = hashlib.sha256(json.dumps(self.spec, sort_keys=True, separators=(",", ":"),
                                                allow_nan=False).encode()).hexdigest()
        c.need(receipt["model_spec_storage_sha256"] == spec_storage, "Stable selected model configuration storage pin")
        for key in ("native_qualification", "provider_state_qualification", "scientific_qualification"):
            c.need(receipt[key] is False, "No automatic context qualification")
        summaries = [{key: value for key, value in stage["broker"]["phase_record"].items()
                      if key not in ("private_transcript", "transcript_custody")} for stage in (fit, inferred)]
        c.need(receipt["phases"] == summaries, "Exact train then query stage summaries")
        reserved = {key: sum(x["usage"][field] for x in summaries) for key, field in
                    (("max_calls", "calls"), ("input_tokens", "input_tokens_reserved"),
                     ("output_tokens", "output_tokens_reserved"))}
        c.need(receipt["reserved"] == reserved and all(type(receipt["reserved"][key]) is int and
               receipt["reserved"][key] <= self.limits[context_key(item)][key] for key in reserved),
               "Shared fit/query context allocation; no refund or reset")
        self._admitted_contexts.append({"condition": item, "usage": closed["agent_usage"], "reserved": reserved})

    def admit_finished(self):
        value = self._accounting
        c.need(self._admitted_contexts == value["contexts"], "Every accounted context matches admitted native stages")
        calls = sum(x["reserved"]["max_calls"] for x in self._admitted_contexts)
        tokens = sum(x["reserved"]["input_tokens"] + x["reserved"]["output_tokens"] for x in self._admitted_contexts)
        c.need(type(value["adaptive_reserved_calls"]) is int and value["adaptive_reserved_calls"] == calls and
               type(value["adaptive_reserved_tokens"]) is int and value["adaptive_reserved_tokens"] == tokens and
               calls <= value["ceiling_each_strategy"]["calls"] and tokens <= value["ceiling_each_strategy"]["tokens"],
               "Exact full-strategy model usage within prospectively equal ceilings")
