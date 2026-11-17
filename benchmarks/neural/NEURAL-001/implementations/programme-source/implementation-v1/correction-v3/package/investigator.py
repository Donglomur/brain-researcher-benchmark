"""Fresh actual investigation loop with tool use and generated final program.

The tool engine must be independently qualified. This code enforces action flow,
not filesystem/network isolation or universal inference-versus-training semantics.
"""
from .protocol import canonical, require, pin_bytes, Refusal
from .provider import Provider


def investigate(*, provider, engine, method_reviewer, instruction, view_description,
                context, phase, budget, journal, cutoff, max_steps):
    require(phase in ('author','training','case'),'explicit investigator phase')
    require(type(context)is str and context,'fresh opaque context identity')
    require(type(max_steps)is int and max_steps>0,'complete bounded action count')
    # Construct fresh transcript here; there is no history/cache reuse parameter.
    messages=[{'role':'system','content':instruction},
              {'role':'user','content':canonical(view_description).decode('ascii')}]
    for step in range(1,max_steps+1):
        budget.tick(cutoff)
        action,text=provider.complete(messages,replicate=view_description['replicate'],
                person_alias=view_description.get('person_alias','global'),
                query_id=view_description.get('query_id','training' if phase=='training' else 'author'),
                cutoff=cutoff)
        messages.append({'role':'assistant','content':text})
        if action['action']=='stop':
            raise Refusal('investigator explicit failed stop')
        if action['action']=='python':
            # Code review is bounded evidence; engine mounts/read-only states and
            # one-query boundary have separate physical/provider qualifications.
            require(method_reviewer.admit_action(phase,action,view_description) is True,
                    'independent action method admission refused')
            result=engine.execute_current_action(action['code'],context=context,phase=phase,cutoff=cutoff)
            require(type(result)is dict and set(result)=={'stdout','stderr','observation_pin','usage'},
                    'bounded observed tool response required')
            require(all(type(result[k])is str for k in ('stdout','stderr')),'text-only tool feedback')
            require(len(canonical(result))<=view_description['tool_feedback_byte_cap'],'tool feedback cap')
            journal({'kind':'investigation_tool','step':step,'context':context,
                     'source_pin':pin_bytes(action['code'].encode()),'result':result})
            # No labels/scores/other-query state may be inserted by the engine.
            messages.append({'role':'user','content':canonical(result).decode('ascii')})
            continue
        require(method_reviewer.admit_submission(phase,action,view_description) is True,
                'independent submitted method admission refused')
        sealed=engine.seal_source(action['source'],action['method'],context=context,phase=phase)
        journal({'kind':'investigation_submitted','context':context,'step':step,
                 'sealed':sealed,'numeric_training_seen_by_llm':phase!='author',
                 'finite_bank_routing':False})
        return sealed
    raise Refusal('investigator exhausted complete action budget; no partial submission')
