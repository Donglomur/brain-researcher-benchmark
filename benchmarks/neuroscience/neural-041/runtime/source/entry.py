"""Whole original owner: qualification, preparation, exposure, campaign, report."""
from pathlib import Path
from core import Budget,need,parse,encoded,capture,publish,fresh
from custody import Attempt
from admission import verify_signed,source_capture
from engine import Engine
from transport import prepare_native
from projection import build
from campaign import Campaign

def run(profile,signature,public_key,origin,deadline,bootstrap_account):
    owner=Attempt('NEURAL-041-original-invocation');budget=None;engine=None;campaign=None;result=None
    owner.known_cost_prefix.append(bootstrap_account)
    try:
        verify_signed(profile,signature,public_key)
        budget=Budget(origin,deadline,profile['host_read_bytes'],profile['host_write_bytes']);owner.owned.append(budget)
        need(bootstrap_account['host_read_cap']==profile['host_read_bytes'],'same original bootstrap/read envelope')
        # Carry forward the already admitted bootstrap debit into the remaining
        # whole-invocation Budget; this does not retroactively authorize reads.
        budget.reserve_read(bootstrap_account['logical_read_reserved'])
        source_capture(profile,budget)
        for key in('operations_root','journal_root','report_root','views_root'):fresh(profile[key],budget)
        def record(row):
            owner.known_cost_prefix.append(row)
            publish(Path(profile['journal_root'])/('preparation-'+str(len(owner.known_cost_prefix))+'.json'),encoded(row),budget,readonly=True)
        engine=Engine(profile['preparation_engine'],budget,record);owner.owned.append(engine)
        private,epoch_root,receipt=prepare_native(profile,profile['source'],budget,engine)
        raw,_=capture(private['path'],private['pin'],profile['private_metadata_bytes'],budget,readonly=True);prepared=parse(raw)
        # build creates its own fresh child; the roots and all future external
        # outputs remain covered by the original owner and clock.
        views=build(prepared,epoch_root,Path(profile['views_root'])/'folds',budget,profile['worker_limits']['epoch_bytes'],profile['protocol'])
        selected=dict(profile,preparation_receipt=receipt)
        campaign=Campaign(selected,profile['source'],budget,views,private);owner.owned.append(campaign)
        result=campaign.run();owner.known_cost_prefix.append(budget.record());owner.status='complete'
        publish(Path(profile['report_root'])/'INVOCATION_COMPLETE.json',encoded(owner.summary()),budget,readonly=True)
        budget.tick()
    except BaseException as error:
        owner.failed('original_invocation',error)
    if owner.raw_first is not None:
        if engine is not None:owner.cleanup('preparation_scope_retirement',lambda:engine.abort_scope)
        if budget is not None:
            owner.cleanup('original_final_cost',lambda:lambda:owner.known_cost_prefix.append(budget.record()))
            owner.cleanup('original_failure_publication',lambda:lambda:publish(Path(profile['report_root'])/'INVOCATION_FAILED.json',encoded(owner.summary()),budget,readonly=True))
        # No str(error), no raw error substitution, no successful completion if
        # publication/cost/closure failed. Strong owner retains every occurrence.
        try:owner.raw_first.n041_owner=owner
        except BaseException as later:owner.failed('error_owner_attachment',later)
        owner.raise_first()
    return result
