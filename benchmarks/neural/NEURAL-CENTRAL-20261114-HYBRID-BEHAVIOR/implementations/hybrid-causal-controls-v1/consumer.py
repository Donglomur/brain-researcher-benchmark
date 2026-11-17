"""Fixture-only causal parser and predictor protocol.

The authentic private-file admission pin is intentionally absent. The original
loader can open and hash an operator-selected file, but cannot admit it.
Use only invented inputs in this public package. This is not an OS sandbox.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter, defaultdict
import hashlib
import hmac
import json
import math
import os
import stat
from pathlib import Path

FEATURES=("nL","nR","nB","rL","rR","muL","muR","gL","gR","first_visit","after_first_visit","t")
BOOLEAN=frozenset(("gL","gR","first_visit","after_first_visit"))
COUNTS=frozenset(("nL","nR","nB","rL","rR","t"))
MAIN_CASE_BYTES=200756614
MAIN_CASE_SHA256=None  # Authentic private-case admission is disabled.
MAIN_ROWS=182671
MAIN_ELIGIBLE=163135
MAIN_TRIALS=4884
GROUPS=frozenset((str(s),k) for s in range(1,21) for k in range(1,5))
class ContractError(ValueError):pass

def ordinary_input(path):
    p=Path(path)
    if not p.is_absolute() or ".." in p.parts or any(q.is_symlink() for q in (p,*p.parents)):
        raise ContractError("absolute nonlinked input")
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    f=os.fdopen(fd,"rb");s=os.fstat(f.fileno())
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:
        f.close();raise ContractError("ordinary single-link input")
    return f

def file_identity(f):
    s=os.fstat(f.fileno())
    return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

@dataclass(frozen=True)
class Decision:
    # Private keys, session/trial and action remain curator-only.
    source_row: int
    subject: str
    session: int
    trial: int
    values: tuple
    action: int
    def observation(self):
        return dict(zip(FEATURES,self.values))

def validate_observation(x):
    if not isinstance(x,dict) or set(x)!=set(FEATURES):
        raise ContractError("exact current-observation feature set required")
    for k,v in x.items():
        if k in BOOLEAN:
            if type(v) is not bool:raise ContractError("boolean feature "+k)
        elif type(v) not in (int,float) or not math.isfinite(v):
            raise ContractError("finite numeric feature "+k)
        elif k in COUNTS and (v<0 or int(v)!=v):
            raise ContractError("nonnegative count/clock "+k)
    if x["gL"]==x["gR"] or x["first_visit"]==x["after_first_visit"]:
        raise ContractError("exclusive cursor and visit flags")
    if x["rL"]>x["nL"] or x["rR"]>x["nR"]:
        raise ContractError("red exceeds observed colored")
    for side in ("L","R"):
        mu=x["mu"+side]
        if not 0<mu<1:raise ContractError("posterior range")
        # n is source 'colored': before observing a patch it can instead encode
        # the initial visible green cover. ev uses raw red+black evidence.
        # Therefore ev=(red+1)/(colored+2) is NOT a valid general invariant.
        r,n=x["r"+side],x["n"+side]
        evidence=math.isclose(mu,(r+1)/(n+2),rel_tol=1e-12,abs_tol=1e-12)
        cue=r==0 and math.isclose(mu,.5,rel_tol=1e-12,abs_tol=1e-12)
        if n>100 or not (evidence or cue):raise ContractError("source evidence/cue disjunction")
    if x["nB"]>100:raise ContractError("blocked cue range")
    return tuple(x[k] for k in FEATURES)

def validate_decisions(decisions, *, expected_eligible, expected_trials):
    if len(decisions)!=expected_eligible:raise ContractError("incomplete eligible population")
    rows=set();groups=set();trials=set();closed=set();previous=None;last_row=0
    for d in decisions:
        if type(d.source_row) is not int or d.source_row<1 or d.source_row in rows:
            raise ContractError("source row identity")
        if (d.subject,d.session) not in GROUPS or type(d.trial) is not int or d.trial<1:
            raise ContractError("group/trial identity")
        if type(d.action) is not int or d.action not in (1,2,3,4):
            raise ContractError("four-action identity")
        validate_observation(d.observation());rows.add(d.source_row)
        group=(d.subject,d.session);trial=group+(d.trial,)
        if trial!=previous:
            if trial in closed:raise ContractError("trial reentry")
            if previous is not None:closed.add(previous)
            last_row=0
        if d.source_row<=last_row:raise ContractError("within-trial source order")
        last_row=d.source_row;previous=trial;groups.add(group);trials.add(trial)
    if groups!=GROUPS or len(trials)!=expected_trials:raise ContractError("complete20x4/trial cohort")
    # Terminal decision must be the unique last scored decision in each trial.
    by_trial=defaultdict(list)
    for d in decisions:by_trial[(d.subject,d.session,d.trial)].append(d)
    for seq in by_trial.values():
        if len({d.observation()["nB"] for d in seq})!=1:
            raise ContractError("blocked cue changed within a processed trial")
        if seq[-1].action not in (3,4) or any(d.action in (3,4) for d in seq[:-1]):
            raise ContractError("terminal target chronology")
        clock=0;switched=False;cursor=None
        for d in seq:
            x=d.observation();now=x["gL"]
            changed=cursor is not None and now!=cursor
            if changed:switched=True
            clock=0 if cursor is None or changed else clock+1
            if x["t"]!=clock or x["first_visit"]!=(not switched):
                raise ContractError("source clock/visit differs from complete causal cursor history")
            cursor=now
    return tuple(decisions)

def load_accepted_private_cases(path):
    """Trusted whole adapter, future execution only. Two bounded sequential reads.

    First read authenticates the entire accepted case stream; second parses every
    source row. The original RDS, typed arrays and unrelated metadata are unused.
    """
    h=hashlib.sha256();n=0
    with ordinary_input(path) as f:
        first=file_identity(f)
        for chunk in iter(lambda:f.read(1<<20),b""):
            n+=len(chunk)
            if n>MAIN_CASE_BYTES:raise ContractError("case extent")
            h.update(chunk)
        if first!=file_identity(f):raise ContractError("input changed during authentication")
    if (n,h.hexdigest())!=(MAIN_CASE_BYTES,MAIN_CASE_SHA256):
        raise ContractError("accepted complete case identity")
    with ordinary_input(path) as f:
        if file_identity(f)!=first:raise ContractError("input changed between passes")
        second=hashlib.sha256();parsed_bytes=0
        def checked_lines():
            nonlocal parsed_bytes
            for line in f:
                parsed_bytes+=len(line);second.update(line)
                if parsed_bytes>MAIN_CASE_BYTES:raise ContractError("parsed input extent")
                yield line
        result=parse_private_stream(checked_lines(),expected_rows=MAIN_ROWS,expected_eligible=MAIN_ELIGIBLE,expected_trials=MAIN_TRIALS)
        if first!=file_identity(f) or (parsed_bytes,second.hexdigest())!=(MAIN_CASE_BYTES,MAIN_CASE_SHA256):
            raise ContractError("parsed whole input identity differs")
        return result

def parse_private_stream(lines, *, expected_rows,expected_eligible,expected_trials):
    """Trusted common parser; authentic caller fixes all counts above.

    Synthetic controls use the same parser with complete invented20x4 inputs.
    This function alone does not authenticate a biological source.
    """
    decisions=[];seen1=set();seen2=set();count=0;excluded=0
    for line in lines:
            if len(line)>65536:raise ContractError("case record bound")
            r=json.loads(line);count+=1
            if r.get("schema")!="hybrid-private-source-case-map-v1" or r.get("private_only") is not True:
                raise ContractError("private case schema")
            one,two=r.get("ct1"),r.get("ct2")
            if not one or not two or r.get("coding_mismatches"):
                raise ContractError("complete coding correspondence")
            i,j=one["source_row_1based"],two["source_row_1based"]
            if type(i) is not int or type(j) is not int or i in seen1 or j in seen2:
                raise ContractError("duplicate/invalid source row")
            seen1.add(i);seen2.add(j)
            if r["source_eligibility"]=="EXCLUDED":
                excluded+=1;continue
            if r["source_eligibility"]!="ELIGIBLE" or r["row_mapping_qualified"] is not True or r["row_mapping_problems"]:
                raise ContractError("held source row; no selective omission")
            g=r["group"]
            if type(g["subject"]) is not str or type(g["session"]) is not str or g["session"] not in ("1","2","3","4"):
                raise ContractError("canonical string participant/session")
            if type(g["trial"]) not in (int,float) or int(g["trial"])!=g["trial"]:raise ContractError("trial number")
            d=Decision(i,g["subject"],int(g["session"]),int(g["trial"]),validate_observation(r["predictors"]),r["action"])
            decisions.append(d)
    if count!=expected_rows or seen1!=set(range(1,expected_rows+1)) or seen2!=set(range(1,expected_rows+1)) or excluded!=expected_rows-expected_eligible:
        raise ContractError("incomplete whole source population")
    return validate_decisions(decisions,expected_eligible=expected_eligible,expected_trials=expected_trials)

def outer_fold(decisions, subject, held_session):
    """Offline within-person cross-session interpolation, not forecasting."""
    if (subject,held_session) not in GROUPS:raise ContractError("outer fold")
    train=tuple(d for d in decisions if d.subject==subject and d.session!=held_session)
    test=tuple(d for d in decisions if d.subject==subject and d.session==held_session)
    if not train or not test or {d.session for d in train}!={1,2,3,4}-{held_session}:
        raise ContractError("complete training/held sessions")
    if {d.source_row for d in train}&{d.source_row for d in test}:raise ContractError("row leakage")
    return train,test

def training_view(train):
    # A method may use complete training trials/labels, but no outer test keys.
    episode=0;previous=None;out=[]
    session_codes={s:i+1 for i,s in enumerate(sorted({d.session for d in train}))}
    for d in train:
        trial=(d.session,d.trial)
        if trial!=previous:episode+=1;previous=trial
        out.append({"episode":episode,"training_session_group":session_codes[d.session],
                    "observation":d.observation(),"action":d.action})
    return out

def probability_vector(p):
    if not isinstance(p,(list,tuple)) or len(p)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 or v>=1 for v in p):
        raise ContractError("four strictly positive finite probabilities required")
    s=math.fsum(p)
    if abs(s-1)>1e-9:raise ContractError("probabilities must sum to1")
    # Only roundoff-level normalization, declared identically for every method.
    return tuple(v/s for v in p)

def decode_reply(body):
    if type(body) is not bytes or len(body)>4096:raise ContractError("reply byte bound")
    def unique(items):
        out={}
        for k,v in items:
            if k in out:raise ContractError("duplicate JSON key")
            out[k]=v
        return out
    return json.loads(body,object_pairs_hook=unique,
                      parse_constant=lambda value:(_ for _ in ()).throw(ContractError("nonfinite JSON")))

class OnlineSession:
    """Trusted stop-and-wait protocol, one current query only.

    The transport must run the candidate outside this process and outside private
    data mounts. Passing this object to untrusted Python is expressly forbidden.
    It intentionally does not expose a query-list or remaining-length method.
    """
    def __init__(self, test, secret):
        if type(secret) is not bytes or len(secret)<32:raise ContractError("private token key")
        self._test=iter(test);self._secret=secret;self._pending=None
        self._previous_trial=None;self._predictions=[];self._complete=False;self._failed=False
    def next_query(self):
        if self._failed:raise ContractError("whole session aborted")
        if self._pending is not None:
            self._failed=True
            raise ContractError("commit before next observation")
        if self._complete:raise ContractError("session already complete")
        try:d=next(self._test)
        except StopIteration:self._complete=True;return None
        trial=(d.subject,d.session,d.trial);reset=trial!=self._previous_trial
        self._previous_trial=trial
        token=hmac.new(self._secret,str(d.source_row).encode(),hashlib.sha256).hexdigest()
        self._pending=(token,d)
        return {"schema":"hybrid-current-query-v1","token":token,"new_trial":reset,"observation":d.observation()}
    def commit(self, reply):
        try:
            if self._failed:raise ContractError("whole session aborted")
            if self._pending is None:raise ContractError("no current observation")
            if type(reply) is not dict or set(reply)!={"token","probabilities"}:raise ContractError("reply schema")
            token,d=self._pending
            if reply["token"]!=token:raise ContractError("out-of-order/replayed token")
            p=probability_vector(reply["probabilities"])
            self._predictions.append((d,p));self._pending=None
        except Exception:
            self._failed=True
            raise
        # No target, per-case score or completion hint is returned.
    def finished_predictions(self):
        if self._failed or not self._complete or self._pending is not None:raise ContractError("whole session unfinished or aborted")
        return tuple(self._predictions)

