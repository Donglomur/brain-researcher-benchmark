"""Exact original Publisher/root receipt bases and target-last own-run collections."""
from .common import need, closed, same, pin, encode, parse, relative, integer

def ordinary_hex(value, cap):
    need(type(value) is str and len(value) <= 2 * cap and len(value) % 2 == 0,
         "bounded complete original stream hex")
    need(all(c in "0123456789abcdef" for c in value), "canonical original hex")
    return bytes.fromhex(value)

def reference_submission(plan, complete_pin, reference_store, workspace_store,
                         consume_store, *, source_encode, scope_identity, inputs_identity):
    need(len(plan["jobs"]) == 8223, "full original 8223-job plan")
    plan_identity = pin(source_encode(plan))
    complete = reference_store.document(complete_pin, 16 << 20)
    closed(complete,("plan","completed","scientific_qualified","budget"))
    ids = [j["id"] for j in plan["jobs"]]
    need(set(complete["completed"]) == set(ids) and complete["plan"] == plan_identity,
         "complete original job order, including consume")
    original_receipts = {}
    consume = None
    for ordinal, job in enumerate(plan["jobs"]):
        journal_pin = complete["completed"][job["id"]]
        need(journal_pin["path"] == "job_%05d.json" % ordinal, "actual Journal Publisher ordinal")
        journal = reference_store.document(journal_pin, 16 << 20)
        closed(journal,("job","plan","receipt","observation"))
        need(journal["job"] == job["id"] and journal["plan"] == plan_identity, "same original job")
        observation = journal["observation"]
        closed(observation,("completion","stdout_hex","stderr_hex","stdout_pin","stderr_pin"))
        c = observation["completion"]
        need(c["natural_completion"] is True and type(c["returncode"]) is int and
             c["returncode"] == 0 and c["forced"] is False, "original natural child completion")
        for name in ("stdout","stderr"):
            raw = ordinary_hex(observation[name+"_hex"], 16 << 20)
            need(pin(raw) == observation[name+"_pin"], "complete original job stream")
        receipt = workspace_store.document(journal["receipt"], 16 << 20)
        closed(receipt,("schema","job","plan","result","source_scope","inputs","budget","output_custody"))
        need(receipt["schema"] == "hundred_models_original_job_receipt_v1" and
             receipt["job"] == job["id"] and receipt["plan"] == plan_identity and
             receipt["source_scope"] == scope_identity and receipt["inputs"] == inputs_identity,
             "same complete source scope and scientific inputs, own job receipt")
        original_receipts[job["id"]] = {"journal":journal_pin,"receipt":journal["receipt"],
                                       "document":receipt,"observation":observation}
        if receipt["result"].get("schema") == "hundred_models_complete_consumer_receipt_v1":
            need(consume is None, "unique original consume producer")
            need(consume_store.root.name == "work_%05d" % ordinal,
                 "explicit consume Publisher root derived from plan ordinal")
            consume = receipt["result"]
    need(consume is not None, "complete original consume job required")
    document = consume_store.document(consume["submission"], 16 << 20)
    need(document["schema"] == "hundred_models_submission_v2", "full reference ABI")
    return {"document":document,"submission":consume["submission"],"complete":complete_pin,
            "plan":plan_identity,"original_jobs":original_receipts}

def candidate_submission(receipt_pin, candidate_store, selected_submission,
                         *, source_encode, process_admission):
    # process_admission is a fixed original outer consumer result, never child JSON alone.
    need(process_admission.complete and process_admission.subject == "candidate",
         "independently closed original candidate invocation")
    receipt = candidate_store.document(receipt_pin, 16 << 20)
    closed(receipt,("submission","result","completion","stdout_hex","stderr_hex","scientific_qualification"))
    need(receipt["submission"] == pin(source_encode(selected_submission)),
         "exact source-selected candidate invocation")
    need(receipt["result"]["path"] == "candidate_result.json", "original operator Publisher result")
    need(receipt["completion"] == process_admission.original_child_completion,
         "same actual inner process, not a success-shaped receipt")
    for name in ("stdout","stderr"):
        raw = ordinary_hex(receipt[name+"_hex"], selected_submission["stream_limit_bytes"])
        need(pin(raw) == process_admission.original_child_streams[name], "complete original candidate stream")
    document = candidate_store.document(receipt["result"], selected_submission["maximum_result_bytes"])
    need(document["schema"] == "hundred_models_submission_v2", "full candidate ABI")
    custody = document["custody"]
    need(custody["schema"] == "hundred_models_own_run_custody_v1" and
         custody["runtime_source"] == pin(source_encode(selected_submission["source_files"])) and
         custody["environment"] == pin(source_encode(selected_submission["environment"])),
         "operator-attached own-run source/environment custody")
    return {"document":document,"receipt":receipt_pin,"result":receipt["result"],
            "submission_identity":receipt["submission"],"process":process_admission.record_pin}

def seal_candidates(candidates, source_encode):
    need(set(candidates) == {"A","B"}, "both original arms before protected reference")
    return {arm:{"raw":source_encode(candidates[arm]["document"]),
                 "identity":pin(source_encode(candidates[arm]["document"])),
                 "original":candidates[arm]} for arm in ("A","B")}

def make_matched_pair(pair_id, scores, originals, admission):
    need(admission.complete and admission.pair_id == pair_id,
         "independent own-run isolation, common-input and resource admission")
    rows = {}
    additions = {"arm","common_inputs","budget_identity","independent_fresh_workspace","provenance"}
    for arm in ("A","B"):
        score = scores[arm]
        need(not set(score) & additions, "do not overwrite original scientific score fields")
        need(originals[arm]["submission_identity"] == admission.submissions[arm],
             "distinct exact own-run identities are admitted separately")
        rows[arm] = dict(score,arm=arm,common_inputs=admission.common_inputs,
                         budget_identity=admission.budget_identity,
                         independent_fresh_workspace=True,
                         provenance={"original":originals[arm],"qualification":admission.record_pin,
                                     "costs":admission.whole_costs})
    return {"pair_id":pair_id,"A":rows["A"],"B":rows["B"]}
