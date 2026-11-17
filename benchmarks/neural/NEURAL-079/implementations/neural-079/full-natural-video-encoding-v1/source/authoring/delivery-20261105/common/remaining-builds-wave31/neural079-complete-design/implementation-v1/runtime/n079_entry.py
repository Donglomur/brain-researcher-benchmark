"""Concrete role composition; deployment activation is independently selected."""
import importlib
import os
import sys
from ach_resource_common import collect_errors, bounded_encode
from n079_common import require, fields, identity, error_record
from n079_effects import EffectContext, Journal, AuthorityClient
from n079_endpoint_owner import RoleEndpoints
from n079_jobs import ChargedWireLedger
from n079_observer import open_directory
from n079_products import read_index, write_index

WORK = {'features': 'raw-all17-features', 'grams': 'feature-grams', 'issuer': 'custody-issuer',
        'provider': 'provider-proxy', 'grader': 'target-last-grader', 'references': 'reference/sub-01/measured'}


def numeric(module_name, context, loader):
    required = context.numeric_source_pins['r1' if module_name == 'n079_numeric_r1' else 'r2']
    require(loader.modules[module_name]['pin'] == required, 'actual exact independently frozen numerical implementation')
    return importlib.import_module(module_name)


def producer(context, role, config, repository, output_fd, loader):
    fields(config['role_payload'], ('input_index',))
    selected = read_index(context, repository, config['role_payload']['input_index'], WORK.get(role, role))
    require(selected['study_pin'] == context.effect_admission['study_pin'] and selected['source_pin'] == context.source_pin,
            'complete source/study producer input-index join')
    payload = selected['payload']; primary = numeric('n079_numeric_r1', context, loader)
    independent = numeric('n079_numeric_r2', context, loader)
    limits = context.numeric_limits
    if role == 'assembler':
        from n079_preparation import PreparationProducer
        instance = PreparationProducer(context, repository, primary, output_fd, limits, config['coordinate_block'])
        error = None
        try:
            return instance.run(payload)['index']
        except BaseException as exc:
            error = exc; raise
        finally:
            instance.close(error)
    if role == 'features':
        from n079_features import FeatureExtractor
        instance = FeatureExtractor(context, repository, payload['selection'], limits)
        result = instance.produce(payload['videos'], output_fd, payload['lineage'])
        return write_index(context, output_fd, {'schema': 'n079_full_features_index_v1', 'source_pin': context.source_pin,
            'study_pin': context.effect_admission['study_pin'], 'array': result, 'feature_outputs': 17, 'videos': 1102}, 'raw-all17-features')
    if role == 'grams':
        from n079_grams import GramBuilder
        from n079_arrays import MatrixReader, MatrixWriter
        from n079_plan import admit_study_metadata
        parts = admit_study_metadata(payload['study']); reader = None; error = None; result = {}
        try:
            reader = MatrixReader(context, repository, payload['raw_features'], limits, 'feature-grams')
            builder = GramBuilder(context, reader, primary, limits, config['feature_block'])
            for partition in parts:
                state = builder.partition(partition); record = {'partition': partition, 'identity': state['identity'], 'train': [], 'cross': []}
                for side in ('train', 'cross'):
                    for layer, array in enumerate(state[side]):
                        rows = partition['train'] if side == 'train' else partition['other']
                        lineage = {'rows_pin': identity(rows, context.encoding_limits),
                            'columns_pin': identity(partition['train'], context.encoding_limits),
                            'lineage_pin': identity({'feature_identity': state['identity'], 'side': side, 'layer': layer,
                                                    'moments': state['moments']}, context.encoding_limits)}
                        writer = MatrixWriter(context, output_fd, '%s-%s-layer%d.f64' % (partition['id'], side, layer),
                            array.shape[0], array.shape[1], '<f8', limits, 'feature-grams', lineage)
                        inner = None
                        try:
                            writer.append_columns(0, array); record[side].append(writer.finish())
                        except BaseException as exc:
                            inner = exc; raise
                        finally:
                            writer.close(inner)
                record['moments'] = state['moments']; result[partition['id']] = record
            return write_index(context, output_fd, {'schema': 'n079_full_gram_index_v1', 'source_pin': context.source_pin,
                'study_pin': context.effect_admission['study_pin'], 'partitions': parts, 'grams': result}, 'feature-grams')
        except BaseException as exc:
            error = exc; raise
        finally:
            if reader is not None:
                reader.close(error)
    if role == 'references':
        from n079_references import ReferenceProducer
        preparation = read_index(context, repository, payload['preparation_index'], WORK[role])
        grams = read_index(context, repository, payload['gram_index'], WORK[role])
        require(preparation['study_pin'] == grams['study_pin'] == context.effect_admission['study_pin'], 'same full reference study')
        targets = {name: {(row['person'], row['signal']): row for row in rows} for name, rows in preparation['reference_targets'].items()}
        # Final query target descriptors exist only in protected preparation;
        # the reference material catalog is independently minimized to fitting
        # and inner-validation objects before this process is released.
        for rows in targets.values():
            require(len(rows) == 12, 'all12 exact reference target heads')
        actual_grams = {k: {name: row[name] for name in ('partition', 'train', 'cross', 'identity')} for k, row in grams['grams'].items()}
        instance = ReferenceProducer(context, repository, primary, independent, output_fd, limits, config['coordinate_block'])
        result = instance.run(grams['partitions'], actual_grams, targets)
        return write_index(context, output_fd, {'schema': 'n079_full_reference_index_v1', 'source_pin': context.source_pin,
            'study_pin': context.effect_admission['study_pin'], 'result': result,
            'preparation_pin': payload['preparation_index'], 'gram_pin': payload['gram_index']}, WORK[role])
    raise ValueError('unknown trusted scientific producer')


