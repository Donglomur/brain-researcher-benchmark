"""Future complete prepared-cohort custody and exact selected-unit staging.

Reads only admitted source metadata/public train/query packets. Private choice
mapping bodies are exclusively owned by the later closed-batch grader.
"""
from pathlib import Path
from regional_custody import need, parsed, encoded, pin, read, write
from regional_scope import StudyScope, CANONICAL

CURRENT = {'bytes': 131043, 'sha256': 'abb6e17b38999ddb6cf66af2100be4fcd1cdf7697fd0e3379a7888de13726225'}


class Cohort:
    def __init__(self, binding_bytes, cohort_bytes, assets_bytes, scope, *, public_root, budget, validator):
        need(type(scope) is StudyScope and pin(binding_bytes) == CURRENT, 'Exact retained input binding and G1 scope')
        binding = parsed(binding_bytes)
        need(pin(cohort_bytes) == binding['authorities']['cohort']
             and pin(assets_bytes) == binding['authorities']['assets'], 'Exact complete cohort/asset source bodies')
        cohort, assets = parsed(cohort_bytes), parsed(assets_bytes)
        need(len(binding['roster']) == len(cohort['roster']) == len(assets['sessions']) == 39,
             'All original sessions before packet access')
        need(binding['partition_rows'] == {'fit': 6014, 'validation': 1994, 'query': 2042}, 'Original complete support')
        self.scope, self.binding, self.roster, self.assets = scope, binding, cohort['roster'], assets
        self.root, self.budget, self.validator = public_root, budget, validator
        self.rows = []
        for i, (source, row, prepared) in enumerate(zip(binding['roster'], self.roster, assets['sessions']), 1):
            need(source['ordinal'] == row['ordinal'] == prepared['ordinal'] == i
                 and source['session'] == row['session'] == scope.canonical['sessions'][i-1]['session']
                 and source['mouse'] == row['mouse'] == scope.canonical['sessions'][i-1]['mouse']
                 and source['session_token'] == row['session_token'] == prepared['session_token'],
                 'Same full source-to-opaque-session identity')
            self.rows.append(prepared)
        self.source_pin = pin(binding_bytes)

    def admit_all_manifests(self):
        for ordinal in range(1,40):
            documents={};lengths={}
            for arm in ('context_wheel','context_wheel_neural'):
                documents[arm]={};lengths[arm]={}
                for phase in ('fitval','query'):
                    raw,doc,_=self.manifest(ordinal,arm,phase)
                    documents[arm][phase]=doc;lengths[arm][phase]=len(raw)
            self.validator.validate_panel(documents,lengths)
        return {'sessions':39,'public_manifests':156,'private_mapping_body_reads':0}

    def manifest(self, ordinal, arm, phase):
        need(type(ordinal) is int and 1 <= ordinal <= 39
             and arm in ('context_wheel', 'context_wheel_neural') and phase in ('fitval', 'query'), 'Original packet address')
        descriptor = self.rows[ordinal-1]['public_manifests'][arm][phase]
        raw = read(self.root, 'public/'+descriptor['path'], {k: descriptor[k] for k in ('bytes','sha256')}, self.budget)
        doc = parsed(raw); self.validator.validate_manifest(doc)
        source = self.binding['roster'][ordinal-1]
        need(doc['session_token'] == source['session_token'] and doc['arm'] == arm and doc['phase'] == phase,
             'Packet/session/arm/phase source join')
        if phase == 'query':
            need(doc['case_tokens'] == self.roster[ordinal-1]['query_tokens'], 'Every original opaque query')
        else:
            n = source['partition_rows']
            need(doc['case_splits'] == ['fit']*n['fit']+['validation']*n['validation'], 'Complete chronological train/validation')
        return raw, doc, 'public/'+descriptor['path'].rsplit('/',1)[0]

    def original(self, ordinal, arm, phase):
        raw, doc, directory = self.manifest(ordinal, arm, phase)
        members = {name: read(self.root, directory+'/'+name,
                    {k: descriptor[k] for k in ('bytes','sha256')}, self.budget)
                   for name, descriptor in doc['files'].items()}
        return {'manifest_bytes': raw, 'manifest': doc, 'members': members, 'selection_private': None}

    def prepare(self, bundle, phase, *, subset, modules, np):
        """Real future projection using captured unchanged feature/codec methods."""
        arm = 'context_wheel' if bundle['kind'] == 'whole' and bundle['side'] == 'context' else 'context_wheel_neural'
        original = self.original(bundle['ordinal'], arm, phase)
        if bundle['kind'] == 'whole':
            return original
        result = subset.project(self.scope.plan, bundle['pair'], bundle['ordinal'], bundle['seed'], bundle['side'],
            original['members'], original['manifest'], support=modules['support'], np=np,
            ref=modules['reference'], choice=modules['choice'], validator=modules['validator'],
            worker=modules['worker'], tick=self.budget.tick)
        raw = encoded(result['manifest'])
        need(len(raw)<=len(original['manifest_bytes']) and all(len(body)<=len(original['members'][name])
             for name,body in result['members'].items()),
             'Prospective original uncompressed-member capacity bound; refuse whole route, never thin data')
        return dict(result, manifest_bytes=raw)

    def extent_rows(self):
        """Target-free deterministic preallocation, no neural arrays decoded.

        The original exporter uses np.savez, not compressed archives. The new
        selected arrays never grow; prepare() still enforces the declared member
        bound rather than guessing serialized extents. Source capture bounds
        are not advertised as actual projected bytes. Feature bytes describe
        selected output matrices, not the projection's peak live allocation.
        """
        from regional_scope import bundles
        cached = {}
        for b in bundles(self.scope):
            arm = 'context_wheel' if b['kind'] == 'whole' and b['side'] == 'context' else 'context_wheel_neural'
            key = b['ordinal'], arm
            if key not in cached:
                cached[key] = [self.manifest(b['ordinal'], arm, phase)[:2] for phase in ('fitval','query')]
            phases = cached[key]
            k = phases[0][1]['unit_count']
            if b['kind'] == 'regional':
                k = self.scope.plan.select(b['pair'], b['ordinal'], b['seed'])['K']
            columns = 23 + (5*k if arm == 'context_wheel_neural' else 0)
            yield {'key': b['key'], 'fit_bytes': len(phases[0][0])+sum(x['bytes'] for x in phases[0][1]['files'].values()),
                   'query_bytes': len(phases[1][0])+sum(x['bytes'] for x in phases[1][1]['files'].values()),
                   'feature_bytes': 8*columns*sum(len(x[1]['case_tokens']) for x in phases)}


def stage_packet(prepared, destination, budget):
    need(not any(Path(destination).iterdir()), 'Fresh isolated input directory')
    files = {'MANIFEST.json': prepared['manifest_bytes'], **prepared['members']}
    for name, raw in files.items():
        write(destination, name, raw, budget)
    return {name: pin(raw) for name, raw in files.items()}
