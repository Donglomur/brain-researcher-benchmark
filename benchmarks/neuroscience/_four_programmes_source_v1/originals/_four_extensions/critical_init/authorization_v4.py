"""V4 execution output binding; v3 nonexecution fields and all original gates persist."""
import os
from .authorization_v3 import Selection as OriginalSelection
from .authorization import OPERATIONS
from .custody import read_pin,parse,descriptor,need,pin,encode
from four_programmes.common import closed
from four_programmes.identity import process_identity

COMMON=frozenset(("schema","issuer_role","canonical_id","phase","selected_operations",
                  "qualification_pins","scope_digest","evidence_cap_bytes","contract_bindings",
                  "census_pin","census_cap_bytes","census_content_identity","campaign_id","pre_run_subject"))
EXTRA={
 "prepare":frozenset(("run_nonce","runtime_profile","selected_commands","views","model_socket","cgroup_parent","condition","lifecycle_profile","job_output_contract")),
 "independent_reference":frozenset(("run_nonce","runtime_profile","selected_commands","views","model_socket","cgroup_parent","condition","lifecycle_profile","job_output_contract")),
 "native_reference":frozenset(("run_nonce","runtime_profile","selected_commands","views","model_socket","cgroup_parent","condition","lifecycle_profile","job_output_contract")),
 "candidate":frozenset(("run_nonce","runtime_profile","selected_commands","views","model_socket","cgroup_parent","condition","lifecycle_profile","job_output_contract")),
 "collect":frozenset(("collections","stream_cap_bytes","candidate_report_cap_bytes")),
 "grade":frozenset(("sealed_collection_pins","protected_reference_banks")),
 "report":frozenset(),
}

class Selection(OriginalSelection):
    def __init__(self,root,selected_pin,budget):
        self.root=root;self.pin=descriptor(selected_pin,2000000);self.budget=budget
        self.body=parse(read_pin(root,selected_pin,2000000,budget));b=self.body
        need(type(b) is dict,"closed selected authority")
        operations=b.get("selected_operations")
        need(type(operations) is list and len(operations)==1,"one selected operation")
        if operations[0] not in ("prepare","independent_reference","native_reference","candidate"):
            # The original v3 collect/grade/report fields and gates remain.
            super().__init__(root,selected_pin,budget)
            return
        need(b.get("schema")=="critical_init_root_operation_selection_v4","explicit output-bound v4 execution authority")
        need(b["issuer_role"]=="independent_root_controller" and b["canonical_id"]=="PAPER-FIND-050","original external issuer/canonical ID")
        need(type(b["selected_operations"]) is list and len(b["selected_operations"])==1 and
             b["selected_operations"][0] in OPERATIONS,"one original source operation")
        operation=b["selected_operations"][0]
        closed(b,COMMON|EXTRA[operation])
        subject=parse(read_pin(root,b["pre_run_subject"],2000000,budget))
        closed(subject,("schema","campaign_id","operation","authority_projection"))
        need(subject["schema"]=="critical_init_pre_run_authority_subject_v3" and
             subject["campaign_id"]==b["campaign_id"] and subject["operation"]==operation,
             "earlier fixed operation subject")
        need(subject["authority_projection"]==pin(encode({k:v for k,v in b.items() if k!="pre_run_subject"})),
             "acyclic authority projection excludes only earlier subject pin")
        if operation in ("prepare","independent_reference","native_reference","candidate"):
            need((operation=="candidate" and b["condition"] in ("paper_data","paper_data_author_code")) or
                 (operation!="candidate" and b["condition"] is None),"exact stage arm")
            need(type(b["selected_commands"]) is dict and type(b["views"]) is dict,"complete original command/view domains")
        descriptor(b["job_output_contract"],b["evidence_cap_bytes"])
        self.subject=subject
    def admit(self,operation):
        self.budget.require_operation(operation)
        # Exact unmodified original gate timing, scope and full evidence reads.
        return super().admit(operation)
    def admit_start(self,start_pin,context):
        closed(context,("lease","lease_pin","profile_pin","clock","mapping","meter","schemas"))
        start=parse(read_pin(self.root,start_pin,2000000,self.budget));lease=context["lease"]
        context["schemas"].validate("ci","StartBinding",start,context["meter"])
        need(start["authority"]==self.pin and start["authority_subject"]==self.body["pre_run_subject"] and
             start["lease"]==context["lease_pin"] and start["campaign_id"]==self.body["campaign_id"]==lease["campaign_id"] and
             start["profile"]==context["profile_pin"]==self.body["lifecycle_profile"]==lease["profile"] and
             start["census"]==self.body["census_pin"]==lease["census"] and
             start["scope_digest"]==self.body["scope_digest"],"exact actual original pre-run start")
        worker=start["worker"]
        actual=process_identity(os.getpid(),launch_nonce=lease["worker_nonce"],source=worker["source"],
                                parent_launch=worker["parent_launch"],mapping=context["mapping"],meter=context["meter"])
        need(actual==worker and worker!=start["controller"] and start["controller"]==lease["controller"],
             "this original W identity, independently observed by H, is distinct from C")
        need(start["observer_source"]==lease["observer_source"] and
             all(start[k] is True for k in ("memory_enforced","whole_CPU_enforced","aggregate_storage_enforced")),
             "selected actual whole/stage physical enforcement")
        need(context["clock"]["origin_monotonic_ns"]<=start["issued_ns"]<context["clock"]["run_deadline_ns"],
             "actual start inside unchanged original clock")
        return start
