"""Fictional complete metadata and scripted adapters. No scientific file I/O."""
from collections import Counter
import hashlib
import types

KEY = b'G' * 32


class Fixture:
    def __init__(self, modules, admission):
        self.m, self.a = modules, admission
        self.canonical, self.binding = admission.canonical, admission.binding
        indexed, core = modules['indexed'], modules['core']
        clock = indexed.NativeClock(100000, 44, 100172, (), {})
        self.indices = []
        counts = Counter()
        for i in range(7345):
            rid, row = str(i % 171 + 1), i // 171
            event = {'schema': 'dosei_private_annotation_event_v1', 'visibility': 'evaluator_private',
                'source_event_id': f'recording:{rid}/row:{row}', 'recording_id': rid, 'source_row': row,
                'recognized_time_ms': clock.time(row), 'condition': core.CONDITION,
                'marker_kind': 'moaas_assessment_marker', 'moaas_grouped_ordinal': None if i % 17 == 0 else i % 5 + 1,
                'biological_person_id': None, 'assessment_onset_verified': False, 'unresolved_reason_codes': []}
            self.indices.append(indexed.make_case_index(clock, event, secret=KEY, core=core))
            counts[rid] += 1
        self.indices.sort(key=lambda x: (int(x['evaluator']['recording_id']), x['evaluator']['source_row']))
        self.by_id = {x['case_id']: x for x in self.indices}
        self.receipts = {}
        self.records = []
        for rid in sorted(counts, key=int):
            outputs = {}
            for kind, width in modules['host'].WIDTHS.items():
                size = 44 * width
                outputs[kind] = {'path': '/generated/no-arrays/recording-'+rid+'.'+modules['host'].SUFFIXES[kind],
                    'bytes': size, 'sha256': hashlib.sha256(('fictional-'+rid+kind).encode()).hexdigest(),
                    'closed_file_signature': {'st_dev': 1, 'st_ino': int(rid), 'st_size': size,
                                              'st_mtime_ns': 1, 'st_ctime_ns': 1},
                    'hash_scope': 'generated nonexistent arrays'}
            self.receipts[rid] = {'schema': 'dosei_full_eeg_member_success_v1', 'status': 'succeeded',
                'recording_id': rid, 'source_rows': 44, 'complete_source_EOF_CRC_SHA': True,
                'all_three_streams_closed_and_size_stat_checked': True, 'outputs': outputs}
            sample = next(x for x in self.indices if x['evaluator']['recording_id'] == rid)
            self.records.append({'recording_id': rid, 'clock': sample['clock'], 'cases': counts[rid]})
        self.rows = []
        coverage = Counter()
        for position, ident in enumerate(sorted(self.by_id)):
            index = self.by_id[ident]
            packet = self.packet(index)
            raw, png = self.canonical(packet), self.png(packet)
            coverage['full_interval' if index['coverage']['full_interval_recorded'] else 'short_prefix'] += 1
            if not packet['relative_time_ms']:
                coverage['empty_window'] += 1
            self.rows.append({'schema': 'dosei_paired_observation_manifest_row_v1', 'public_position': position,
                'case_id': ident, 'observation_sha256': admission.sha(raw), 'observation_bytes': len(raw),
                'default_png_sha256': admission.sha(png), 'default_png_bytes': len(png),
                'source_rows': len(packet['relative_time_ms']), 'coverage': packet['coverage'],
                'channel_counts': [{'observed': len(packet['relative_time_ms'])}, {'blank': len(packet['relative_time_ms'])}],
                'projection_receipt_sha256': 'd'*64, 'array_identity_binding_sha256': self.array_identity(index)})
        self.cohort = {'schema': 'dosei_complete_paired_observations_v1', 'status': 'complete',
            'condition': core.CONDITION, 'cases': 7345, 'recordings': 171,
            'execution_binding': {'scope': 'fictional generated source only'},
            'canonical_public_order': 'ascending opaque HMAC case ID',
            'public_order_label_or_outcome_dependent': False,
            'all_cases_and_both_workflows_share_disclosure': True,
            'code_and_viewer_observation_hashes_matched': True, 'source_labels_exported': False,
            'biological_person_mapping_verified': False, 'verified_pre_challenge_onset': False,
            'common_workflow_disclosure': modules['host'].DISCLOSURE,
            'common_workflow_disclosure_sha256': admission.sha(self.canonical(modules['host'].DISCLOSURE)),
            'source_temporal_coverage': dict(coverage)}
        self.im = {'schema': 'dosei_complete_private_case_index_manifest_v1', 'status': 'complete',
            'visibility': 'evaluator_private', 'condition': core.CONDITION, 'recordings': self.records}
        self.numeric = {'schema': 'dosei_complete_full_eeg_preparation_v1', 'status': 'succeeded',
                        'complete_source_recordings': 171}
        self.proof = {'schema': 'dosei_full_saved_projection_verification_v1', 'status': 'succeeded',
            'all171_projection_hashes_verified_in_one_structural_read': True,
            'recordings': [{'recording_id': rid, 'source_rows': 44,
                           'all_stream_hashes_and_structural_checks_passed': True} for rid in sorted(counts, key=int)]}
        self.success = {'schema': 'dosei_complete_paired_success_v1', 'status': 'succeeded',
            'cases': 7345, 'recordings': 171, 'all_cases_rendered': True,
            'execution_binding': self.cohort['execution_binding']}
        self.acceptance = {'schema': 'dosei_complete_paired_observation_evidence_v1',
            'independent_saved_verification': {'exit_code': 0, 'contradictory_failure_present': False,
                'all_case_rows_order_source_joins_counts_and_closed_hashes_verified': True}, 'construction': {}}
        self.rebuild()

    def named(self, role, raw):
        return {'path': '/generated/metadata/'+role, **self.binding(raw)}

    def rebuild(self):
        """Coherent outer rebinding for negative controls; does not fix semantic rows."""
        a = self.a
        members = {rid: self.canonical(value)+b'\n' for rid, value in self.receipts.items()}
        links = [{'recording_id': rid, 'receipt': self.named('member-'+rid, raw)} for rid, raw in members.items()]
        self.numeric['complete_member_receipts'] = links
        self.cohort['native_member_bindings'] = links
        for record in self.records:
            record['native_receipt'] = self.named('member-'+record['recording_id'], members[record['recording_id']])
        blobs = {'key': KEY, 'index_cases': b''.join(self.canonical(x)+b'\n' for x in self.indices),
            'numeric_cohort': self.canonical(self.numeric)+b'\n', 'numeric_proof': self.canonical(self.proof)+b'\n',
            'observations': b''.join(self.canonical(x)+b'\n' for x in self.rows)}
        for field, role in (('cases', 'index_cases'), ('key', 'key'), ('numeric_cohort', 'numeric_cohort'),
                            ('verification_report', 'numeric_proof')):
            self.im[field] = self.named(role, blobs[role])
        blobs['index_manifest'] = self.canonical(self.im)+b'\n'
        for field, role in (('source_index_manifest', 'index_manifest'), ('source_case_stream', 'index_cases'),
                            ('numeric_cohort', 'numeric_cohort'), ('numeric_verification', 'numeric_proof'),
                            ('observations', 'observations')):
            self.cohort[field] = self.named(role, blobs[role])
        blobs['cohort'] = self.canonical(self.cohort)+b'\n'
        self.success['cohort'] = self.named('cohort', blobs['cohort'])
        self.success['observations'] = self.cohort['observations']
        blobs['success'] = self.canonical(self.success)+b'\n'
        self.acceptance['construction'] = {
            'complete_observation_manifest_sha256': a.sha(blobs['observations']),
            'complete_cohort_sha256': a.sha(blobs['cohort']), 'success_receipt_sha256': a.sha(blobs['success']),
            'common_disclosure_sha256': a.sha(self.canonical(self.cohort['common_workflow_disclosure']))}
        blobs['accepted_observation_evidence'] = self.canonical(self.acceptance)+b'\n'
        self.blobs, self.members = blobs, members
        self.pins = {role: a.sha(raw) for role, raw in blobs.items()}

    def packet(self, index):
        indexed, core = self.m['indexed'], self.m['core']
        clock, _, start, end, _ = indexed.validate_index(index, secret=KEY, core=core)
        rows = ((r, clock.time(r), .25, float('nan'), 0, 1) for r in range(start, end))
        return indexed.project_window(index, rows, secret=KEY, core=core, policy=self.m['numeric_policy'])

    def png(self, packet):
        return b'\x89PNG\r\n\x1a\nGENERATED-NOT-A-REAL-IMAGE'+hashlib.sha256(self.canonical(packet)).digest()

    def array_identity(self, index):
        outputs = self.receipts[index['evaluator']['recording_id']]['outputs']
        value = {kind: {key: outputs[kind][key] for key in ('bytes', 'sha256', 'closed_file_signature')}
                 for kind in ('time', 'eeg', 'quality')}
        return self.a.sha(self.canonical(value))


