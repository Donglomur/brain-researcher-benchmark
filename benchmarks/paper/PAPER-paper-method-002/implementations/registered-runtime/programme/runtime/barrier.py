"""All conditions freeze before any final target root may be opened."""
from .strict import require, digest, canonical_bytes, Root
from .profiles import CONDITIONS

class AssessmentPermit:
    def __init__(self, manifest, commits, method_freezes, publication_pin):
        require(set(commits)==set(CONDITIONS) and set(method_freezes)==set(CONDITIONS),"all four conditions required before target access")
        manifest_sha=digest(canonical_bytes(manifest))
        for condition in CONDITIONS:
            c=commits[condition]
            require(c["condition"]==condition and c["manifest_sha256"]==manifest_sha,"collection source/condition binding")
            require(c.get("all_required_jobs_collected") is True,"incomplete final collection")
            require(c["collection_commit_sha256"]==digest(canonical_bytes(c["collections"])),"collection changed")
            require([r["job_id"] for r in c["collections"]]==[j["job_id"] for j in manifest["jobs"]],"full job roster at barrier")
            require(method_freezes[condition].get("sha256") and method_freezes[condition].get("published_before_assessment") is True,"method not frozen")
        require(publication_pin.get("sha256") and publication_pin.get("bytes",0)>0,"retained immutable pre-assessment commit")
        self.manifest_sha256=manifest_sha
        self.commits=commits
        self.publication_pin=publication_pin
    def validate(self,job,condition):
        require(condition in CONDITIONS,"assessment condition")
        hits=[c for c in self.commits[condition]["collections"] if c["job_id"]==job["job_id"]]
        require(len(hits)==1 and hits[0]["contract_sha256"]==job["contract_sha256"],"uncommitted scientific output")
    def open_targets(self, authority, path):
        require(authority.receipt["target_root"]==path,"unselected target custody")
        return Root(path,private=True)

def seal(manifest, commits, method_freezes, evidence, clock):
    # Body is retained before permit construction; deadline failure cannot grant access.
    body=canonical_bytes({"manifest_sha256":digest(canonical_bytes(manifest)),
                          "commits":commits,"method_freezes":method_freezes})
    pin=evidence.write_new("all-conditions-before-assessment.json",body,8*1024*1024,clock=clock)
    return AssessmentPermit(manifest,commits,method_freezes,pin)
