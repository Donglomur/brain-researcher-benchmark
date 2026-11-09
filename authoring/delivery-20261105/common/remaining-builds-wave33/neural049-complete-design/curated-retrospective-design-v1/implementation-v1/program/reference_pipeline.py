"""Complete reference fit/consumer/selection execution, with actual producer edges."""
from pathlib import Path
from core import need, encoded, pin
from contracts import CONFIGS, FAMILIES, identity
from schedule import support
from views import make, numeric_parts
from reference_adapter import configuration, join_output, primitive, host_descriptor
from operative import source as effective_source


class References:
    def __init__(self, a, captured, budget, artifacts, transport, bank, packet, table):
        self.a, self.captured, self.budget, self.artifacts = a, captured, budget, artifacts
        self.transport, self.bank, self.packet, self.table = transport, bank, packet, table
        from records import Records
        from core import fresh
        root = fresh(Path(a['roots']['reference'])/'records',budget)
        self.records = Records(root,budget,a['resources']['record_bytes'],a['resources']['index_bytes'])
        self.fits = self.records; self.predictions = self.records; self.selections = self.records

    def identity(self, impl):
        prefix = 'references/'+impl+'/'
        files = {k: effective_source(self.captured['manifest'],k)[1] for k in self.captured['manifest']['files']
                 if k.startswith(prefix) and k.endswith('.py')}
        need(files, 'complete independently captured reference bank')
        return {'runtime': self.captured['pin'], 'implementation': impl.upper(), 'files': files,
                'effective_paths':{k:effective_source(self.captured['manifest'],k)[0] for k in files},
                'seed_contract': self.a['seed_contract'], 'numerical_contract': self.a['numerical_contract']}

    def invoke(self, job):
        impl = job['implementation']; endpoint = job['endpoint']; view = job['view']; operation = job['id']
        if job['kind'] == 'reference_select': return self.select(job)
        fitting = job['kind'] in ('reference_fit','reference_final_fit')
        if fitting:
            days = job['training']; role = 'fit_only'; query = []; training = days
        else:
            days = job['query']; role = 'query_only'; query = days; training = []
        source = self.identity(impl)
        v = make(self.a, self.packet, self.bank, self.budget, operation, job['person'], training, query,
                 view, role, pin(encoded(source)))
        batch, mounts = numeric_parts(v, 'train' if fitting else 'query', endpoint if fitting else None)
        # Remove every other-endpoint label by matching PRIVATE mount kind, not a filename guess.
        allowed = {m['target'].replace('/case/', '/inputs/case/', 1) for m in v['plan']['mounts']
                   if not m['kind'].startswith('label_') or (fitting and m['kind'] == 'label_'+endpoint)}
        mounts = [m for m in mounts if m['destination'] in allowed]
        env = self.a['numerical_environments'][impl]
        req = {'schema': 'neural049_'+impl+'_request_v1', 'operation': 'fit' if fitting else 'predict',
               'source_identity': source, 'environment': env, 'batch': batch, 'assigned_days': days,
               'assigned_ids': support(self.table, job['person'], days), 'input_roots': ['/inputs']}
        if fitting:
            ordinal = job.get('configuration')
            if ordinal is None: ordinal = self.selections[job['selection']]['value']['selected'][job['family']]
            req['configuration'] = configuration(impl, ordinal)
            req['scope'] = {'task': 'NEURAL-049', 'implementation': impl.upper(), 'person': job['person'],
                            'view': view, 'endpoint': endpoint, 'training_days': days, 'training_ids': req['assigned_ids'],
                            'base_generation': self.a['base_generation'], 'axis': batch['parts'][0]['axis'],
                            'input_identity': {'batch': batch, 'packet': self.a['packet'], 'view_source': v['selection']['source_policy'],
                                               'view': view, 'bank': self.a['bank']['manifest']},
                            'source_identity': source, 'environment': env}
            profile = 'reference_fit'
        else:
            fit = self.fits[job['fit']]; req['state'] = fit['joined']['container_document']
            req['input_roots'].append(fit['produced']['container_output'])
            mounts += self.transport.remount(fit['produced']); profile = 'reference_predict'
        required, optional = self.transport.reference_plan(req['operation'])
        produced = self.transport.invoke(operation, 'reference', profile, req, mounts,
                                          implementation=impl, expected=required, optional=optional)
        actual_req = produced['request_value']
        joined = join_output(produced, actual_req, self.artifacts, impl, self.a['resources']['state_bytes'])
        row = {'job': job, 'view': v['result'], 'view_selection': v['selection'], 'produced': produced, 'joined': joined}
        if fitting:
            row['joined']['tree'] = {k:joined['tree'][k] for k in ('schema','meta')}
        self.records[operation] = row; return row

    def select(self, job):
        impl, endpoint, view, person, held = (job[k] for k in ('implementation','endpoint','view','person','outer'))
        days = [r['day'] for r in self.table[person] if r['day'] != held]
        rows = []; mounts = []; targets = {}
        for configuration_id in CONFIGS:
          for day in days:
            excluded = sorted([held,day]); cache_role = None if self.a['cache'] else held
            fid = identity(['inner-fit',[impl,endpoint,view,person,excluded,configuration_id,cache_role]])
            pid = identity(['inner-predict',fid,held,day]); record = self.predictions[pid]; j = record['job']
            need(j['kind'] == 'reference_inner_predict' and j['id'] == pid, 'exact complete ordered inner consumer')
            tree = record['joined']['tree']; d = primitive(tree['projected'], impl)
            # The original output namespace is unchanged, so all state/result pins
            # remain literal edges rather than a reserialized fitted object.
            mounts += self.transport.remount(record['produced'])
            rows.append({'configuration': j['configuration'], 'day': j['query'][0], 'ids': tree['ids'],
                         'projected': d, 'prediction_operation': j['id'], 'fit_operation': j['fit']})
        need(len(rows) == len(CONFIGS)*len(days), 'complete inner graph before selection')
        for day in days:
            original = next(x for x in self.packet['manifest']['days'] if x['person'] == person and x['day'] == day)
            d = original['labels'][endpoint]; desc = {'bytes':d['bytes'],'sha256':d['sha256']}
            path = '/inputs/labels/'+str(day)+'.npy'
            targets[str(day)] = {'ids':original['ids'], 'array': {'path':path,'pin':desc,'shape':d['shape'],'dtype':d['dtype']}}
            mounts.append({'source':self.bank.source(d['path'], desc),'destination':path,'pin':desc,'bytes_cap':desc['bytes']})
        req = {'scope': {k:job[k] for k in ('implementation','endpoint','view','person','outer')},
               'held_day':held,'validation_days':days,'rows':rows,'targets':targets}
        required = {n:self.a['resources']['selection_bytes'] for n in ('SELECTION.json','WORK.json','RECEIPT.json')}
        produced = self.transport.invoke(job['id'], 'selection', 'reference_select', req, mounts, expected=required)
        value = self.artifacts.json(Path(produced['output'])/'SELECTION.json', produced['native']['artifacts']['SELECTION.json'],
                                    self.a['resources']['selection_bytes'])
        need(value['scope'] == req['scope'] and value['consumer_rows'] == rows and value['targets'] == targets,
             'actual complete selection producer/input edges')
        row = {'job':job,'value':value,'produced':produced}
        self.records[job['id']] = row; return row

    def selected_fit(self, person, held, endpoint, view='NC'):
        sid = identity(['selection','r1',endpoint,view,person,held]); selection = self.selections[sid]['value']
        family = selection['strongest']; fid = identity(['final-fit','r1',endpoint,view,person,held,family])
        return fid, self.fits[fid], sid