class Environment:
    def __init__(self, fixture, modules, data, assembler, *, retain=False):
        self.f, self.m, self.data, self.assembler = fixture, modules, data, assembler
        self.retained = {} if retain else None
        self.evidence_bytes = self.projections = self.models = self.model_closes = self.code_closes = self.code_calls = 0
        self.views = 0
    def sink(self, kind, raw):
        ref = self.m['controller'].binding(raw)
        self.evidence_bytes += len(raw)
        if self.retained is not None:
            self.retained[ref['sha256']] = raw
        return ref
    def project(self, index, receipt, **options):
        self.projections += 1
        if options['root'].as_posix() != '/generated/no-arrays' or options['secret'] != KEY:
            raise AssertionError('fictional projector received unexpected source')
        packet = self.f.packet(index)
        raw = self.f.canonical(packet)
        options['budget'].confirmed += len(packet['relative_time_ms']) * 26
        return packet, {'schema': 'dosei_host_slice_projection_receipt_v1', 'visibility': 'evaluator_private',
            'case_id': index['case_id'], 'observation_sha256': self.f.a.sha(raw), 'observation_bytes': len(raw),
            'source_rows_read': len(packet['relative_time_ms']), 'array_identity_binding_sha256': self.f.array_identity(index)}
    def renderer(self):
        env = self
        class TinyViewer:
            def __init__(self, packet, profile):
                env.views += 1
                self.packet, self.state = packet, 0
            def action(self, command):
                if command != {'action': 'view'}:
                    self.state += 1
                raw = env.f.png(self.packet) + (str(self.state).encode() if self.state else b'')
                return raw, {'observation_sha256': env.f.a.sha(env.f.canonical(self.packet))}
        return types.SimpleNamespace(TraceViewer=TinyViewer)
    def code(self, **kwargs):
        env = self
        if kwargs['process_api'] is not self.m['owned_process_v2']:
            raise AssertionError('wrong code process dependency')
        class ScriptedCode:
            def code_observation(self):
                return kwargs['observation_bytes']
            def viewer_action(self, command):
                return kwargs['viewer'](command)
            def run_tool(self, name, program):
                env.code_calls += 1
                if (name, program) != ('python', 'print(6)'):
                    raise AssertionError('only fictional fixed code requested')
                return {'status': 'ok', 'text': '6'}
            def close(self):
                env.code_closes += 1
                return env.sink('generated_code_close', b'fictional context closed')
        return ScriptedCode()
    def participant(self, arm, budget_binding):
        self.models += 1
        env = self
        context_id = hashlib.sha256(('fictional-model-'+str(self.models)).encode()).hexdigest()
        class ScriptedParticipant:
            def __init__(self):
                self.calls = 0
            def open(self, raw):
                value = env.m['controller'].strict_json(raw)
                if value['capabilities']['arm'] != arm or b'recording_id' in raw or b'moaas_grouped_ordinal' in raw:
                    raise AssertionError('public delivery leaks private scope')
                return env.sink('generated_delivery_ack', b'fictional delivery accepted')
            def respond(self, continuation):
                self.calls += 1
                if arm == 'code_enabled' and self.calls == 1:
                    return b'{"action":"tool","name":"python","input":"print(6)"}'
                if arm == 'code_enabled':
                    return b'{"status":"ok","probabilities":[0,0,1,0,0]}'
                return b'{"status":"ok","probabilities":[0.2,0.2,0.2,0.2,0.2]}'
            def close(self):
                env.model_closes += 1
                return env.sink('generated_model_close', b'fictional participant closed')
        return {'participant': ScriptedParticipant(), 'context_id': context_id,
                'setup_evidence': env.sink('generated_model_setup', b'fictional participant setup')}
    def options(self):
        c = self.m['controller']
        env = self.assembler.environment_bytes(self.m, self.data, call_wall_seconds=3, max_calls=3)
        budget = c.canonical({'schema': 'dosei_paired_controller_budget_v1', 'participant_wall_ms': 1000,
            'max_tool_calls': 3, 'participant_token_limit': 1000, 'model_configuration_sha256': 'a'*64,
            'analysis_environment_sha256': hashlib.sha256(env).hexdigest(), 'code_tools': [self.m['code_backend'].TOOL]})
        return {'budget_bytes': budget, 'participant_factory': self.participant, 'evidence_sink': self.sink,
            'clock_ms': lambda: 0, 'array_read_limit': 1432465970, 'staging_parent': '/generated/no-staging',
            'docker_executable': '/generated/forbidden/docker', 'docker_socket': '/generated/forbidden/socket',
            'call_wall_seconds': 3,
            'context_ids': [hashlib.sha256(('fictional-code-'+str(i)).encode()).hexdigest() for i in range(7345)]}
