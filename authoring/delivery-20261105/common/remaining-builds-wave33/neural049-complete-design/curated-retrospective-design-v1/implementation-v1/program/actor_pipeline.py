"""One full held-day batch per case; matched F/I access and fresh paired D state."""
from pathlib import Path
from core import need, fresh, capture, parse, encoded, pin
from contracts import identity
from views import make
from reference_adapter import primitive, host_descriptor


class Actors:
    def __init__(self, a, captured, budget, artifacts, transport, investigator, bank, packet, table, references):
        self.a, self.captured, self.budget, self.artifacts = a, captured, budget, artifacts
        self.transport, self.investigator, self.bank = transport, investigator, bank
        self.packet, self.table, self.references = packet, table, references
        from records import Records
        root = fresh(Path(a['roots']['output'])/'actor-records',budget)
        self.policies = {}; self.results = Records(root,budget,a['resources']['record_bytes'],a['resources']['index_bytes']); self.tools = {}

    def author(self, job, cutoff):
        root = fresh(Path(self.a['roots']['output'])/'authors'/job['id'], self.budget)
        profile = self.a['provider_profiles']['global_author']
        provider = self.investigator.provider([job['policy'],'source-only','author-01'], 'global_author')
        engine = self.transport.engines['public']; engine.begin_scope(job['id'], cutoff, self.a['episode_limits']['global_author'])
        try:
            result = self.investigator.run(job['id'], job['mode'], root, provider, cutoff, source_only=True,
                                           setting={'view':job['view'],'tool':job['tool']})
            result['resources'] = engine.end_scope(job['id']); result['policy_identity'] = job['policy']
            self.policies[job['policy']] = result; return result
        except BaseException:
            engine.abort_scope(); raise

    def tool(self, job):
        fid, fit, sid = self.references.selected_fit(job['person'], job['outer'], job['endpoint'])
        actual = {**job, 'fit':fid, 'selection':sid, 'implementation':'r1', 'view':'NC'}
        result = self.references.invoke(actual)
        self.tools[(job['person'],job['outer'],job['axis'],job['endpoint'])] = job['id']
        return result

    def tool_views(self, person, held):
        value = {}; mounts = []
        for role, axis in (('train','training'),('query','query')):
            columns = {}; ids = None
            for endpoint in ('angle','magnitude','speed'):
                result = self.references.records[self.tools[(person,held,axis,endpoint)]]; tree = result['joined']['tree']
                if ids is None: ids = tree['ids']
                need(tree['ids'] == ids, 'same full three-endpoint tool rows')
                d = host_descriptor(primitive(tree['projected'],'r1'), result['produced'])
                target = '/inputs/tool/'+role+'_'+endpoint+'.npy'
                columns[endpoint] = {**d,'path':target}
                mounts.append({'source':d['path'],'destination':target,'pin':d['pin'],'bytes_cap':d['pin']['bytes']})
            value[role] = {'ids':ids,'columns':columns,'in_sample':role == 'train'}
        return value, mounts

    def case(self, job, cutoff):
        cell = job['cell']; policy = self.policies[cell['policy']]
        need(not cell['disrupted'] or cell['policy'] == cell['mode']+'_NC', 'same exact original NC source-only policy')
        profile = self.a['provider_profiles']['case']; self.budget.tick(cutoff)
        paired = [cell['policy'],job['case_id'],'author-01']
        provider = self.investigator.provider(paired, 'case')
        engine = self.transport.engines['public']; engine.begin_scope(job['id'], cutoff, self.a['episode_limits']['case'])
        root = fresh(Path(self.a['roots']['output'])/'actors'/job['id'], self.budget)
        try:
            view = make(self.a, self.packet, self.bank, self.budget, job['id'],job['person'],job['training'],[job['held']],
                        'NC_D' if cell['disrupted'] else cell['view'],'outer',policy['source']['pin'])
            tool, tool_mounts = self.tool_views(job['person'],job['held']) if cell['tool'] else (None,[])
            mounts = view['mounts']+tool_mounts
            if cell['mode'] == 'F': method = policy
            else:
                raw, _ = capture(policy['source']['path'],policy['source']['pin'],131072,self.budget,readonly=True)
                method = self.investigator.run(job['id'],'I',root,provider,cutoff,policy=raw.decode(),
                                              view=view,tool=tool,mounts=mounts,source_only=False,
                                              setting={'view':cell['view'],'tool':cell['tool']})
            # Public worker scope carries no private person/day/D flag or policy name.
            scope = {'case':view['visible']['case'],'training_ids':[x for p in view['visible']['train_parts'] for x in p['ids']],
                     'query_ids':[x for p in view['visible']['query_parts'] for x in p['ids']]}
            request = {'kind':'fit','view':view['descriptor'],'view_cap':self.a['resources']['view_bytes'],
                       'tool_bank':tool,'method':{'path':'/inputs/METHOD.py','pin':method['source']['pin']},
                       'method_cap':131072,'recipe':method['recipe'],'scope':scope,
                       'feature_bytes':self.a['resources']['view_bytes']}
            mounts += [{'source':method['source']['path'],'destination':'/inputs/METHOD.py',
                        'pin':method['source']['pin'],'bytes_cap':method['source']['pin']['bytes']}]
            required = {n:self.a['resources']['state_bytes'] for n in ('STATE.json','FEATURES.json','WORK.json','RECEIPT.json')}
            optional = {'arrays/'+str(i).zfill(8)+'.npy':method['recipe']['state_array_bytes']
                        for i in range(method['recipe']['state_array_cap'])}
            fit = self.transport.invoke(identity(['candidate-fit',job['id']]),'candidate','actor_fit',request,mounts,
                                          expected=required,optional=optional,paired_seed=paired,cutoff=cutoff)
            features = self.artifacts.json(Path(fit['output'])/'FEATURES.json',fit['native']['artifacts']['FEATURES.json'],self.a['resources']['view_bytes'])
            need(features['state'] == fit['native']['artifacts']['STATE.json'],'features produced with exact fitted state')
            replies = self.investigator.fixed(method,features,provider,job['id'],cutoff)
            req = {**request,'kind':'predict','provider_values':replies,
                   'state':{'path':'/inputs/state/STATE.json','pin':fit['native']['artifacts']['STATE.json']},'state_root':'/inputs/state'}
            model_mounts = [{'source':str(Path(fit['output'])/name),'destination':'/inputs/state/'+name,'pin':d,'bytes_cap':d['bytes']}
                            for name,d in fit['native']['artifacts'].items() if name=='STATE.json' or name.startswith('arrays/')]
            pred = self.transport.invoke(identity(['candidate-predict',job['id']]),'candidate','actor_predict',req,mounts+model_mounts,
                expected={n:self.a['resources']['state_bytes'] if n.endswith('.json') else self.a['resources']['array_bytes']
                          for n in ('RESULT.json','raw.npy','projected.npy','WORK.json','RECEIPT.json')},
                paired_seed=paired,cutoff=cutoff)
            result = self.artifacts.json(Path(pred['output'])/'RESULT.json',pred['native']['artifacts']['RESULT.json'],self.a['resources']['state_bytes'])
            need(result['ids'] == scope['query_ids'] and result['state'] == req['state'] and result['scope'] == scope,
                 'complete exact case prediction and fitted-state join')
            row = {'job':job,'policy':policy,'method':method,'view':view['result'],'selection':view['selection'],
                   'tool':tool,'fit':fit,'predict':pred,'result':result,'provider_values':replies,
                   'resources':engine.end_scope(job['id']),'provider_calls':provider.calls,
                   'provider_observed_tokens':provider.tokens,'source_only_policy_shared':True,
                   'case_state_shared':False,'paired_provider_seed_identity':paired}
            self.results[job['id']] = row; return row
        except BaseException:
            engine.abort_scope(); raise
