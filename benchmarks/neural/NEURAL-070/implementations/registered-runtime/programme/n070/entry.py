"""Enclosing original controller lifetime, through report and final projection."""
from pathlib import Path
from .core import Attempt
from .native.io import dump
from .native.resources import ControllerMeter
from .programme import compile
from .engine import Engine
from .campaign import Campaign
def execute(deployment,args,bootstrap_owner):
    owner=Attempt("entry");bootstrap_owner.children.append(owner)
    result=None;controller=None
    try:
        programme=compile(deployment,args.phase);owner.originals["programme"]=programme
        controller=ControllerMeter(programme);owner.children.append(controller)
        with controller.activate("whole_entry"):
            engine=Engine(deployment,programme,Path(args.root),controller);owner.children.append(engine)
            campaign=Campaign(deployment,programme,engine,Path(args.root));owner.children.append(campaign)
            result=campaign.run();owner.originals["result"]=result
            owner.publish("result",result,lambda:dump(Path(args.root)/"RESULT.json",result))
            owner.raise_first()
    except BaseException as error:owner.fail("entry",error)
    if controller is not None:owner.call("controller_final",controller.final,"whole_entry_final")
    owner.raise_first();return result

