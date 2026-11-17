"""Complete source-owned participant/reference campaign controller.
No candidate import and no target callback before the one global barrier.
"""
from pathlib import Path
import shutil
import time
from .common import need, digest, canonical, pin, put, load, read, tree, same_tree, relative, probabilities, Refusal, extent, encoded
from .spec import campaign, census, CORE, SUMMARY, PROFILE, REFS, LABELS, DOMAIN, INERT
from .views import summary_payload
from .journal import Journal
from .collections import Collections
from .bindings import Bindings


class Controller:
    def __init__(self, root, manifest, issuer, launcher, trusted_source, trusted_entry, inert=False):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.manifest = manifest; self.requirements = campaign(manifest); self.issuer = issuer
        self.launcher = launcher; self.trusted_source = Path(trusted_source); self.trusted_entry = trusted_entry
        self.inert = inert
        need(inert == (manifest['domain'] == INERT) and launcher.domain == manifest['domain'], 'Domain consistency')
        need(issuer.domain == manifest['domain'], 'Issuer domain')
        self.panel = issuer.panel; self.census = census(manifest, self.panel)
        self.events = Journal(self.root / 'event-index', 'controller_events', manifest['resources']['aggregate']['write_bytes'])
        self.expected_processes = Journal(self.root / 'expected-index', 'scheduled_processes')
        self.collections = Collections(self.root / 'collections')
        self.phase_counts = {}; self.programs = {}; self.banks = {}; self.candidates = {}
        self.states = Bindings(self.root / 'bindings/states.sqlite')
        self.stage_status = {}; self.started = time.monotonic(); self.tool_calls = 0
        self.reference_cache = Bindings(self.root / 'bindings/reference.sqlite')
        self.prediction_cache = Bindings(self.root / 'bindings/prediction.sqlite')
        self.summary_cache = Bindings(self.root / 'bindings/summary.sqlite')
        self.family_cache = Bindings(self.root / 'bindings/family.sqlite')
        self.shared_summaries = Bindings(self.root / 'bindings/shared-query.sqlite')
        self.target_reads = 0; self.closed = None; self.interpretation_closures = []
        self.primary_exception = None; self.secondary_failures = []; self.terminal_disposition = None
        self.terminal_stop = False; self.run_started = False
        # Reserve two largest original observation bodies plus bounded closure metadata.
        # This is a logical budget reservation, not a promise that failed storage works.
        self.terminal_reserved_bytes = 2 * launcher.records.entry_cap + (1 << 20)
        self.terminal_reserved_files = 8
        self._validate_resources()
        self.terminal_hold = {'schema': 'n054_terminal_hold_v1', 'status': 'INCOMPLETE',
            'reason': 'Campaign admitted; original process/terminal custody is unresolved until a durable final disposition.',
            'final_disposition_admitted': False, 'scientifically_qualified': False,
            'reserved_bytes': self.terminal_reserved_bytes, 'reserved_files': self.terminal_reserved_files}
        # This immutable hold exists before any scientific/participant process. If
        # even initial reserve persistence fails, construction cannot admit work.
        self._terminal_write('TERMINAL_HOLD.json', self.terminal_hold)
        try:
            self.event('S01', 'campaign_admission', {'manifest': digest(manifest), 'census': self.census})
            self._put('CAMPAIGN.json', manifest); self._put('CENSUS.json', self.census)
        except BaseException as error:
            self._remember(error, 'initial_controller_admission')
            self._finish_terminal({'status': 'INCOMPLETE', 'failure': str(error), 'scientifically_qualified': False})
            raise


    def _validate_resources(self):
        r = self.manifest['resources']
        need(set(r) == {'aggregate', 'phase_process_caps', 'solve', 'retries', 'workers', 'd_context_bytes'}, 'Resource plan schema')
        need(r['workers'] == 1 and r['retries'] == 0 and r['solve'] in ('common', 'direct'), 'Serial no-retry schedule; explicit LDA route')
        need(set(r['aggregate']) == {'processes', 'cpu_s', 'wall_s', 'read_bytes', 'write_bytes', 'retained_bytes',
                                    'files', 'tool_calls', 'model_calls', 'tokens'}, 'Whole resource axes')
        need(all(type(v) is int and v > 0 for v in r['aggregate'].values()), 'Positive aggregate limits')
        need(r['aggregate']['write_bytes'] > self.terminal_reserved_bytes and
             r['aggregate']['retained_bytes'] > self.terminal_reserved_bytes and
             r['aggregate']['files'] > self.terminal_reserved_files, 'Prospective terminal reserve required')
        need(type(r['d_context_bytes']) is int and r['d_context_bytes'] > 0, 'Full prompt context admission')
        required = {'build', 'candidate_train', 'candidate_predict', 'candidate_D', 'interpret', 'family_prepare',
                    'reference_prepare', 'reference_predict', 'summary_prepare', 'summary_control_prepare',
                    'summary_query', 'summary_predict'}
        need(set(r['phase_process_caps']) == required and all(type(v) is int and v >= 0 for v in r['phase_process_caps'].values()),
             'Every phase prospective census/cap')

    def _put(self, name, value):
        return put(self.root / name, value, self.manifest['resources']['aggregate']['write_bytes'] - self.terminal_reserved_bytes)

    def _terminal_write(self, name, value):
        # Independent of ordinary controller event/_put writers; all writes remain
        # fallible. A failed terminal write never becomes a successful disposition.
        return put(self.root / name, value, self.terminal_reserved_bytes)

    def _remember(self, error, where):
        record = {'where': where, 'type': type(error).__name__, 'message': str(error)}
        if self.primary_exception is None:
            self.primary_exception = error
            self.primary_failure_record = record
        elif error is not self.primary_exception:
            self.secondary_failures.append(record)
        self.terminal_stop = True

    def _attempt(self, where, action):
        try:
            return True, action()
        except BaseException as error:
            self._remember(error, where)
            return False, None

    def _failure_context(self):
        ok, prefix = self._attempt('failure_original_receipt_snapshot', self.launcher.records.snapshot)
        primary = self.primary_exception
        original = getattr(primary, 'original_error', primary)
        return {'primary_failure': dict(self.primary_failure_record) if primary is not None else None,
                'original_error': {'type': type(original).__name__, 'message': str(original)} if original is not None else None,
                'original_observation': getattr(primary, 'original_observation', None),
                'original_receipt_prefix': prefix if ok else {'status': 'UNAVAILABLE'},
                'original_observed_totals': dict(self.launcher.totals),
                'original_unresolved_custody': dict(self.launcher.unresolved_holds),
                'pending_original_jobs': dict(self.launcher.pending),
                'secondary_failures': list(self.secondary_failures),
                'unknown_counters_are_not_zero': True}

    def _qualification_failure(self, qualification):
        if self.primary_exception is not None:
            qualification.update(status='INCOMPLETE', failure=type(self.primary_exception).__name__ + ': ' + str(self.primary_exception))
            qualification['failure_context'] = self._failure_context()
        return qualification

    def _finish_terminal(self, qualification):
        self._qualification_failure(qualification)
        qualification['terminal_custody'] = {'status': 'PENDING', 'final_disposition_admitted': False}
        self.terminal_disposition = qualification
        final = {**qualification, 'terminal_custody': {'status': 'DURABLE_FINAL_DISPOSITION', 'final_disposition_admitted': True}}
        ok, _ = self._attempt('final_disposition_writer', lambda: self._put('FINAL_DISPOSITION.json', final))
        if ok:
            self.terminal_stop = True
            self.terminal_disposition = final
            return final
        self._qualification_failure(qualification)
        qualification['terminal_custody'] = {'status': 'UNRESOLVED_TERMINAL_HOLD', 'final_disposition_admitted': False,
            'initial_hold': 'TERMINAL_HOLD.json', 'failed_final_path_may_be_partial': 'FINAL_DISPOSITION.json'}
        # The full exception/observation remains owned even if this reserved writer
        # also fails. Never replace it with the secondary persistence exception.
        ok, _ = self._attempt('reserved_terminal_hold_writer', lambda: self._terminal_write('TERMINAL_HOLD_FINAL.json', qualification))
        if ok:
            self.terminal_disposition = qualification
            return qualification
        self._qualification_failure(qualification)
        self.terminal_disposition = qualification
        primary = self.primary_exception
        primary.controller_terminal_disposition = qualification
        primary.controller_failure_context = qualification['failure_context']
        # Preserve any launcher's original_observation exactly, with costs/context
        # exposed separately rather than overwriting its original observation type.
        raise primary


    def items(self, collection):
        return self.collections.iterate(collection)

    def event(self, stage, name, details):
        event = {'sequence': len(self.events), 'stage': stage, 'name': name,
                 'details': details, 'prior': self.events.chain,
                 'elapsed_s': time.monotonic() - self.started, 'domain': self.manifest['domain']}
        identity = self.events.append(event)
        self.stage_status[stage] = 'SOURCE_ROUTE_OBSERVED_INERT' if self.inert else 'OBSERVED_UNQUALIFIED'
        return identity

    def _budget(self, next_phase=None):
        need(not self.terminal_stop, 'Controller terminal hold prevents further work')
        need(not self.launcher.unresolved_holds, 'Unresolved original process custody')
        r = self.manifest['resources']; a = r['aggregate']; records = self.launcher.records
        need(len(records) + (next_phase is not None) <= a['processes'], 'Aggregate process ceiling')
        need(time.monotonic() - self.started <= a['wall_s'], 'Aggregate wall ceiling')
        t = self.launcher.totals
        need(t['cpu_s'] <= a['cpu_s'], 'Aggregate observed CPU ceiling')
        if next_phase: need(self.phase_counts.get(next_phase, 0) < r['phase_process_caps'][next_phase], 'Phase process cap: ' + next_phase)
        need(t['logical_request_bytes'] <= a['read_bytes'] and t['logical_output_bytes'] + self.terminal_reserved_bytes <= a['write_bytes'], 'Logical transport caps')
        need(t['physical_read_bytes'] <= a['read_bytes'] and t['physical_write_bytes'] + self.terminal_reserved_bytes <= a['write_bytes'], 'Physical IO caps')
        need(self.tool_calls <= a['tool_calls'], 'Tool call cap')
        need(t['model_calls'] <= a['model_calls'] and t['tokens'] <= a['tokens'], 'Observed model/token caps')
        if not self.inert:
            need(not t['unknown_model_counter_count'] and not t['unknown_cpu_jobs'], 'Original meter unavailable; stop before further work')
        return {'processes': len(records), 'cpu_s': t['cpu_s'], 'wall_s': time.monotonic() - self.started,
                'logical_request_bytes': t['logical_request_bytes'], 'logical_output_bytes': t['logical_output_bytes'],
                'tool_calls': self.tool_calls, 'model_calls': t['model_calls'] if not t['unknown_model_counter_count'] else None,
                'tokens': t['tokens'] if not t['unknown_model_counter_count'] else None,
                'unknown_model_counter_jobs_sample': list(t['unknown_model_counter_jobs']),
                'unknown_model_counter_count': t['unknown_model_counter_count'], 'unknown_cpu_jobs': t['unknown_cpu_jobs'],
                'physical_io_qualified': False,
                'meter_scope': 'Original actor/control observations and logical transport; controller/issuer overhead remains separately unqualified'}

    def invoke(self, phase, source, entry, request, state=None, build=None):
        self._budget(phase)
        observation_stage = 'S17' if self.requirements['standalone_R'] or phase == 'interpret' else 'S19'
        expected = {'ordinal': len(self.expected_processes), 'phase': phase,
                    'request': digest(request), 'source': digest(tree(source, 16 << 20, 512))}
        self.expected_processes.append(expected)
        self.phase_counts[phase] = self.phase_counts.get(phase, 0) + 1
        self.event(observation_stage, 'original_process_scheduled', expected)
        try:
            result = self.launcher.run(phase, source, entry, request, state, build)
        except BaseException as e:
            self._remember(e, 'original_process')
            context = self._failure_context()
            self._attempt('original_process_failed_event', lambda: self.event(observation_stage, 'original_process_failed',
                          {'expected': expected, 'error': str(e), 'failure_context': context}))
            raise
        self._budget()
        self.event(observation_stage, 'original_process_completed', {'expected': expected, 'receipt': result['receipt']})
        return result

    def trusted(self, phase, request, state=None):
        return self.invoke(phase, self.trusted_source, self.trusted_entry, {'phase': phase, **request}, state)

    def register(self, key, source, entries):
        need(key not in self.programs, 'No source replacement after registration')
        need(set(entries) == {'build', 'train', 'predict', 'interpret'}, 'Complete named source entrypoints')
        files = tree(source, 16 << 20, 512)
        for entry in entries.values():
            relative(entry); need(entry in {x['path'] for x in files}, 'Entrypoint outside source graph')
        destination = self.root / 'sources' / digest({'key': key, 'files': files})
        shutil.copytree(source, destination)
        need(tree(destination, 16 << 20, 512) == files, 'Exact frozen source snapshot')
        self.programs[key] = {'source': destination, 'files': files, 'id': digest(files), 'entries': entries}
        self.event('S09', 'A01_register', {'program': key, 'source': digest(files), 'entries': entries})

    def build_all(self):
        need({c['program'] for c in self.manifest['conditions']} == set(self.programs), 'Exactly selected programs registered before views')
        for key, program in self.programs.items():
            result = self.invoke('build', program['source'], program['entries']['build'],
                                 {'phase': 'build', 'schema': 'n054_actor_v1', 'program': program['id']})
            need(result['result'].get('status') == 'built', 'Observed successful build required')
            program['build'] = result['output']; program['build_receipt'] = result['receipt']
            self.event('S09', 'A02_build', {'program': key, 'receipt': result['receipt'],
                                         'build': digest(result['record']['outputs'])})

    def _context(self, slot, condition=None):
        # All source person/session/concept identities stay in controller-only panel.
        context = {'episode': slot['id'], 'window': slot['logical']['window'], 'arm': slot['logical']['arm'],
                   'labels': list(LABELS), 'generation': self.manifest['source_generation']}
        if condition:
            context.update({k: condition[k] for k in ('mode', 'tool', 'replicate', 'profile')})
        return context

    def _seal_state(self, result, source, training, role):
        need(result['result'].get('status') == 'prepared' and result['result'].get('state') == 'state', 'Actual state product')
        path = result['output'] / 'state'
        files = tree(path, self.launcher.limits['output_bytes'], self.launcher.limits['files'])
        need(files, 'Nonempty state; explicit constant recipes are state too')
        seal = {'source': source, 'training': training, 'files': files, 'receipt': result['receipt'],
                'environment': digest(self.manifest['environment']), 'role': role}
        sid = digest(seal); self.states[sid] = {'path': str(path), 'seal': seal}
        self.event('S11' if role == 'candidate' else ('S18' if role.startswith('summary') else 'S08'),
                   'immutable_state_seal', {'id': sid, **seal})
        return sid

    def state_path(self, sid):
        s = self.states[sid]
        same_tree(s['path'], s['seal']['files'], self.launcher.limits['output_bytes'], self.launcher.limits['files'])
        return s['path']

    def _prepare_core(self, family, slot, view):
        case = digest(slot['logical']['case']); arm = slot['logical']['arm']; window = slot['logical']['window']
        # R4 recipe ignores data. R5 depends only on exact outer training labels. Other reuse is VISUAL-only.
        if family == 'R4': key = ('R4',); training = 'CONSTANT_NO_FIT'; parts = {}; labels = []
        elif family == 'R5':
            parts = {}; labels = view['labels']; training = digest(labels); key = ('R5', case, training)
        else:
            parts = view['families']; labels = view['labels']; training = digest({'families': parts, 'labels': labels})
            key = (family, case, arm, 'VISUAL_IDENTITY' if arm == 'VISUAL' else window, training)
        if key in self.reference_cache:
            sid = self.reference_cache[key]
            self.event('S08', 'R02_R03_exact_state_reuse', {'family': family, 'slot': slot['id'], 'state': sid, 'training': training})
            return sid
        prepared = None
        if family in ('R0', 'R1', 'R2'):
            prepared = {}
            for name, values in parts.items():
                fk = (case, name, 'VISUAL_IDENTITY' if name == 'visual' else window, digest(values))
                if fk not in self.family_cache:
                    res = self.trusted('family_prepare', {'family': name, 'values': values})
                    need(res['result']['status'] == 'prepared_family', 'Actual family preparation')
                    self.family_cache[fk] = {'transform': res['result']['transform'], 'receipt': res['receipt']}
                    self.event('S08', 'R02_family_preparation', {'key': digest(fk), **self.family_cache[fk]})
                prepared[name] = self.family_cache[fk]['transform']
        result = self.trusted('reference_prepare', {'family': family, 'view': {'families': parts, 'labels': labels},
                              'prepared': prepared, 'solve': self.manifest['resources']['solve']})
        sid = self._seal_state(result, digest(tree(self.trusted_source, 16 << 20, 512)), training, 'reference')
        self.reference_cache[key] = sid
        return sid

    def _predict_core(self, family, slot, qid, state, query):
        arm = slot['logical']['arm']; case = digest(slot['logical']['case'])
        if family == 'R4': key = (family, state)
        elif family == 'R5': key = (family, state, case)
        elif arm == 'VISUAL': key = (family, state, case, digest(query['families']))
        else: key = (family, state, slot['id'], qid)
        reusable = family in ('R4', 'R5') or arm == 'VISUAL'
        if not reusable or key not in self.prediction_cache:
            result = self.trusted('reference_predict', {'family': family, 'query': query}, self.state_path(state))
            need(result['result'].get('status') == 'complete', 'References cannot abstain')
            observed = {'probabilities': probabilities(result['result']['probabilities']),
                        'receipt': result['receipt'], 'original_query': digest(query)}
            if reusable: self.prediction_cache[key] = observed
        else: observed = self.prediction_cache[key]
        self.event('S08', 'R04_R06_admit_materialize', {'family': family, 'slot': slot['id'], 'query': qid,
                   'permitted_payload': digest(query), 'state': state, 'original': observed,
                   'pure_reuse': 'exact VISUAL inputs or fixed constant/prior' if arm == 'VISUAL' or family in ('R4', 'R5') else 'none'})
        return {'id': qid, 'status': 'complete', **observed, 'input': digest(query), 'state': state}

    def _collect(self, kind, owner, slot, rows, profile):
        need(kind in ('candidate', CORE, SUMMARY), 'Typed collector')
        ids = [r['id'] for r in rows]
        need(sorted(ids) == sorted(slot['query_ids']) and len(ids) == len(set(ids)), 'Exact complete query membership')
        known = self.launcher.records
        abstention = False
        for row in rows:
            need(known.contains(row['receipt']) and known.get(row['receipt'])['exit_code'] == 0 and known.get(row['receipt'])['failure'] is None,
                 'Original successful inference observation required')
            role = known.get(row['receipt'])['role']
            need((kind == CORE and role == 'reference_predict') or
                 (kind == SUMMARY and role == 'summary_predict') or
                 (kind == 'candidate' and role in ('candidate_predict', 'candidate_D')), 'Producer/collector role confusion')
            if row['status'] == 'abstain':
                need(kind == 'candidate' and row.get('probabilities') is None, 'No reference abstention or fallback numerics')
                abstention = True
            else:
                need(row['status'] == 'complete', 'Terminal output status'); probabilities(row['probabilities'])
        artifact = {'kind': kind, 'owner': owner, 'slot': slot['id'], 'profile': profile,
                    'domain': self.manifest['domain'], 'generation': self.manifest['source_generation'],
                    'label_order': list(LABELS), 'status': 'abstain' if abstention else 'complete', 'rows': rows,
                    'target_commitment': self.panel['target_commitment']}
        folder = self.root / 'artifacts' / digest([kind, owner])
        descriptor = put(folder / (slot['id'] + '.json'), artifact, 128 << 20)
        receipt = self.event('S13' if kind == 'candidate' else ('S08' if kind == CORE else 'S18'),
                             'A06_collect' if kind == 'candidate' else ('R07_collect' if kind == CORE else 'DC07_collect'),
                             {'kind': kind, 'owner': owner, 'slot': slot['id'], 'artifact': descriptor,
                              'original_inference': [r['receipt'] for r in rows], 'status': artifact['status']})
        return {'path': str(folder / (slot['id'] + '.json')), **descriptor, 'receipt': receipt,
                'status': artifact['status'], 'slot': slot['id'], 'owner': owner, 'kind': kind, 'profile': profile}

    def _seal_bank(self, kind, artifacts):
        wanted = set(map(tuple, self.census['references'][kind]))
        need({(a['owner'], a['slot']) for a in artifacts} == wanted and len(artifacts) == len(wanted), 'Full required bank census')
        need(all(a['status'] == 'complete' and a['kind'] == kind and a['profile'] == PROFILE[kind] for a in artifacts), 'Complete same-profile bank')
        for a in artifacts: read(a['path'], 128 << 20, {k: a[k] for k in ('bytes', 'sha256')})
        collection = self.collections.seal(['bank', kind], iter(artifacts))
        bank = {'kind': kind, 'profile': PROFILE[kind], 'census': digest(self.census['references'][kind]),
                'artifacts': collection, 'generation': self.manifest['source_generation'],
                'original_receipts': self.launcher.records.snapshot(),
                'resources': self._budget(), 'target_commitment': self.panel['target_commitment'],
                'domain': self.manifest['domain']}
        bank['seal'] = digest(bank)
        # Controller observes seal completion after producing the bank, not a bank's self-assertion.
        bank['original_seal_receipt'] = self.event('S08' if kind == CORE else 'S18',
                                                  'R08_bank_sealed' if kind == CORE else 'DC08_bank_sealed',
                                                  {'seal': bank['seal'], 'kind': kind, 'artifacts': len(artifacts)})
        self._put('BANK_' + kind + '.json', bank)
        self.banks[kind] = bank

    def core_bank(self):
        need(CORE in self.requirements['banks'], 'Inactive full-core bank')
        self.event('S08', 'R01_full_census', {'expected': len(self.census['references'][CORE])})
        artifacts = []
        for slot in self.panel['slots']:
            view = self.issuer.training(slot['id'])
            for family in REFS[CORE]:
                state = self._prepare_core(family, slot, view)
                rows = [self._predict_core(family, slot, qid, state, self.issuer.query(slot['id'], qid))
                        for qid in slot['query_ids']]
                artifacts.append(self._collect(CORE, family, slot, rows, PROFILE[CORE]))
        self._seal_bank(CORE, artifacts)

    def summary_bank(self):
        need(SUMMARY in self.requirements['banks'], 'Inactive summary bank')
        self.event('S18', 'DC01_full_census', {'expected': len(self.census['references'][SUMMARY])})
        artifacts = []
        for slot in self.panel['slots']:
            view = self.issuer.training(slot['id']); context = self._context(slot)
            key = (digest(slot['logical']['case']), slot['logical']['arm'],
                   'VISUAL_IDENTITY' if slot['logical']['arm'] == 'VISUAL' else slot['logical']['window'],
                   digest({'families': view['families'], 'labels': view['labels']}))
            if key not in self.summary_cache:
                result = self.trusted('summary_prepare', {'view': {'families': view['families'], 'labels': view['labels']}})
                state = self._seal_state(result, digest(tree(self.trusted_source, 16 << 20, 512)), key[-1], 'summary_projection')
                self.summary_cache[key] = (state, result['result']['summary'])
            state, summary = self.summary_cache[key]
            controls = {}
            for family in REFS[SUMMARY]:
                result = self.trusted('summary_control_prepare', {'family': family, 'summary': summary})
                controls[family] = self._seal_state(result, digest(tree(self.trusted_source, 16 << 20, 512)),
                                                    digest(summary), 'summary_control')
            control_rows = {f: [] for f in REFS[SUMMARY]}
            for qid in slot['query_ids']:
                query = self.issuer.query(slot['id'], qid)
                projected = self.trusted('summary_query', {'query': query}, self.state_path(state))
                need(projected['result']['status'] == 'summary', 'Actual frozen projection result')
                payload = summary_payload(projected['result']['payload'])
                need(payload['classes'] == summary, 'Exact serialized training summary')
                need(len(canonical(payload)) <= self.manifest['resources']['d_context_bytes'], 'No D truncation fallback')
                # Exact same payload object/bytes goes to both controls and later D candidate.
                result_pin = next(x for x in projected['record']['outputs'] if x['path'] == 'result.json')
                shared = {'payload_path': str(projected['output'] / 'result.json'),
                          'payload_file': {k: result_pin[k] for k in ('bytes', 'sha256')},
                          'projection': state, 'receipt': projected['receipt'], 'digest': digest(payload)}
                self.shared_summaries[(slot['id'], qid)] = shared
                self.event('S18', 'DC04_shared_query', {'slot': slot['id'], 'query': qid,
                           'payload': shared['digest'], 'projection': state, 'receipt': projected['receipt']})
                for family in REFS[SUMMARY]:
                    result = self.trusted('summary_predict', {'family': family, 'payload': payload},
                                          self.state_path(controls[family]))
                    need(result['result'].get('status') == 'complete', 'Summary controls cannot abstain')
                    row = {'id': qid, 'status': 'complete', 'probabilities': probabilities(result['result']['probabilities']),
                           'receipt': result['receipt'], 'input': digest(payload), 'state': controls[family]}
                    self.event('S18', 'DC05_DC06_materialize', {'family': family, 'slot': slot['id'], **row})
                    control_rows[family].append(row)
            for family in REFS[SUMMARY]:
                artifacts.append(self._collect(SUMMARY, family, slot, control_rows[family], PROFILE[SUMMARY]))
        self._seal_bank(SUMMARY, artifacts)

    def summary_for(self, slot_id, query_id):
        shared = self.shared_summaries[(slot_id, query_id)]
        original = self.launcher.records.get(shared['receipt'])
        output = next(x for x in original['outputs'] if x['path'] == 'result.json')
        need({k: output[k] for k in ('bytes', 'sha256')} == shared['payload_file'] and
             original['role'] == 'summary_query', 'Original summary projection lineage')
        result = load(shared['payload_path'], self.launcher.limits['output_bytes'], shared['payload_file'])
        need(result['status'] == 'summary', 'Actual summary product')
        payload = summary_payload(result['payload'])
        need(digest(payload) == shared['digest'], 'Unchanged shared serialized input')
        return {**shared, 'payload': payload}

    def _tool(self, family, slot, qid):
        need(CORE in self.banks and family in REFS[CORE], 'Only sealed full-core current-query tools')
        bank = self.banks[CORE]
        artifact = next(a for a in self.items(bank['artifacts']) if a['owner'] == family and a['slot'] == slot['id'])
        data = load(artifact['path'], 128 << 20, {k: artifact[k] for k in ('bytes', 'sha256')})
        rows = [r for r in data['rows'] if r['id'] == qid]; need(len(rows) == 1, 'Admitted current query only')
        self.tool_calls += 1; self._budget()
        self.event('S12', 'reference_tool_served', {'family': family, 'slot': slot['id'], 'query': qid,
                   'bank': bank['seal'], 'original_probability': digest(rows[0]['probabilities']), 'call': self.tool_calls})
        return {'family': family, 'probabilities': rows[0]['probabilities']}

    def candidate_condition(self, condition):
        program = self.programs[condition['program']]; mode = condition['mode']
        need(mode in 'PID', 'Predictive condition')
        artifacts = []
        for slot in self.panel['slots']:
            context = self._context(slot, condition); state = None
            if mode in 'PI':
                result = self.invoke('candidate_train', program['source'], program['entries']['train'],
                                     {'phase': 'train' if mode == 'P' else 'investigate', 'context': context,
                                      'view': self.issuer.training(slot['id']), 'tools': ['offline_numerical'],
                                      'training_reference_probes': 'NOT_SELECTED'}, build=program['build'])
                self.event('S10', 'A03_actual_training_or_investigation', {'condition': condition['id'], 'slot': slot['id'], 'original_receipt': result['receipt']})
                state = self._seal_state(result, program['id'], result['record']['request']['sha256'], 'candidate')
            rows = []
            for qid in slot['query_ids']:
                transcript = []; calls = 0
                if mode == 'D':
                    shared = self.summary_for(slot['id'], qid)
                    request = {'phase': 'diagnose', 'context': context, 'query_id': qid,
                               'payload': shared['payload'], 'tools': []}
                    input_id = shared['digest']; phase = 'candidate_D'
                else:
                    query = self.issuer.query(slot['id'], qid)
                    request = {'phase': 'predict', 'context': context, 'query': query,
                               'tools': list(REFS[CORE]) if condition['tool'] == 'NUM_REF' else [], 'tool_transcript': []}
                    input_id = digest(query); phase = 'candidate_predict'
                while True:
                    result = self.invoke(phase, program['source'], program['entries']['predict'], request,
                                         self.state_path(state) if state else None, program['build'])
                    response = result['result']
                    if response.get('status') != 'tool_call': break
                    need(mode in 'PI' and condition['tool'] == 'NUM_REF', 'Tool unavailable in this mode/profile')
                    need(set(response) == {'status', 'family'}, 'Only current-query fixed reference invocation')
                    calls += 1; need(calls <= self.launcher.limits['tool_calls'], 'Per-query call cap')
                    transcript.append(self._tool(response['family'], slot, qid))
                    request = {**request, 'tool_transcript': transcript}
                status = response.get('status')
                need(status in ('complete', 'abstain'), 'Typed candidate terminal status')
                if status == 'complete':
                    need(set(response) == {'status', 'probabilities'}, 'Unknown output fields')
                    probs = probabilities(response['probabilities'])
                else:
                    need(set(response) == {'status'}, 'Abstention has no fallback numbers'); probs = None
                self.event('S18' if mode == 'D' else 'S12', 'DA01_no_tools_candidate' if mode == 'D' else 'A05_one_query', {'condition': condition['id'], 'slot': slot['id'], 'query': qid, 'receipt': result['receipt'], 'input': input_id, 'state': state})
                rows.append({'id': qid, 'status': status, 'probabilities': probs, 'receipt': result['receipt'],
                             'input': input_id, 'state': state, 'program': program['id'],
                             'query_tool_receipts': calls})
            artifacts.append(self._collect('candidate', condition['id'], slot, rows, condition['profile']))
        self.candidates[condition['id']] = self.collections.seal(['candidate', condition['id']], iter(artifacts))

    def audit_artifact(self, descriptor):
        artifact = load(descriptor['path'], 128 << 20, {k: descriptor[k] for k in ('bytes', 'sha256')})
        need(all(artifact[k] == descriptor[k] for k in ('kind', 'owner', 'slot', 'profile', 'status')),
             'Artifact envelope mismatch')
        need(artifact['target_commitment'] == self.panel['target_commitment'] and
             artifact['generation'] == self.manifest['source_generation'], 'Target/source substitution')
        need(self.events.contains(descriptor['receipt']), 'Missing original collector')
        observed = self.events.get(descriptor['receipt'])
        need(observed['details']['artifact'] ==
             {k: descriptor[k] for k in ('bytes', 'sha256')}, 'Original collector receipt missing or changed')
        known = self.launcher.records
        for row in artifact['rows']:
            need(known.contains(row['receipt']), 'Original inference receipt absent after collection')
            record = known.get(row['receipt'])
            need(record.get('exit_code') == 0 and record.get('failure') is None, 'Original actor failed')
            expected = next((r for r in record['outputs'] if r['path'] == 'result.json'), None)
            need(expected is not None, 'Original result not inventoried')
            response = load(self.launcher.root / record['job'] / 'out/result.json', 16 << 20,
                            {k: expected[k] for k in ('bytes', 'sha256')})
            need(response['status'] == row['status'] and
                 response.get('probabilities') == row.get('probabilities'), 'Probabilities differ from actual producer bytes')
            if row.get('state') is not None: self.state_path(row['state'])
        return artifact

    def resource_closure(self, stage='S19', event_name='pre_target_resource_closure', reserve_bytes=0, reserve_files=0):
        records = self.launcher.records
        need(len(records) == len(self.expected_processes), 'Missing original process completion')
        need(all(r.get('original_observer') and r.get('failure') is None and r.get('exit_code') == 0 for r in records),
             'Failed or missing original completion')
        for expected, record in zip(self.expected_processes, records):
            need(expected['phase'] == record['role'] and expected['request'] == record['request']['sha256'] and
                 expected['source'] == record['source'], 'Exact launch/completion join')
        self.events.verify(self.events.snapshot())
        self.expected_processes.verify(self.expected_processes.snapshot())
        self.launcher.records.verify(self.launcher.records.snapshot())
        stats = self._budget()
        caps = self.manifest['resources']['aggregate']
        retained = [extent(self.root), extent(self.launcher.root)]
        retained_bytes = sum(x['bytes'] for x in retained); retained_files = sum(x['files'] for x in retained)
        reserve_bytes += self.terminal_reserved_bytes; reserve_files += self.terminal_reserved_files
        need(retained_bytes + reserve_bytes <= caps['retained_bytes'] and retained_files + reserve_files <= caps['files'], 'Total retained source/process quota')
        stats.update({'terminal_reserved_bytes': reserve_bytes, 'terminal_reserved_files': reserve_files, 'retained_bytes': retained_bytes, 'retained_files': retained_files,
                      'original_receipts': self.launcher.records.snapshot(), 'events': self.events.snapshot(),
                      'scheduled_processes': self.expected_processes.snapshot()})
        if not self.inert:
            need(all(r.get('cgroup_original_observations') for r in records), 'Original aggregate cgroup evidence required')
            need(all(r.get('model_calls') is not None and r.get('tokens') is not None for r in records),
                 'Model/token observer not qualified; no zero substitution')
        need(stats['model_calls'] <= self.manifest['resources']['aggregate']['model_calls'] and
             stats['tokens'] <= self.manifest['resources']['aggregate']['tokens'], 'Aggregate model budget')
        self.event(stage, event_name, stats)
        return stats

    def barrier(self):
        req = self.requirements
        need(req['prediction'], 'R-only performs no new target/bank barrier')
        need(set(self.banks) == set(req['banks']), 'Missing active typed bank or unexpected bank')
        for kind, bank in self.banks.items():
            need(bank['kind'] == kind and bank['profile'] == PROFILE[kind] and
                 bank['artifacts']['count'] == len(self.census['references'][kind]), 'Bank type/census mismatch')
            observed_seal = self.events.get(bank['original_seal_receipt'])
            need(observed_seal['details']['seal'] == bank['seal'] and observed_seal['details']['kind'] == kind, 'Original bank-seal observation')
            body = {k: v for k, v in bank.items() if k not in ('seal', 'original_seal_receipt')}
            need(digest(body) == bank['seal'], 'Bank changed after seal')
            self.launcher.records.verify(bank['original_receipts'])
            for a in self.items(bank['artifacts']): self.audit_artifact(a)
        expected = set(map(tuple, self.census['candidates']))
        candidate_artifacts = [a for values in self.candidates.values() for a in self.items(values)]
        need({(a['owner'], a['slot']) for a in candidate_artifacts} == expected and len(candidate_artifacts) == len(expected),
             'Every selected candidate slot required globally')
        for a in candidate_artifacts:
            need(a['kind'] == 'candidate' and a['status'] == 'complete', 'Candidate abstention: null/no target')
            self.audit_artifact(a)
        stats = self.resource_closure()
        closure = {'manifest': digest(self.manifest), 'census': digest(self.census),
                   'candidates': self.collections.seal(['global_candidates'], iter(candidate_artifacts)),
                   'banks': {k: v['seal'] for k, v in self.banks.items()}, 'resources': digest(stats),
                   'target_commitment': self.panel['target_commitment'], 'domain': self.manifest['domain']}
        self.closed = digest(closure)
        self.event('S14', 'A07_global_campaign_sealed', {'seal': self.closed, **closure})
        self._put('GLOBAL_SEAL.json', {'seal': self.closed, **closure})
        return self.closed

    def validate_closed(self):
        need(self.closed is not None, 'No global seal')
        original = load(self.root / 'GLOBAL_SEAL.json', 64 << 20)
        need(original['seal'] == self.closed and original['manifest'] == digest(self.manifest) and
             original['census'] == digest(self.census), 'Frozen campaign changed')
        body = {k: v for k, v in original.items() if k != 'seal'}
        need(digest(body) == self.closed, 'Global seal bytes')
        need(original['banks'] == {k: v['seal'] for k, v in self.banks.items()}, 'Bank substitutions')
        for bank in self.banks.values():
            observed = self.events.get(bank['original_seal_receipt'])
            need(observed['details']['seal'] == bank['seal'], 'Original bank seal observation changed')
            need(digest({k: v for k, v in bank.items() if k not in ('seal', 'original_seal_receipt')}) == bank['seal'],
                 'Sealed bank changed')
            self.launcher.records.verify(bank['original_receipts'])
            for a in self.items(bank['artifacts']):
                self.audit_artifact(a)
        for a in self.items(original['candidates']):
            self.audit_artifact(a)
        need(len(self.launcher.records) == len(self.expected_processes) and
             all(r.get('failure') is None for r in self.launcher.records), 'Original receipt set changed')

    def current_admission(self):
        """Current original custody/resources after expensive validation, before capability use."""
        need(not self.launcher.pending and not self.launcher.owned_children and
             not self.launcher.unresolved_holds, 'Original process ownership unresolved')
        caps = self.manifest['resources']['aggregate']
        retained = [extent(self.root), extent(self.launcher.root)]
        need(sum(r['bytes'] for r in retained) + self.terminal_reserved_bytes <= caps['retained_bytes'] and
             sum(r['files'] for r in retained) + self.terminal_reserved_files <= caps['files'], 'Current retained source/process quota')
        # This final budget/deadline check follows the filesystem census. No event
        # write, whole receipt scan or other expensive step follows before callback.
        return self._budget()

    def grade(self, grader):
        need(self.closed is not None, 'Targets closed before full campaign seal')
        need(not self.inert or getattr(grader, 'inert_control', False), 'Inert controls cannot execute scientific scoring')
        self.validate_closed()  # Revalidate without minting a different seal or replaying completion.
        self.current_admission()  # Last work before invoking the target capability.
        targets = self.issuer.protected_targets(); self.target_reads += 1
        need(pin(canonical(targets)) == self.panel['target_commitment'], 'Exact physical target bank/support commitment')
        self.event('S15', 'protected_target_opened', {'seal': self.closed, 'target_commitment': self.panel['target_commitment']})
        self.current_admission()  # Target read/commitment/event work may itself exhaust a limit.
        report = grader(self, targets)
        report.update({'campaign': digest(self.manifest), 'domain': self.manifest['domain'],
                       'global_seal': self.closed, 'banks': {k: v['seal'] for k, v in self.banks.items()},
                       'exposure': self.manifest['exposure'], 'scientifically_qualified': False,
                       'submission_ready': False, 'resources': self._budget()})
        self.event('S16', 'complete_tagged_report', {'report': digest(report)})
        self._put('REPORT.json', report)
        return report

    def interpret(self, condition, report, prior=None):
        need(condition['mode'] == 'R', 'Interpretation condition')
        if self.requirements['standalone_R']:
            need(prior is not None and set(prior) == {'report', 'source', 'status', 'exposure', 'costs', 'admission'}, 'Admitted prior provenance')
            need(prior['report'] == pin(canonical(report)) and prior['admission']['status'] == 'INDEPENDENTLY_ADMITTED',
                 'Exact immutable prior report admission')
        else: need(self.closed is not None and report['global_seal'] == self.closed, 'Current globally sealed report')
        program = self.programs[condition['program']]
        result = self.invoke('interpret', program['source'], program['entries']['interpret'],
                             {'phase': 'interpret', 'report': report, 'prior_provenance': prior,
                              'limits': ['No irreducible information, causal onset, population generalization, or preferred-sign reward'],
                              'tools': []}, build=program['build'])
        claims = result['result']
        from .report import check_claims
        checks = check_claims(claims, report)
        self.event('S17', 'A09_interpretation', {'source': program['id'], 'claims': claims,
                   'original_receipt': result['receipt'], 'arithmetic': checks, 'scientific_rubric_score': None})
        return {'claims': claims, 'arithmetic': checks, 'scientific_rubric_score': None, 'receipt': result['receipt']}

    def interpretation_closure(self, baseline, report):
        """Separate S17 closure; R-only never activates scientific S19 or a target bank."""
        stats = self.resource_closure('S17', 'interpretation_resource_closure')
        after = self.launcher.records.snapshot()
        closure = {'schema': 'n054_interpretation_cost_closure_v2', 'report': digest(report),
                   'mode': 'standalone_R' if self.requirements['standalone_R'] else 'post_predictive_R',
                   'before_process_prefix': baseline['prefix'], 'after_process_prefix': after,
                   'additional_processes': after['count'] - baseline['prefix']['count'],
                   'additional_observed_cpu_s': stats['cpu_s'] - baseline['resources']['cpu_s'],
                   'additional_logical_request_bytes': stats['logical_request_bytes'] - baseline['resources']['logical_request_bytes'],
                   'additional_logical_output_bytes': stats['logical_output_bytes'] - baseline['resources']['logical_output_bytes'],
                   'additional_model_calls': stats['model_calls'] - baseline['resources']['model_calls'],
                   'additional_tokens': stats['tokens'] - baseline['resources']['tokens'],
                   'terminal_whole_campaign_resources': stats, 'scientific_seal_unchanged': self.closed,
                   'build_cost_policy': 'R-only includes all source builds. Mixed builds already charged before target seal; new interpretation costs are the prefix difference, never charged twice.'}
        self.launcher.records.verify(after)
        self._put('INTERPRETATION_COST_CLOSURE.json', closure)
        self.interpretation_closures.append(closure)
        return closure

    def interpretation_failure_closure(self, baseline, report, primary):
        retention = {}; retention_error = None
        try:
            for name, root in [('campaign', self.root), ('processes', self.launcher.root)]: retention[name] = extent(root)
        except BaseException as error: retention_error = str(error)
        budget_error = None
        try: self._budget()
        except BaseException as error: budget_error = str(error)
        closure = {'schema': 'n054_interpretation_failure_closure_v2', 'status': 'INCOMPLETE',
                   'primary_failure': primary, 'before_process_prefix': baseline['prefix'],
                   'after_process_prefix': self.launcher.records.snapshot(),
                   'report': digest(report) if report is not None else None,
                   'original_observed_totals': dict(self.launcher.totals), 'retention': retention,
                   'retention_error': retention_error, 'budget_error': budget_error,
                   'unknown_counters_are_not_zero': True, 'scientific_seal_unchanged': self.closed}
        closure['failure_context'] = self._failure_context()
        self.interpretation_closures.append(closure)
        self._attempt('interpretation_failure_event', lambda: self.event('S17', 'failed_interpretation_resources_preserved', closure))
        self._attempt('interpretation_failure_writer', lambda: self._put('INTERPRETATION_FAILURE_CLOSURE.json', closure))

    def run(self, grader=None, prior_report=None, prior_provenance=None):
        need(not self.run_started and not self.terminal_stop, 'No campaign retry after terminal ownership')
        self.run_started = True
        failure = None; report = None; interpretations = []; interpretation_started = False
        baseline = {'prefix': None, 'resources': None}
        try:
            baseline = {'prefix': self.launcher.records.snapshot(), 'resources': self._budget()}
            self.build_all()
            if self.requirements['prediction']:
                for s in ('S02', 'S03', 'S04', 'S05', 'S06', 'S07'):
                    self.event(s, 'issuer_admission_binding', {'panel': digest(self.panel),
                               'qualification': 'INERT_PLACEHOLDER' if self.inert else self.issuer.admission})
                if CORE in self.requirements['banks']: self.core_bank()
                if SUMMARY in self.requirements['banks']: self.summary_bank()
                for condition in self.manifest['conditions']:
                    if condition['mode'] in 'PID': self.candidate_condition(condition)
                self.barrier()
                if grader is not None: report = self.grade(grader)
            else:
                need(prior_report is not None and prior_provenance is not None, 'R-only requires prior report')
                report = prior_report
            if self.requirements['prediction']:
                baseline = {'prefix': self.launcher.records.snapshot(), 'resources': self._budget()}
            for condition in self.manifest['conditions']:
                if condition['mode'] == 'R':
                    need(report is not None, 'R waits for complete report')
                    interpretation_started = True
                    interpretations.append(self.interpret(condition, report, prior_provenance))
            if self.requirements['interpret']:
                self.interpretation_closure(baseline, report)
        except BaseException as e:
            self._remember(e, 'campaign_work')
            failure = type(self.primary_exception).__name__ + ': ' + str(self.primary_exception)
            if self.requirements['standalone_R'] or interpretation_started:
                self._attempt('interpretation_failure_closure', lambda: self.interpretation_failure_closure(baseline, report, failure))
            context = self._failure_context()
            self._attempt('failed_campaign_event', lambda: self.event('S20', 'failed_campaign_preserved', {'failure': failure,
                       'missing_banks': sorted(set(self.requirements['banks']) - set(self.banks)),
                       'failure_context': context, 'target_reads': self.target_reads}))
        qualification = {'status': 'INCOMPLETE' if failure else ('INERT_CONTROL_ONLY' if self.inert else 'SOURCE_RUN_UNQUALIFIED'),
                         'failure': failure, 'target_reads': self.target_reads,
                         'reference_artifacts': {k: v['artifacts']['count'] for k, v in self.banks.items()},
                         'candidate_artifacts': sum(v['count'] for v in self.candidates.values()), 'interpretations': interpretations,
                         'interpretation_cost_closures': self.interpretation_closures,
                         'stage_observations': self.stage_status, 'all_29_gates_remain_open': True,
                         'scientifically_qualified': False, 'canonical_task_count_delta': 0}
        self._qualification_failure(qualification)
        self._attempt('qualification_event', lambda: self.event('S20', 'qualification_limits', qualification))
        self._qualification_failure(qualification)
        provisional = {**qualification, 'status': 'PROVISIONAL_PENDING_TERMINAL' if self.primary_exception is None else 'INCOMPLETE'}
        self._attempt('provisional_disposition_writer', lambda: self._put('DISPOSITION.json', provisional))
        if self.primary_exception is None:
            try:
                terminal_reserve = (1 << 20) + sum(len(b) for b in encoded({**qualification, 'terminal_resource_closure': '0' * 64}))
                terminal = self.resource_closure('S20', 'terminal_resource_closure', terminal_reserve, 16)
                self._put('TERMINAL_RESOURCE_CLOSURE.json', terminal)
                qualification['terminal_resource_closure'] = digest(terminal)
            except BaseException as error:
                self._remember(error, 'terminal_resource_closure')
                context = self._failure_context()
                self._attempt('terminal_resource_failure_event', lambda: self.event('S20', 'terminal_resource_failure_preserved', context))
        return self._finish_terminal(qualification)
