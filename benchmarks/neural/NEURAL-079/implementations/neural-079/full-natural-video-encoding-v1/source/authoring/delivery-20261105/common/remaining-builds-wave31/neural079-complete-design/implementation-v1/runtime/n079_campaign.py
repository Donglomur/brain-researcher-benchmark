"""Concrete full candidate/native controller and observed artifact composition."""
import importlib
import math
import mmap
import os
from n079_common import require, fields, integer, identity, close_all
from n079_products import write_index
from n079_controller import Controller


def promote(supervisor, repository, context_id, path, name):
    descriptor = supervisor.promote(context_id, path, name)
    registration = supervisor.request('material_record', {'material_name': name})
    require(registration['pin'] == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'actual same supervisor registry/body return')
    require(name not in repository.catalog, 'one observed immutable registry publication')
    repository.catalog[name] = registration
    return descriptor


def read_raw(context, repository, descriptor, maximum, work):
    require(descriptor['bytes'] <= maximum, 'bounded complete opaque comparison extent')
    context.ledger.charge(work, {'data_read_bytes': descriptor['bytes'] + 1}, 'actual native opaque bytes after full identity admission')
    fd = repository.open(descriptor); first = None
    try:
        chunks = []; total = 0
        while total <= descriptor['bytes']:
            context.tick(); block = os.read(fd, min(65536, descriptor['bytes'] - total + 1))
            if not block:
                break
            chunks.append(block); total += len(block)
        require(total == descriptor['bytes'], 'complete opaque native body'); return b''.join(chunks)
    except BaseException as error:
        first = error; raise
    finally:
        close_all([('opaque comparison descriptor', lambda: os.close(fd))], first)


