"""Finite complete condition/arm/case plan, reserved before source exposure."""
from .core import need,digest
from .protocol import PARTICIPANTS,CONDITIONS,ARMS,protocol_identity
from .native.resources import Budget
def compile(deployment,phase):
    body=deployment.require().body
    need(phase in("prepare","evaluate","literal_a"),"Explicit complete pipeline phase")
    jobs=[]
    if phase=="evaluate":
        for condition in CONDITIONS:
            for arm in ARMS:
                for p in PARTICIPANTS:
                    for fold in range(5):
                        for step in range(body["max_steps"]):
                            # A frozen script can use the same finite number of calls;
                            # adaptive replacements are allowed only in the other condition.
                            key="/".join((condition,arm,p,str(fold),str(step)))
                            jobs.append({"id":key,"condition":condition,"arm":arm,"participant":p,"fold":fold,"step":step,"operation":"participant"})
        for p in PARTICIPANTS:
            for fold in range(5):jobs.append({"id":"REFERENCE/"+p+"/"+str(fold),"arm":"REFERENCE","participant":p,"fold":fold,"operation":"reference"})
        for condition in CONDITIONS:
            for arm in ARMS:jobs.append({"id":"SCORE/"+condition+"/"+arm,"arm":"REFERENCE","condition":condition,"scored_arm":arm,"operation":"score"})
    elif phase=="prepare":
        for operation in("convert","features","prepare"):jobs.append({"id":"PREPARE/"+operation,"arm":"REFERENCE","operation":operation})
    else:jobs=[{"id":"LITERAL_A","arm":"REFERENCE","operation":"literal_a"}]
    budget=Budget(body["resource_plan"]["total"])
    for i,job in enumerate(jobs):
        cap=body["caps"][job["operation"]];job["public_id"]="n070-"+str(i)+"-"+digest(job)[:16]
        job["resource_reservation"]=budget.reserve(job["id"],cap,cap["output_bytes"],body["terminal_bytes"],body["terminal_files"])
    plan={"body":{"phase":phase,"jobs":jobs,"resource_plan":body["resource_plan"],"protocol":protocol_identity()},
          "identity":None,"budget":budget}
    plan["identity"]=digest(plan["body"]);return plan

