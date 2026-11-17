"""Full original 76-panel projection. This module computes no scientific metric."""
from .common import need, same, encode, pin, parse, closed

ARMS = ("paper_data", "paper_data_author_code")

def seal_collections(collections, source_encode):
    need(set(collections) == set(ARMS), "both complete original collections")
    result = {}
    for arm in ARMS:
        c = collections[arm]
        need(c["condition"] == arm and c["protected_targets_opened"] is False,
             "original target-last arm")
        raw = source_encode(c)
        # Original codec bytes are kept; no projection is substituted for the seal.
        result[arm] = {"raw":raw,"identity":pin(raw)}
    return result

def project_panels(scope, census, census_pin, collections, graded, support,
                   reference_banks, context_admissions, original_failures):
    need(len(scope.panel_ids) == 76 and len(set(scope.panel_ids)) == 76, "full original panels")
    need(census['scope_digest']==scope.digest and set(census['panels'])==set(scope.panel_ids),
         'same complete original census and panel domain')
    jobs = census["jobs"]
    ids = [j["id"] for j in jobs]
    need(len(set(ids)) == len(ids), "complete unique original job domain")
    byid = {j["id"]:j for j in jobs}
    candidate_ids = [j["id"] for j in jobs if j["operation"] == "candidate"]
    need(set(collections) == set(ARMS), "full paired collection domain")
    for arm in ARMS:
        c = collections[arm]
        need(c["condition"] == arm and c["scope_digest"] == scope.digest and
             c["protected_targets_opened"] is False and set(c["results"]) == set(candidate_ids),
             "every original candidate, including failures, in source order")
    if graded is not None:
        need(graded["scope_digest"] == scope.digest and set(graded["jobs"]) == set(candidate_ids),
             "complete protected grade has the same full job set")
        for jid in candidate_ids:
            need(set(graded["jobs"][jid]) == set(ARMS), "both original metric objects")
    need(set(support) == set(ids), "all supporting job outcomes retained")
    panels, metrics = {}, {}
    for panel in scope.panel_ids:
        members = [j["id"] for j in jobs if panel in j["panels"]]
        candidate_members = [jid for jid in members if jid in candidate_ids]
        noncandidate = [jid for jid in members if jid not in candidate_ids]
        binding = census["panels"][panel]
        bound = binding.get("status") == "bound"
        if bound:
            need(binding["jobs"] == members, "exact original panel/job incidence")
        failures = [f for f in original_failures
                    if f.get("panel_id") == panel or f.get("job_id") in members or
                    f.get("whole_campaign") is True]
        support_rows = []
        variant_groups = []
        complete = bound and bool(members) and not failures
        for arm in ARMS:
            for failure in collections[arm]['failures']:
                # Preserve the exact original failure object plus its arm.
                # An unscoped failure cannot be silently assigned to no panel.
                if failure.get('job_id') in members or failure.get('job_id') is None:
                    failures.append({'arm':arm,'original_collection_failure':failure})
                    complete=False
        for jid in members:
            j = byid[jid]; evidence = support[jid]
            need(evidence["job_id"] == jid, "same original support job")
            row = {"job_id":jid,"operation":j["operation"],"variant":j["variant"],
                   "support_identity":j["support_identity"],
                   "expected_outputs":j["expected_outputs"],"original_evidence":evidence}
            support_rows.append(row)
            group = next((g for g in variant_groups if g["variant"] == j["variant"] and
                          same(g["support_identity"],j["support_identity"])),None)
            if group is None:
                group = {"variant":j["variant"],"support_identity":j["support_identity"],"jobs":[]}
                variant_groups.append(group)
            group["jobs"].append(jid)
            if evidence["status"] != "admitted_complete":
                complete = False
                failures.append({"job_id":jid,"status":evidence["status"],
                                 "original_evidence":evidence})
        candidate_rows = []
        for jid in candidate_members:
            arm_rows = {arm:collections[arm]["results"][jid] for arm in ARMS}
            candidate_rows.append({"job_id":jid,"arms":arm_rows})
            if any(r["status"] != "collected" for r in arm_rows.values()):
                complete = False
            if graded is None or jid not in reference_banks:
                complete = False
            elif all(r['status']=='collected' for r in arm_rows.values()):
                bank=reference_banks[jid]
                identity=bank['scientific_identity']
                need(all(same(r['payload']['identities']['scientific_identity'],identity) for r in arm_rows.values()) and
                     all(same(bank[k]['identities']['scientific_identity'],identity) for k in ('independent','native')),
                     'both original candidates and both references retain the same scientific identity')
        context = []
        if not candidate_members:
            admission = context_admissions.get(panel)
            if admission is None:
                complete = False
            else:
                closed(admission,("panel_id","kind","original_obligation","outputs","source_admission"))
                need(admission["panel_id"] == panel and admission["kind"] in
                     ("context","provenance","render"), "independently selected nonperformance designation")
                # These identities are supplied only by the source-bound context admission consumer.
                context = [admission]
                if not admission["outputs"] or not admission["source_admission"]:
                    complete = False
        panels[panel] = {"schema":"critical_init_panel_collection_v2",
                         "status":"complete" if complete else "required_unscorable",
                         "panel_id":panel,"census":census_pin,"support_jobs":support_rows,
                         "candidate_jobs":candidate_rows,
                         "noncandidate_jobs":[r for r in support_rows if r["job_id"] in noncandidate],
                         "failure_records":failures,"variant_groups":variant_groups}
        metrics[panel] = None
        if complete:
            metric_jobs = []
            for jid in candidate_members:
                j = byid[jid]; bank = reference_banks[jid]
                arm_metrics = graded["jobs"][jid]
                for arm in ARMS:
                    need(set(arm_metrics[arm]) == set(bank["metrics"]),
                         "entire original protected metric object domain")
                metric_jobs.append({"job_id":jid,"variant":j["variant"],
                                    "support_identity":j["support_identity"],
                                    "scientific_identity":bank["scientific_identity"],
                                    "arm_metrics":arm_metrics})
            metrics[panel] = {"schema":"critical_init_panel_metrics_v2","panel_id":panel,
                              "kind":"candidate_comparison" if candidate_members else "source_context",
                              "jobs":metric_jobs,"context_evidence":context}
    return panels, metrics
