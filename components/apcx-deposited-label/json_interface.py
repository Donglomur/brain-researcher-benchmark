"""Bounded JSON entry for projection audit, transparent prior and owner grading.

It launches no code, model or network request. Candidate use receives only a
participant packet. Owner grading receives a separate trusted target document;
this dispatch API is not a filesystem/process isolation mechanism.
"""
import json
import sys

import participant_core as core
import released_profile as profile
import grader

MAX_INPUT_BYTES = 256*1024*1024
MAX_OUTPUT_BYTES = 2*1024*1024


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError("duplicate JSON key")
        result[key]=value
    return result


def decode(body,limit=MAX_INPUT_BYTES):
    if type(body) is not bytes or len(body)>limit:raise ValueError("complete bounded JSON input")
    return json.loads(body.decode("utf8"),object_pairs_hook=_pairs,
                      parse_constant=lambda value:(_ for _ in ()).throw(ValueError("nonfinite JSON constant")))


def dispatch(request):
    if type(request) is not dict or request.get("profile")!=profile.PROFILE:
        raise ValueError("explicit separate deposited-label profile")
    operation=request.get("operation")
    if operation=="audit_packet":
        core.exact_keys(request,("profile","operation","packet"))
        return {"status":"VALID_TARGET_FREE_QUERY_SCHEMA","valid":profile.audit_public(request["packet"]),
                "process_isolation_established":False}
    if operation=="prior":
        core.exact_keys(request,("profile","operation","packet"))
        return {"status":"TRANSPARENT_CALIBRATION_ONLY_PRIOR","submission":profile.submission(request["packet"],profile.prior(request["packet"])),
                "competent_reference_claim":False}
    if operation=="score":
        core.exact_keys(request,("profile","operation","owner","submission"))
        return grader.grade(request["owner"],request["submission"])
    if operation=="paired_uncertainty":
        core.exact_keys(request,("profile","operation","owner","first","second"))
        a=grader.grade(request["owner"],request["first"]);b=grader.grade(request["owner"],request["second"])
        if a["primary_metric"] is None or b["primary_metric"] is None:
            return {"status":"NO_PAIRED_UNCERTAINTY_INVALID_SUBMISSION","replicates":0}
        return grader.paired_conditional_bootstrap(request["owner"],request["first"]["records"],request["second"]["records"])
    if operation=="physical_primary_status":
        core.exact_keys(request,("profile","operation"))
        return core.current_primary_status()
    raise ValueError("closed operation")


def run_bytes(body):
    result=dispatch(decode(body))
    encoded=core.canonical(result)
    if len(encoded)>MAX_OUTPUT_BYTES:raise ValueError("complete output bound")
    return encoded


def main():
    # Original owner must preserve stdin source identity and complete streams.
    body=sys.stdin.buffer.read(MAX_INPUT_BYTES+1)
    output=run_bytes(body)
    sys.stdout.buffer.write(output);sys.stdout.buffer.flush()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
