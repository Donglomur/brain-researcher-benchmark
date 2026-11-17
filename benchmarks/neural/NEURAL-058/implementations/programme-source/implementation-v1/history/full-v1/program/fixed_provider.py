"""Positive fixed-program provider grammar: finite numeric slots, no agent DSL."""
from core import encoded, need, finite


def execute(provider, recipe, features, episode, cutoff):
    slots=recipe['provider_slots']
    need(type(features) is dict and set(features)==set(slots),'all frozen provider slots, no dynamic calls')
    values={};records=[]
    for name in sorted(slots):
        spec=slots[name];items=features[name]
        need(type(items) is list and len(items)<=spec['feature_count'],'bounded predeclared numerical features')
        items=[finite(x) for x in items]
        # No provider-chosen tool name, executable body, prompt or dispatch loop
        # exists. The instruction is immutable in the globally frozen recipe.
        messages=[{'role':'system','content':'Return exactly one JSON object with a finite numeric values array. Do not return code, text actions, tools, plans or prompts.'},
                  {'role':'user','content':spec['instruction']+'\nRequired output length: '+str(spec['output_count'])+'\nFeatures: '+encoded(items).decode()}]
        response,text,raw=provider.complete(messages,[episode,name],cutoff,mode='fixed_numeric')
        need(len(response['values'])==spec['output_count'],'exact fixed provider output axis')
        values[name]=response['values'];records.append({'slot':name,'response_bytes':len(raw)})
    return values,records
