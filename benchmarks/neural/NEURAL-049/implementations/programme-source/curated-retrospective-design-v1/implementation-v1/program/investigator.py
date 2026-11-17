"""Actual source authoring and case investigation over HTTPS and fresh analysis workers."""
from pathlib import Path
from core import need, encoded, pin, publish, fresh, capture, parse, finite
from contracts import recipe as admit_recipe, identity
from provider import Provider
from authority import method as method_admission
from actor_context import setup

PROTOCOL = '''You are authoring a complete NEURAL-049 curated, event-cued retrospective decoder.
Return exactly one JSON action: python {action,code,rationale}, submit {action,source,recipe,claim}, or stop {action,reason}.
Study values are absent during global authorship. Case investigation receives all permitted training rows and the complete label-free held-day batch, never held targets. No case state may cross contexts.
A computational method defines fit(batch,context)->(safe_state,features) and predict(state,batch,typed_provider_values,context)->finite float64[n_query,3]. Endpoints are angle degrees, magnitude pixels, onset speed pixels/s in that order. All released rows/channels/5000 samples remain. batch train/query lists contain ids,axis,mask,offsets,x unless C,context unless N; training parts alone have all3 labels. Whole held-day label-free batch operations are permitted equally for frozen F code and I code. Safe state contains primitive JSON and primitive contiguous numpy arrays only, no pickle. features maps frozen provider-slot names to full float64[row_count,input_width] arrays. Recipe schema neural049_candidate_recipe_v1 has provider_slots (name,prompt,input_width,output_width,axis training/query/one),state_array_cap,state_array_bytes,state_metadata_bytes. F later provider responses are numeric values only; no query-generated executable code or interpreted plan/DSL. Query-dependent method authoring is I. Predeclared numerical TTA in F is permitted. T1, when selected, adds numeric tool train/query matrices, with training outputs explicitly in-sample. Claim must describe actual exposure/method limits; no causal, continuous-confidence or population-transfer claim. Output support is complete, not a convenient subset.
For an I global policy, submit.source is a source-only instruction policy rather than an executable case method. Later fresh case investigation must submit the executable method above. An analysis action runs its exact Python in a fresh isolated worker; the variable batch is None globally, otherwise the complete permitted case. stdout is bounded feedback. Its content is candidate-influenced, not independent performance or usage evidence.'''


class Investigator:
    def __init__(self, a, captured, budget, transport, artifacts, journal, quota):
        self.a, self.captured, self.budget = a, captured, budget
        self.transport, self.artifacts, self.record, self.quota = transport, artifacts, journal, quota

    def provider(self, seed_identity, profile):
        selection = {**self.a['provider'], 'seed_identity': list(seed_identity)}
        return Provider(selection, self.budget, self.record, self.a['provider_profiles'][profile], self.quota)

    def run(self, operation, mode, root, provider, cutoff, *, policy=None, view=None, tool=None, mounts=(), source_only=False, setting):
        source_context = setup(self.a,setting['view'],setting['tool']); context_pin = pin(encoded(source_context))
        messages = [{'role':'system','content':PROTOCOL}, {'role':'user','content':encoded({
            'stage':'source_only_policy' if source_only and mode == 'I' else 'source_only_program' if source_only else 'fresh_case_method',
            'view': setting['view'], 'tool_access':setting['tool'],'source_context':source_context,
            'policy':policy, 'same_complete_batch_access':True}).decode()}]
        analyses = []; transcript = []
        for ordinal in range(provider.limits['steps']):
            self.budget.tick(cutoff)
            action, text, raw = provider.complete(messages, [operation], cutoff)
            transcript.append({'ordinal':ordinal,'response':pin(raw),'text':text})
            messages.append({'role':'assistant','content':text})
            if action['action'] == 'stop': raise ValueError('explicit author stop: '+action['reason'])
            if action['action'] == 'submit':
                plan = admit_recipe(action['recipe']); source = action['source'].encode()
                desc = publish(root/'METHOD.py', source, self.budget, readonly=True)
                rp = publish(root/'RECIPE.json', encoded(plan), self.budget, readonly=True)
                cp = publish(root/'CLAIM.json', encoded(action['claim']), self.budget, readonly=True)
                admission = method_admission(self.a, operation, desc, rp, cp, 'I_policy' if source_only and mode == 'I' else mode,
                                             self.budget, cutoff, context_pin)
                tp = publish(root/'TRANSCRIPT.json', encoded(transcript), self.budget, readonly=True)
                result = {'source':{'path':str(root/'METHOD.py'),'pin':desc}, 'recipe':plan,
                          'recipe_descriptor':{'path':str(root/'RECIPE.json'),'pin':rp},
                          'claim':{'path':str(root/'CLAIM.json'),'pin':cp}, 'admission':admission,
                          'transcript':{'path':str(root/'TRANSCRIPT.json'),'pin':tp},'analyses':analyses,
                          'source_only':source_only,'mode':mode,'source_context':context_pin}
                self.budget.tick(cutoff); return result
            code = action['code'].encode(); codepath = root/('analysis-'+str(ordinal)+'.py')
            codepin = publish(codepath, code, self.budget, readonly=True)
            req = {'source_only':source_only,'view':None if view is None else view['descriptor'],
                   'view_cap':self.a['resources']['view_bytes'],'tool_bank':tool,
                   'code':{'path':'/inputs/ANALYSIS.py','pin':codepin},'code_cap':131072,'feedback_bytes':32768}
            produced = self.transport.invoke(identity(['analysis',operation,ordinal]), 'analysis', 'analysis', req,
                list(mounts)+[{'source':str(codepath),'destination':'/inputs/ANALYSIS.py','pin':codepin,'bytes_cap':codepin['bytes']}],
                expected={n:self.a['resources']['state_bytes'] for n in ('FEEDBACK.json','WORK.json','RECEIPT.json')},
                paired_seed=[*provider.selection['seed_identity'],'analysis',ordinal], cutoff=cutoff)
            feedback = self.artifacts.json(Path(produced['output'])/'FEEDBACK.json', produced['native']['artifacts']['FEEDBACK.json'],32768+4096)
            analyses.append(produced); messages.append({'role':'user','content':encoded(feedback).decode()})
        raise ValueError('complete author step allowance exhausted without method')

    def fixed(self, method, features, provider, operation, cutoff):
        need(features['schema'] == 'neural049_fixed_features_v1', 'actual frozen feature producer')
        values = {}
        for ordinal, slot in enumerate(method['recipe']['provider_slots']):
            rows = features['slots'][slot['name']]
            need(type(rows) is list and all(type(r) is list and len(r) == slot['input_width'] for r in rows),
                 'complete fixed feature matrix')
            for row in rows:
                for x in row: finite(x)
            if not rows:
                values[slot['name']] = []; continue
            messages = [{'role':'system','content':slot['prompt']+' Return only JSON {"values":[finite numbers]} in row-major order.'},
                        {'role':'user','content':encoded({'features':rows,'output_shape':[len(rows),slot['output_width']]}).decode()}]
            action, _, _ = provider.complete(messages, [operation,'fixed',ordinal], cutoff, mode='fixed_numeric')
            raw = action['values']; need(len(raw) == len(rows)*slot['output_width'], 'full fixed reply, no sampled rows')
            values[slot['name']] = [raw[i*slot['output_width']:(i+1)*slot['output_width']] for i in range(len(rows))]
        return values
