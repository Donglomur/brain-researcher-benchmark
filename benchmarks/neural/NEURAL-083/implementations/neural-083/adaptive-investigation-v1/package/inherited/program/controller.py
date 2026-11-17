"""Two independent complete panels; every condition has a fresh fitted model."""
import os
from pathlib import Path


def write(path, value, budget, cap=2000000):
    return c.save(path, c.encoded(value), cap, budget.tick, budget.write)


def run(selection, source, bodies, origin, worker_end, startup_reads=0):
    root = c.path(selection['output'])
    c.need(not os.path.lexists(root) and root.parent.is_dir(), 'Fresh full-panel attempt')
    c.need(worker_end == origin + selection['limits']['whole_seconds'] - selection['limits']['observer_seconds'],
           'Original enclosing clock')
    budget = c.Budget(root, selection['other_future_bytes'], worker_end, selection['limits'])
    budget.read(startup_reads)
    budget.capacity(65536)
    binding = c.parse(bodies['BINDING.json'])
    c.need(binding['reference'] == c.pin(bodies['reference_program.py']), 'Reference declaration matches captured source')
    policy.reviews(selection, source, binding,
                   lambda path, cap, expected: c.capture(path, cap, expected, budget.tick, budget.read))
    program = c.capture(selection['program']['path'], 1048576, c.only_pin(selection['program']), budget.tick, budget.read)
    program.decode('utf-8')
    root.mkdir(mode=0o700)
    c.sync_dir(root.parent, budget.tick)
    completed = []
    last = 'commitment'
    current = None
    try:
        submitted = root / 'candidate.py'
        c.save(submitted, program, 1048576, budget.tick, budget.write)
        c.readable(submitted, budget.tick)
        reference = root / 'reference.py'
        c.save(reference, bodies['reference_program.py'], 131072, budget.tick, budget.write)
        c.readable(reference, budget.tick)
        write(root / 'COMMITMENT.json', dict(schema='neural083_full_commitment_v1', source=source,
              candidate=c.pin(program), reference=c.pin(bodies['reference_program.py']),
              canonical=c.only_pin(selection['canonical']), origin=origin, worker_end=worker_end,
              programs_fixed_before_operator_staging=True), budget)
        canonical = store.load(selection, budget)
        write(root / 'PANEL.json', canonical['panel'], budget)
        trusted = root / 'trusted'
        trusted.mkdir(mode=0o700)
        for name in ('holder.py', 'candidate_entry.py'):
            c.save(trusted / name, bodies[name], 131072, budget.tick, budget.write)
            c.readable(trusted / name, budget.tick)
        os.chmod(trusted, 0o555)
        c.sync_dir(trusted, budget.tick)
        phases = root / 'conditions'
        phases.mkdir(mode=0o700)
        for item in contracts.schedule(canonical['panel']):
            ordinal = item['ordinal']
            folder = phases / ('condition%04d' % ordinal)
            folder.mkdir(mode=0o700)
            c.sync_dir(phases, budget.tick)
            selected_program = submitted if item['panel'] == 'candidate' else reference
            selected_pin = c.pin(program) if item['panel'] == 'candidate' else c.pin(bodies['reference_program.py'])
            current = root / 'current'
            last = str(ordinal) + '/fit-stage'
            training, fit_metadata = store.stage(canonical, item['case'], item['setting'], item['arm'], 'fit', current, budget)
            train_stamps = store.verify(current, training, budget)
            fit_dir = folder / 'fit'
            fit_dir.mkdir(mode=0o700)
            budget.read(sum(p['bytes'] for p in training.values()))
            budget.native('fit', ordinal)
            c.capture(selected_program, 1048576, selected_pin, budget.tick, budget.read)
            last = str(ordinal) + '/fit'
            fitted = native.phase(selection, trusted, current, selected_program, None, fit_dir, 'fit', ordinal,
                                  source, budget, worker_end)
            c.need(fitted['status'] == 'captured' and fitted['all_native_resources_closed'] is True,
                   'Complete fitting closure before model transfer')
            model = folder / 'model.bin'
            model_pin = fitted['output']
            c.capture(fit_dir / 'model.bin', 536870912, model_pin, budget.tick, budget.read)
            c.need(not os.path.lexists(model), 'Fresh single model destination')
            os.rename(fit_dir / 'model.bin', model)
            c.readable(model, budget.tick)
            c.sync_dir(fit_dir, budget.tick)
            c.sync_dir(folder, budget.tick)
            model_stamp = c.stamp(model.lstat())
            fit_native = c.pin(c.capture(fit_dir / 'NATIVE.json', 262144, None, budget.tick, budget.read))
            seal = write(folder / 'MODEL_SEAL.json', dict(schema='neural083_model_seal_v1', condition=item,
                         program=selected_pin, model=model_pin, native=fit_native, model_stamp=list(model_stamp),
                         fit_closed=True, query_exposed=False, permitted_training_state_may_be_retained=True), budget)
            store.verify(current, training, budget)
            store.retire(current, training, train_stamps, budget)
            current = None
            retirement = write(folder / 'TRAIN_RETIRED.json', dict(condition=item, training=training, model_seal=seal,
                               absent=True, parent_fsynced=True, query_exposed=False), budget)
            c.need(not os.path.lexists(root / 'current'), 'Training removed before any query staging')
            current = root / 'current'
            last = str(ordinal) + '/query-stage'
            query, metadata = store.stage(canonical, item['case'], item['setting'], item['arm'], 'infer', current, budget,
                                          model_binding=dict(model=model_pin, program=selected_pin))
            query_stamps = store.verify(current, query, budget)
            metadata_pin = write(folder / 'QUERY_METADATA.json', metadata, budget)
            infer_dir = folder / 'infer'
            infer_dir.mkdir(mode=0o700)
            budget.read(sum(p['bytes'] for p in query.values()) + model_pin['bytes'])
            budget.native('infer', ordinal)
            c.need(c.stamp(model.lstat()) == model_stamp, 'Same immutable condition model')
            c.capture(selected_program, 1048576, selected_pin, budget.tick, budget.read)
            last = str(ordinal) + '/infer'
            inferred = native.phase(selection, trusted, current, selected_program, model, infer_dir, 'infer', ordinal,
                                    source, budget, worker_end)
            c.need(inferred['status'] == 'captured' and inferred['all_native_resources_closed'] is True,
                   'Complete query-process closure before result admission')
            raw = c.capture(infer_dir / 'predictions.json', 100000, inferred['output'], budget.tick, budget.read)
            contracts.prediction(c.parse(raw), metadata)
            infer_native = c.pin(c.capture(infer_dir / 'NATIVE.json', 262144, None, budget.tick, budget.read))
            store.verify(current, query, budget)
            store.retire(current, query, query_stamps, budget)
            current = None
            query_retired = write(folder / 'QUERY_RETIRED.json', dict(condition=item, query=query,
                                 metadata=metadata_pin, absent=True, parent_fsynced=True, native=infer_native), budget)
            c.need(c.stamp(model.lstat()) == model_stamp and not os.path.lexists(fit_dir / 'model.bin'),
                   'Exact sole model before retirement')
            model.unlink()
            c.sync_dir(folder, budget.tick)
            model_retired = write(folder / 'MODEL_RETIRED.json', dict(condition=item, model=model_pin,
                                 model_seal=seal, absent=True, parent_fsynced=True), budget)
            store.unchanged(canonical, budget)
            closed = write(folder / 'CLOSED.json', dict(schema='neural083_closed_condition_v1', condition=item,
                           program=selected_pin, fit_native=fit_native, infer_native=infer_native, seal=seal,
                           train_retired=retirement, query_metadata=metadata_pin, query_retired=query_retired,
                           model_retired=model_retired, model=model_pin, output=inferred['output'],
                           all_views_models_and_native_resources_closed=True), budget)
            completed.append(dict(ordinal=ordinal, condition=item, closed=closed))
            budget.capacity()
        c.need(len(completed) == 2592 and len(budget.phases) == 5184, 'Every condition in both panels')
        store.unchanged(canonical, budget)
        bundle = write(root / 'submission.json', dict(schema='neural083_full_program_submission_v1',
                       source=source, canonical=c.only_pin(selection['canonical']), conditions=completed), budget)
        handoff = write(root / 'GRADE_HANDOFF.json', dict(schema='neural083_protected_grade_handoff_v1',
                        original_scoring_sources=binding['scoring_sources'], complete_panels_required=2,
                        conditions_per_panel=1296, target_access_authorized=False,
                        independent_external_closure_required=True), budget)
        complete = write(root / 'COMPLETE.json', dict(schema='neural083_full_complete_v1', source=source,
                         candidate=c.pin(program), reference=c.pin(bodies['reference_program.py']),
                         canonical=c.only_pin(selection['canonical']), submission=bundle, grade_handoff=handoff,
                         conditions=2592, native_phases=5184, prediction_values=259200,
                         all_views_models_retired=True, query_truth_opened=False,
                         scoring_performed=False, scientific_qualified=False, runtime_qualified=False,
                         costs_snapshot='Before COMPLETE publication; exact final write delta is in worker terminal',
                         costs=budget.record()), budget)
        budget.tick()
        return dict(schema='neural083_full_worker_v1', status='complete_unqualified', source=source,
                    complete=complete, submission=bundle, prediction_values=259200,
                    costs_after_complete=dict(read_reservations=budget.reads, write_reservations=budget.writes,
                                              native_phases=len(budget.phases)))
    except BaseException as error:
        try:
            write(root / 'FAILURE.json', dict(schema='neural083_full_failure_v1', last_phase=last,
                  completed_conditions=len(completed), expected_conditions=2592, source=source,
                  error_type=type(error).__name__, current_view_may_remain=current is not None,
                  nested_native_recovery_may_be_required=True, automatic_retry=False, costs=budget.record()), budget)
        except BaseException:
            pass
        raise