def run(config, loader, ready_fd, bootstrap_cost):
    fields(config, ('execution_enabled', 'module_manifest_pin', 'context', 'endpoint_selection', 'budget',
                    'journal', 'authority', 'repository', 'output', 'services', 'role_payload', 'numeric_limits',
                    'numeric_source_pins', 'coordinate_block', 'feature_block', 'terminal_output_limit'))
    require(config['execution_enabled'] is True, 'inactive role before admitted effects')
    context = None; service = None; endpoints = None; repository = None; output_fd = None; first = None; result = None
    acquired = []; terminal = {'schema': 'n079_actual_role_return_v1', 'status': 'incomplete', 'result': None}
    try:
        context = EffectContext(config['context']); role = context.role; terminal['role'] = role
        # Full configuration authority is detached: actual outer FileAuthority
        # -> OwnedRoles release -> immutable gate -> bootstrap exact bytes.
        # A custody receipt embedded in config cannot hash that same config.
        # The independent outer return join is mandatory for study admission.
        terminal['configuration_custody'] = 'requires_actual_outer_release_gate_bootstrap_and_return_join'
        context.numeric_limits = config['numeric_limits']; context.numeric_source_pins = config['numeric_source_pins']
        endpoints = RoleEndpoints(context, config['endpoint_selection'])
        work = WORK.get(role, role)
        context.ledger.charge(work, {'source_read_bytes': sum(bootstrap_cost.values())}, 'actual known bootstrap source/metadata reads')
        if role == 'observer':
            from n079_observer import ObserverService
            service = ObserverService(context, config['role_payload'], endpoints)
            acquired.append(('observer service', service.close))
        else:
            context.bind_budget(config['budget'], endpoints)
        journal = config['journal']; fields(journal, ('directory', 'name', 'maximum_bytes'))
        context.journal = Journal(journal['directory'], journal['name'], context, work, journal['maximum_bytes'])
        acquired.append(('role journal', context.journal.close))
        context.ledger.charge(work, {'write_bytes': config['terminal_output_limit'], 'log_bytes': config['terminal_output_limit']},
                              'prospective whole role terminal-stream reservation before services/cleanup')
        context.authority = AuthorityClient(context, config['authority'], endpoints)
        context.journal.append('actual_role_bootstrap', {'source_pin': context.source_pin, 'known_source_bytes': bootstrap_cost,
                                                       'source_modules': sorted(loader.modules), 'role': role})
        if config['repository'] is not None:
            from linux_backend import MaterialRepository
            fields(config['repository'], ('root', 'catalog', 'logical_limits'))
            wire = ChargedWireLedger(context, config['repository']['logical_limits']); wire.work_id = work
            repository = MaterialRepository(config['repository']['root'], config['repository']['catalog'], wire)
            acquired.append(('role material directory', lambda: os.close(repository.fd)))
        if config['output'] is not None:
            fields(config['output'], ('path', 'identity'))
            output_fd = open_directory(config['output']['path'])
            acquired.append(('role output directory', lambda: os.close(output_fd)))
            st = os.fstat(output_fd)
            require({'device': st.st_dev, 'inode': st.st_ino} == config['output']['identity'], 'same independently selected owned output root')
            if role in ('assembler', 'features', 'grams', 'references', 'grader'):
                from n079_state import StateStore
                context.state_store = StateStore(context, output_fd, context.numeric_limits)
                acquired.append(('role numeric state store', context.state_store.close))
        from n079_rpc import ServiceClient, SupervisorClient, ProviderClient, serve
        if role == 'issuer':
            from n079_issuer import IssuerService
            service = IssuerService(context, config['role_payload'], ServiceClient(context, 'observer', config['services']['observer'], endpoints))
        elif role == 'supervisor':
            from n079_jobs import JobSupervisor
            service = JobSupervisor(context, config['role_payload']); acquired.append(('supervisor owned resources', service.close))
        elif role == 'provider':
            from n079_provider import ProviderProxy
            fields(config['role_payload'], ('selection', 'credential_fd'))
            service = ProviderProxy(context, config['role_payload']['selection'], endpoints)
            acquired.append(('provider credential lifetime', service.close)); service.bind_credential(config['role_payload']['credential_fd'])
        if role in ('observer', 'issuer', 'supervisor', 'provider'):
            context.ready_fd = ready_fd
            ready_fd = None
            result = serve(context, role, service, config['services']['listen'], endpoints)
        elif role in ('assembler', 'features', 'grams', 'references'):
            require(ready_fd is None and repository is not None and output_fd is not None, 'owned full producer resources')
            result = {'index': producer(context, role, config, repository, output_fd, loader)}
        elif role == 'controller':
            require(ready_fd is None, 'one-shot complete controller')
            context.report_observer = ServiceClient(context, 'observer', config['services']['observer'], endpoints)
            context.report_output_path = config['output']['path']; context.report_material_root = config['repository']['root']
            from n079_campaign import run_controller
            result = run_controller(context, config['role_payload'],
                SupervisorClient(context, 'supervisor', config['services']['supervisor'], endpoints),
                ProviderClient(context, 'provider', config['services']['provider'], endpoints), repository, output_fd)
        elif role == 'grader':
            require(ready_fd is None, 'one actual target-last grade process')
            from n079_grading import ProtectedGrader
            fields(config['role_payload'], ('selection', 'numeric_source', 'input_index'))
            instance = ProtectedGrader(context, repository, config['role_payload']['numeric_source'], output_fd,
                context.numeric_limits, config['coordinate_block'], config['role_payload']['selection'])
            result = instance.grade({'index': config['role_payload']['input_index']})
        else:
            raise ValueError('role is not a concrete selected N079 entry')
        context.tick('closeout' if role in ('observer', 'issuer', 'supervisor', 'provider') else 'scientific')
        terminal.update(status='complete', result=result)
    except BaseException as error:
        first = error
    # Every acquired resource is attempted exactly once even when a previous
    # fsync/close fails. Source-known prefixes survive failed journal output.
    first = collect_errors(list(reversed(acquired)), first)
    if ready_fd is not None:
        first = collect_errors([('untransferred readiness descriptor', lambda: os.close(ready_fd))], first)
    if context is not None:
        terminal['source_pin'] = context.source_pin
        terminal['budget_prefix'] = context.ledger.snapshot()
        if endpoints is not None:
            try:
                terminal['endpoint_record'] = endpoints.closed_record()
            except BaseException as error:
                first = collect_errors([('closed endpoint record', lambda: (_ for _ in ()).throw(error))], first)
        first = collect_errors([('original role return cutoff', lambda: context.tick(
            'closeout' if context.role in ('observer', 'issuer', 'supervisor', 'provider') else 'scientific'))], first)
        context.closed = True
    if first is not None:
        terminal.update(status='failed_or_incomplete', failure=error_record(first))
    if context is not None:
        def publish_terminal():
            raw = bounded_encode(terminal, context.encoding_limits) + b'\n'
            require(len(raw) <= config['terminal_output_limit'], 'whole selected terminal role output ceiling')
        # This source-owned final line is independently captured by the actual
        # parent, including any additional runtime diagnostics on failure.
            stream = sys.stdout.buffer if first is None else sys.stderr.buffer
            stream.write(raw); stream.flush()
        first = collect_errors([('complete terminal role stream publication', publish_terminal)], first)
    if first is not None:
        first.n079_prefix = terminal; raise first
    return terminal
