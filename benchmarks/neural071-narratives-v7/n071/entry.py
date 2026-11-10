"""Actual source-owned entry point called inside the qualified launcher.

The launcher supplies exact ordinary input pins, private mounts, accounting
observer and execution authority. Construction has not qualified those inputs.
No callable here defaults to a local uncontained process or guesses a dependency.
"""
from .errors import need
from .policy import Qualification
from .resources import Budget
from .store import Store
from .journal import Journal
from .identity import identity
from . import codec

def reference(operation,envelope,qualification_record,qualification_pin,observer):
    qualification=Qualification(qualification_record,qualification_pin)
    qualification.require(envelope["generation"],envelope["source"])
    need(operation in ("reference-fit","reference-infer"),"reference-entry-operation")
    budget=Budget(envelope["limits"],envelope["scope"],observer)
    store=Store(envelope["root"],budget,output_prefix=envelope["output_prefix"],
                admitted_directories=envelope["input_directories"])
    journal=Journal(store,envelope["generation"],envelope["source"],envelope["context"],
                    envelope["scope"],envelope["historical_layer8_direct_consumer"])
    journal.parents[envelope["context"]]=envelope["original_parent"]
    request=codec.unpack(store,envelope["request"])
    from .worker import dispatch
    result=dispatch(operation,request,envelope["request"],store,journal)
    original=journal.require_complete()
    rid=journal.begin("worker-return","reference-result",original,{"result":True})
    result_record=store.put("worker-result-"+identity(envelope["context"])+".json",result)
    receipt=journal.finish(rid,{"result":result_record},{"kind":"worker-result-readback"})
    cost=budget.close()
    # Protected launcher return transports the original cost closure, including
    # its separately accounted stream/write/wait overhead, rather than reopening
    # a closed producer's budget to manufacture a self-referential final receipt.
    return {"result":result,"result_record":result_record,"original_receipt":receipt,"cost":cost,
            "output_artifacts":list(store.created)}

def preparation(envelope,qualification_record,qualification_pin,observer):
    qualification=Qualification(qualification_record,qualification_pin)
    qualification.require(envelope["generation"],envelope["source"])
    budget=Budget(envelope["limits"],envelope["scope"],observer);store=Store(envelope["root"],budget)
    journal=Journal(store,envelope["generation"],envelope["source"],envelope["context"],envelope["scope"],True)
    request=store.json(envelope["request"])
    from .native import Preparation
    from .prepared import assemble
    projected=Preparation(qualification,store,journal).all_scans(
        request["release"],request["sources"],request["atlas"],request["clocks"])
    # Only future selected trusted preparation reads this operator-owned key.
    # No such read occurred during source construction.
    key=store.read(request["opaque_key"])
    bank=assemble(request["release"],projected,key,store,journal)
    original=journal.require_complete();cost=budget.close()
    return {"bank":bank,"original_receipts":original,"cost":cost}

def complete(envelope,qualification_record,qualification_pin,allocator):
    qualification=Qualification(qualification_record,qualification_pin)
    binding=qualification.require(envelope["generation"],envelope["source"])
    need(envelope["prepared_bank"]==binding["prepared_bank"] and
         envelope["setup"]==binding["setup_closure"] and
         envelope["contrasts"]==binding["adopted_contrasts"],"complete-input-pins")
    reader=Store(envelope["input_root"],allocator.setup_store.budget)
    prepared=codec.unpack(reader,envelope["prepared_bank"])
    setup=reader.json(envelope["setup"])
    contrasts=reader.json(envelope["contrasts"])["differences"]
    from .programme import Programme
    return Programme(envelope["generation"],envelope["source"],qualification,allocator).run(
        prepared["census"],prepared,setup,contrasts,binding["protected_target_root"])
