"""Actual whole-panel history barriers; trusted in-process core, not a sandbox."""
from copy import deepcopy
from .contracts import (need, probability, canonical, pin, identity, CONDITIONS, STATUS,
                        check_prepared)

class PanelController:
    def __init__(self, prepared, members, methods, project_case, durable_append):
        check_prepared(prepared, members)
        need(callable(project_case) and callable(durable_append), "fixed projection/journal")
        need(type(methods) is list and methods, "complete declared methods")
        self.sessions = deepcopy(prepared)
        self.members = deepcopy(members)
        self.methods = deepcopy(methods)
        self.project, self.writer = project_case, durable_append
        self.method_keys = []
        for m in self.methods:
            key = (m["method_id"], m["arm"])
            need(key not in self.method_keys and m["arm"] in ("F","I","R"), "unique methods")
            identity(m["method_source_identity"])
            rows = m["commitments"]
            need(len(rows) == 29*4, "all method/source/condition commitments")
            mapped = {(r["session_id"],r["condition"]): r for r in rows}
            need(len(mapped) == 116 and set(mapped) == {(s["session_id"],c)
                 for s in self.sessions for c in CONDITIONS}, "exact method commitment grid")
            for r in rows:
                identity(r["config_identity"]); identity(r["parameter_identity"])
            self.method_keys.append(key)
        self.queue = [(s,c) for s in self.sessions for c in s["cases"] if c["split"]=="test"]
        self.position, self.pending, self.previous = 0, None, None
        self.committed, self.rows = set(), []
        self.failure, self.completed = None, None
        self.original_slots = [{"session_id":s["session_id"],"slots":deepcopy(s["slots"])}
                               for s in self.sessions]

    def _healthy(self):
        need(self.failure is None and self.completed is None, "controller poisoned/closed")

    def next_case(self):
        self._healthy()
        need(self.pending is None, "all paired predictions must commit before advance")
        if self.position == len(self.queue):
            return None
        s,c = self.queue[self.position]
        prior = c.get("prior_case_id")
        if c.get("history_available") and prior is not None:
            previous_test = any(x["case_id"]==prior and x["split"]=="test" for x in s["cases"])
            need(not previous_test or (s["session_id"],prior) in self.committed,
                 "prior scored history requires earlier complete panel commitment")
        views = {condition:self.project(deepcopy(c),condition,include_label=False)
                 for condition in CONDITIONS}
        need(all("y" not in v for v in views.values()), "no held target projection")
        self.pending = (s,c,views)
        return {"session_id":s["session_id"],"case_id":c["case_id"],
                "views":deepcopy(views)}

    def commit(self, responses):
        self._healthy()
        need(self.pending is not None, "pending case required")
        s,c,views = self.pending
        expected = {(mid,arm,condition) for mid,arm in self.method_keys for condition in CONDITIONS}
        try:
            need(type(responses) is list and len(responses)==len(expected), "whole paired panel")
            keyed = {}
            for r in responses:
                need(type(r) is dict and set(r)=={"method_id","arm","condition","case_id","p"},
                     "exact actor response")
                key=(r["method_id"],r["arm"],r["condition"])
                need(key in expected and key not in keyed and r["case_id"]==c["case_id"],
                     "exact response identity")
                keyed[key]=probability(r["p"])
            rows=[]
            for method in self.methods:
                commits={(r["session_id"],r["condition"]):r for r in method["commitments"]}
                for condition in CONDITIONS:
                    reg=commits[(s["session_id"],condition)]
                    rows.append({"method_id":method["method_id"],"arm":method["arm"],
                        "session_id":s["session_id"],"subject_id":s["subject_id"],"lab":s["lab"],
                        "condition":condition,"source_identity":deepcopy(s["source_identity"]),
                        "unit_ids":deepcopy(s["unit_ids"]),"case_id":c["case_id"],
                        "ordinal":c["ordinal"],"split":"test","prior_case_id":c.get("prior_case_id"),
                        "method_source_identity":deepcopy(method["method_source_identity"]),
                        "config_identity":deepcopy(reg["config_identity"]),
                        "parameter_identity":deepcopy(reg["parameter_identity"]),
                        "p":keyed[(method["method_id"],method["arm"],condition)],"status":"ok"})
            record={"sequence":self.position,"session_id":s["session_id"],
                    "case_id":c["case_id"],"view_pins":{k:pin(v) for k,v in views.items()},
                    "previous_commit":self.previous,"predictions":rows}
            raw=canonical(record); acknowledgement=self.writer(raw)
            need(acknowledgement==pin(raw), "exact durable acknowledgement")
            self.rows.extend(rows);self.committed.add((s["session_id"],c["case_id"]))
            self.previous=acknowledgement;self.position+=1;self.pending=None
            return deepcopy(acknowledgement)
        except BaseException as error:
            self.failure={"type":type(error).__name__,"message":str(error),
                          "attempted_position":self.position,"committed_cases":len(self.committed),
                          "extent_unknown":True}
            raise

    def finish(self, external_completion):
        self._healthy()
        need(self.pending is None and self.position==len(self.queue), "complete query panel first")
        # This is retained external evidence, never a self-issued host qualification.
        need(type(external_completion) is dict and set(external_completion)=={
            "capture_identity","all_selected_processes_exited","status"}, "external completion schema")
        need(external_completion["all_selected_processes_exited"] is True and
             external_completion["status"]=="source_only_unqualified",
             "source-only completion evidence; no authority promotion")
        identity(external_completion["capture_identity"])
        self.completed=deepcopy(external_completion)
        return {"status":STATUS,"prediction_count":len(self.rows),"case_count":len(self.committed),
                "final_commit":self.previous,"external_completion":self.completed,
                "protected_process_qualification":False}

    def captured_scoring_operands(self):
        need(self.failure is None and self.completed is not None, "outside completion before grade")
        return deepcopy(self.sessions),deepcopy(self.rows),deepcopy(self.methods)