def compare_native(context, repository, module, actual_record, actual_object, reference, admission, selected, work):
    if reference is None or admission is None:
        # Missing authentic units/reference/tolerances are never invented.
        return module.outcome('missing_reference' if reference is None else 'missing_admission', capture_complete=True)
    reference_record = reference['record']; reference_object = reference['object']
    actual_quantity = actual_record['quantity']; reference_quantity = reference_record['quantity']
    if actual_quantity['encoding'] == 'json':
        return module.compare_opaque(read_raw(context, repository, actual_object, selected['opaque_bytes'], work),
            read_raw(context, repository, reference_object, selected['opaque_bytes'], work), actual_record, reference_record,
            admission, max_bytes=selected['opaque_bytes'])
    np = importlib.import_module('numpy'); maps = []; fds = []; arrays = []; first = None
    try:
        for descriptor, quantity in ((actual_object, actual_quantity), (reference_object, reference_quantity)):
            require(quantity['encoding'] == 'numeric' and type(quantity['shape']) is list and
                    all(type(x) is int and x >= 0 for x in quantity['shape']), 'exact native numeric support')
            dtype = np.dtype(quantity['dtype']); cells = math.prod(quantity['shape'])
            require(dtype.kind in 'biuf' and dtype.itemsize in (1, 2, 4, 8) and cells > 0 and
                    cells <= selected['numeric']['max_elements'] and cells * dtype.itemsize == descriptor['bytes'] and
                    descriptor['bytes'] <= selected['mapping_bytes'], 'complete native mapping preflight')
            context.ledger.charge(work, {'data_read_bytes': descriptor['bytes'], 'logical_float_slots':
                selected['numeric']['max_live_bytes'] // 8}, 'independent full native quantity comparison scan')
            fd = repository.open(descriptor); fds.append(fd)
            mapping = mmap.mmap(fd, descriptor['bytes'], access=mmap.ACCESS_READ); maps.append(mapping)
            arrays.append(np.ndarray(tuple(quantity['shape']), dtype=dtype, buffer=mapping))
        return module.compare_quantity(arrays[0], arrays[1], actual_record, reference_record, admission, limits=selected['numeric'])
    except BaseException as error:
        first = error; raise
    finally:
        arrays.clear()
        close_all([('native quantity mapping', mapping.close) for mapping in reversed(maps)] +
                  [('native quantity file', lambda fd=fd: os.close(fd)) for fd in reversed(fds)], first)


def run_native(context, selected, supervisor, repository):
    import native_adapter
    import native_compare
    fields(selected, ('program_selection', 'execution', 'views', 'worker_sources', 'role_command',
                      'program_evidence', 'base_view_evidence', 'comparisons', 'comparison_limits'))
    program = native_adapter.compile_program(selected['program_selection'])
    require(set(selected['execution']) == set(selected['views']) == {j['id'] for j in program['jobs']}, 'all22 native allocations and original views')
    completed = {}; rows = []; outcomes = {}; expected = []; policy_evidence = {}
    for job in program['jobs']:
        work = job['id']; view = {**selected['views'][work],
            'original_inputs': dict(selected['views'][work]['original_inputs']),
            'original_native_target_names': dict(selected['views'][work]['original_native_target_names'])}
        dependencies = {dep: completed[dep] for dep in job['dependencies']}
        for dep, files in job['dependency_files'].items():
            for file_id in files:
                member = dependencies[dep]['native_files'][file_id]; name = dep + '-' + file_id
                require(name not in view['original_inputs'], 'native dependency never shadows original support')
                view['original_inputs'][name] = member['descriptor']
                view['original_native_target_names'][name] = member['native_relative_path']
        binding = {'task': 'NEURAL-079', 'job': work, 'program_pin': native_adapter.pin(native_adapter.canonical(program)),
                   'source_pin': context.source_pin, 'view_pin': identity(view, context.encoding_limits)}
        evidence = context.authority.exchange('native_complete_view', {'job': job, 'view': view,
            'dependencies': dependencies, 'program_evidence': selected['program_evidence'],
            'base_view_evidence': selected['base_view_evidence'], 'binding': binding})
        request = native_adapter.build_request(program, work, execution=selected['execution'][work],
            context=work, work_id=work, worker_sources=selected['worker_sources'], selected_role_command=selected['role_command'],
            view=view, binding=binding, view_evidence=evidence, program_evidence=selected['program_evidence'], dependencies=dependencies)
        context.ledger.charge(work, {'code_executions': 1}, 'one exact complete native22 job')
        result = supervisor.run(request); index = result['output']
        require(index['job_id'] == work and index['context'] == work and index['request_pin'] == request['request_pin'] and
                index['native_execution']['status'] == 'returned' and index['capture_complete'] is True, 'actual complete original native capture')
        index_items = [x for x in result['inventory'] if x['path'] == 'CAPTURE_INDEX.json']
        require(len(index_items) == 1, 'actual independently observed complete native index')
        index_pin = {k: index_items[0][k] for k in ('bytes', 'sha256')}
        promotions = {}
        for member in index['native_files']:
            name = work + '-file-' + member['id']
            promotions[member['path']] = promote(supervisor, repository, work, member['path'], name)
        completed[work] = native_adapter.make_dependency_record(index, index_pin, result['closure'], promotions)
        quantities = {q['id']: q for q in index['quantities']}
        require(set(quantities) == {q['id'] for q in job['quantities']}, 'all required full native quantities')
        for spec in job['quantities']:
            quantity = quantities[spec['id']]; key = work + '/' + spec['id']; expected.append(key)
            actual = {'schema': 'n079_native_quantity_evidence_v1', 'job_id': work, 'variant': program['variant'],
                      'quantity': quantity, 'capture_index_pin': index_pin, 'observer_evidence': result['closure']}
            descriptor = promote(supervisor, repository, work, quantity['path'], work + '-quantity-' + spec['id'])
            choice = selected['comparisons'].get(key)
            if choice is not None:
                policy_evidence[key] = {'selection_pin': identity(choice, context.encoding_limits),
                    'issuer_evidence': context.authority.exchange('native_quantity_policy', {'key': key, 'selection': choice})}
            outcomes[key] = compare_native(context, repository, native_compare, actual, descriptor,
                None if choice is None else choice['reference'], None if choice is None else choice['admission'], selected['comparison_limits'], work)
        rows.append({'job': work, 'index': index_pin, 'capture': index, 'closure': result['closure'],
                     'inventory': result['inventory'], 'dependencies': dependencies})
    summary = native_compare.summarize_outcomes(expected, outcomes)
    require(all(row['capture_complete'] and row['status'] in ('match', 'mismatch', 'undefined_nonfinite') for row in outcomes.values()),
            'complete native capture and valid source/units/support/reference/tolerance evidence; missing or failed evidence refuses')
    return {'schema': 'n079_complete_native_programme_v1', 'program': program, 'jobs': rows, 'comparison': summary, 'comparison_policy_evidence': policy_evidence,
            'reproduction_success': summary['complete_required_comparison'] and summary['numerical_mismatch_count'] == 0,
            'reproduction_undefined_nonfinite': any(row['status'] == 'undefined_nonfinite' for row in outcomes.values()),
            'prospective_numerical_grade_not_blocked_by_mismatch': True, 'whole_paper_claim': False}


def run_controller(context, selected, supervisor, provider, repository, output_fd):
    fields(selected, ('candidate', 'native', 'coordinate_pin', 'consolidation_block', 'consolidation_max_open_files', 'report'))
    export_evidence = context.authority.exchange('register_outer_inputs', {'role': 'controller'})
    public_paths = set()
    for bundle in selected['candidate']['public_bundles'].values():
        bundle['public_export_evidence'] = export_evidence
        public_paths.update(d['path'] for d in bundle['training'].values())
        public_paths.update(d['path'] for query in bundle['queries'].values() for d in query.values())
    supervisor.request('register_public_materials', {'catalog': {k: repository.catalog[k] for k in sorted(public_paths)},
        'export_evidence': export_evidence})
    from n079_products import ProducedRepository, read_index
    from n079_report_evidence import ReportEvidenceBuilder
    produced = ProducedRepository(context, repository, output_fd, 'controller')
    first = None
    try:
        for number, choice in enumerate(selected['report']['bundles'].values()):
            body = read_index(context, repository, choice['public_input'], 'controller')
            item = write_index(context, output_fd, body, 'controller', 'report-public-input-%d.json' % number)
            produced.register(item); choice['public_input'] = item
        report_builder = ReportEvidenceBuilder(context, produced, output_fd, selected['report'])
        return finish_controller(context, selected, supervisor, provider, repository, output_fd, report_builder)
    except BaseException as error:
        first = error; raise
    finally:
        produced.close(first)


def finish_controller(context, selected, supervisor, provider, repository, output_fd, report_builder):
    controller = Controller(context, supervisor, provider, selected['candidate'], report_builder)
    controller.preseal(); candidates = controller.run_candidates()
    candidate_boundary = context.authority.exchange('close_candidate_information_phase',
        {'complete_jobs': sorted(r['context'] for r in controller.jobs), 'source_pin': context.source_pin})
    from n079_candidate_artifacts import consolidate
    panels = consolidate(context, repository, supervisor, output_fd, candidates, selected['coordinate_pin'],
                         coordinate_block=selected['consolidation_block'], max_open_files=selected['consolidation_max_open_files'])
    candidates['consolidated'] = panels
    candidates['information_phase_closed'] = candidate_boundary
    candidate_index = write_index(context, output_fd, candidates, 'controller', 'CANDIDATE_INDEX.json')
    native = run_native(context, selected['native'], supervisor, repository)
    native_index = write_index(context, output_fd, native, 'controller', 'NATIVE_INDEX.json')
    result = {'schema': 'n079_complete_controller_index_v1', 'source_pin': context.source_pin,
              'study_pin': context.effect_admission['study_pin'], 'candidate_index': candidate_index, 'native_index': native_index,
              'candidate_counts': candidates['counts'], 'native_jobs': 22}
    return {'index': write_index(context, output_fd, result, 'controller')}
