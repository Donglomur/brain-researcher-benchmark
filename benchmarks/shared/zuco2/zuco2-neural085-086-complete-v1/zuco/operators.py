"""Complete source-derived operator and native-gap ledger."""
from pathlib import Path
from .io import decode,read,need,digest
ROOT=Path(__file__).resolve().parents[1]
NATIVE_UNRESOLVED={"O07":"Original acquisition/synchronization source and full ABI","O08":"Original gaze word-bound/nonreading/filter procedure","O10":"Original Automagic1.4.6 interpolation/ICA/MARA settings","O11":"Original band filters/Hilbert/rejection units/support","O12":"Every original word-window difference role and geometry","O13":"Original frontal-pair field and hemisphere sign","O14":"Original raw-cleaned same-sentence validation operator","O15":"Original exact screen/event/source join","O16":"Original full eye-tracking validation operators","O17":"Figure7 difference sign/statistic/units","O18":"FRP exact epochs/baseline/reference/rejection","O19":"Fixation bin boundaries/smoothing/edge operator"}
def catalogue():return decode(read(ROOT/"normative/OPERATOR_AND_ROLE_MAP.json",1024**2))
def initial():
    return {o["id"]:{"operator":o["operator"],"stage":o["stage"],"status":"required_unscorable" if o["id"] in NATIVE_UNRESOLVED else "not_started","reason":NATIVE_UNRESOLVED.get(o["id"]),"source_identity":digest(o),"evidence":[]} for o in catalogue()["operators"]}
def record(ledger,op,evidence,status="computed_unqualified"):
    need(op in ledger and evidence,"operator_evidence");need(op not in NATIVE_UNRESOLVED or status=="required_unscorable","native_operator_cannot_be_guessed",op);ledger[op]={**ledger[op],"status":status,"evidence":evidence};return ledger[op]
def native_dispositions():return [{"operator":k,"status":"required_unscorable","missing_exact_source":v,"substitute_used":False} for k,v in NATIVE_UNRESOLVED.items()]
