"""Explicit programme-only production for the frozen full32 reference.

This runner uses the original packet, episode, and response-collection primitives.
It creates no provider condition or private-label descriptor. A full unscored arm
exists only after every original query has one admitted response and owned closure.
There is no import-time work, retry, cross-query fitting, or readiness promotion.
Per-query fitting is restricted to the same four permitted demonstrations.
"""
from __future__ import annotations

from pathlib import Path
import signal
import sys
import time
import types


class ReferenceInterrupted(BaseException):
    """Unwind the accepted episode's finally when its owner is interrupted."""


def run_reference(reference, contract, contract_pin, output, *, modules=None):
    """Produce only the preselected fixed programme's complete 6400-case arm."""
    started = time.monotonic()
    reference.validate_contract(contract)
    modules = reference.dependencies(contract['source_bindings']) if modules is None else modules
    pair = modules['pair']
    pair.need(pair.pin(pair.encode(contract)) == contract_pin, 'Canonical reference contract changed')
    pair.need(reference.COUNT == 6400 and reference.CONDITION == 'numeric_program_four_demo',
              'Original full32 programme condition required')
    condition = reference.CONDITION
    limits = contract['limits']
    deadline = started + limits['campaign_seconds']
    budget = pair.Budget(limits['read_bytes'], limits['write_bytes'], deadline)
    budget.input(4 * 1024**2)  # Conservative authenticated source/configuration reservation.
    frozen = reference.verify_frozen(contract, modules, budget)
    protected = [Path(contract['public_root']).parent, Path(contract['programme']['path']).parent,
                 Path(contract['authoring_exposure']['path']).parent,
                 Path(contract['frozen_roster']['path']).parent, reference.HERE]
    protected.extend((Path(modules['repository_root']) / row['path']).parent
                     for row in modules['source_members'].values())
    output = pair.disjoint_output(output, modules, protected)
    runtime_roots = tuple(Path(value) for value in ('/System', '/usr', '/Library/Frameworks'))
    pair.need(not any(output.is_relative_to(root) for root in runtime_roots),
              'Reference output must not be visible through programme runtime roots')
    pair.need(sys.platform == 'darwin' and
              any(Path(contract['interpreter']['path']).is_relative_to(root) for root in runtime_roots),
              'Pinned interpreter outside accepted macOS sandbox roots')
    pair.executable(contract['interpreter'], budget)
    pair.executable(contract['sandbox'], budget)
    pair.need(limits['campaign_seconds'] > limits['episode_work_seconds'] +
              limits['episode_cleanup_seconds'] + 5, 'Retain campaign failure-finalization time')
    # Metadata authentication and the runtime checks above precede all waveform
    # access. This roster also survives a subsequent PacketSession failure.
    identifiers = tuple(reference.prequery_metadata(contract, modules, budget))
    pair.need(len(identifiers) == reference.COUNT and len(set(identifiers)) == reference.COUNT and
              identifiers == tuple(sorted(identifiers)), 'Exact frozen full32 roster required')
    output.mkdir(mode=0o700)
    pair.write(output / 'CONTRACT.json', pair.encode(contract), budget)
    pair.write(output / 'EXPOSURE.json', frozen['exposure'], budget)
    pair.write(output / 'FROZEN.json', frozen['programme'], budget)
    client = output / 'CLIENT.py'
    client_pin = pair.write(client, frozen['client'], budget)
    initial = b''.join(pair.encode({'ordinal': ordinal, 'trial_id': identifier, 'status': 'unattempted'})
                       for ordinal, identifier in enumerate(identifiers))
    initial_pin = pair.write(output / 'INITIAL.jsonl', initial, budget)
    journal = attempts = None
    episodes = []
    attempted = succeeded = 0
    last_closed = True
    prior_handlers = {}

    def interrupted(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        raise ReferenceInterrupted()

    try:
        # Default SIGTERM would bypass Python finally and orphan a candidate's
        # independently owned session. Raise instead; the original episode owns
        # stop/reap and retains any unresolved closure without a retry.
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGALRM):
            prior_handlers[signum] = signal.signal(signum, interrupted)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - 5 - time.monotonic()))
        journal = (output / 'STATUS.jsonl').open('xb', buffering=0)
        attempts = (output / 'ATTEMPTS.jsonl').open('xb', buffering=0)
        budget.input(pair.SESSION_RESERVE)
        with modules['consumer'].PacketSession(contract['public_root'], contract['public_manifest']) as session:
            pair.need(tuple(session.trial_ids) == identifiers, 'Packet and frozen metadata rosters disagree')
            facade = types.SimpleNamespace(ordinary_path=pair.ordinary_path,
                context_frame=modules['core'].context_frame, PREFIX=pair.PREFIX,
                need=pair.need, pin=pair.pin, encode=pair.encode, write=pair.write)
            for ordinal, identifier in enumerate(identifiers):
                pair.need(time.monotonic() + limits['episode_work_seconds'] +
                          limits['episode_cleanup_seconds'] + 5 < deadline,
                          'Insufficient time for another complete episode; no retry')
                pair.need(budget.written + 2 * 1024**2 <= budget.write_limit,
                          'Insufficient artifact headroom for another complete episode')
                # One public context, bounded stderr and the child source load;
                # explicit retained-file reads below are separately charged.
                budget.input(pair.PROMPT_CAP + 65536 + len(frozen['client']))
                context = session.context(identifier, condition)
                pair.need(context['trial_id'] == identifier and context['condition'] == condition,
                          'Original programme context identity required')
                pair.read(client, 1048576, client_pin, budget)
                path = output / f'{ordinal:04d}'
                pair.append_row(journal, {'ordinal': ordinal, 'trial_id': identifier,
                                         'status': 'dispatch_started'}, budget)
                attempted += 1
                last_closed = False
                envelope, end = modules['episode'].episode(facade, context, condition, path, client,
                    contract['interpreter']['path'], limits, deadline - 5, modules, budget,
                    generated_protocol_only=False)
                last_closed = modules['runtime'].end_closed(end)
                pair.append_row(attempts, envelope, budget)
                pair.append_row(journal, {'ordinal': ordinal, 'trial_id': identifier,
                    'status': envelope['status'], 'known_scope_closed': last_closed,
                    'end': pair.pin(pair.encode(end))}, budget)
                pair.accept_programme(envelope, end, context, modules)
                episodes.append({'trial_id': identifier, 'status': 'ok', 'end': pair.pin(pair.encode(end))})
                succeeded += 1
            pair.need(attempted == succeeded == len(episodes) == reference.COUNT and last_closed and
                      tuple(row['trial_id'] for row in episodes) == identifiers,
                      'All original cases and owned closures required before collection')
            reference.verify_frozen(contract, modules, budget)
            pair.need(tuple(reference.prequery_metadata(contract, modules, budget)) == identifiers,
                      'Frozen packet metadata changed during the arm')
            # Reuse the collector's original finite ceilings, retaining enough
            # independent room for the complete arm or an explicit failure row.
            collector_writes = modules['consumer'].LEDGER_LIMIT + 2 * 1024**2 + 131072
            pair.need(budget.written + collector_writes + pair.ARM_CAP + 65536 <= budget.write_limit,
                      'Collection and final receipt artifact headroom required')
            budget.input(2 * modules['consumer'].LEDGER_LIMIT + reference.COUNT * pair.PROMPT_CAP)
            budget.output(collector_writes)
            collected = modules['consumer'].collect(session, condition, output / 'ATTEMPTS.jsonl',
                                                    output / 'collection', deadline - 5)
            pair.need(collected.get('status') == 'complete_unscored_submission' and
                      collected.get('responses') == reference.COUNT and
                      collected.get('condition') == condition and
                      collected.get('private_target_reads') == 0 and
                      collected.get('scoring_performed') is False,
                      'Original complete unscored collection required')
        predictions = pair.pin(pair.read(output / 'collection/predictions.jsonl', 2 * 1024**2, budget=budget))
        collection_body = pair.read(output / 'collection/COMPLETE.json', 131072, budget=budget)
        pair.need(pair.decode(collection_body) == collected and collected['predictions'] == predictions,
                  'Retained collection differs from its complete return')
        receipt = {'schema': 'erp-full6400-numeric-arm-v1', 'status': 'closed_unscored_arm',
            'reference_scope': 'full32_fixed_reference_only', 'condition': condition, 'contract': contract_pin,
            'public_manifest': contract['public_manifest'], 'study_source_bindings': contract['source_bindings'],
            'programme_identity': contract['programme']['bundle_identity'],
            'authoring_exposure': contract['authoring_exposure']['file'],
            'source_bindings': pair.pin(modules['core_bindings_body']),
            'bundle_identity': contract['programme']['bundle_identity'],
            'query_count': reference.COUNT, 'attempt_inventory_count': attempted,
            'initial_inventory': initial_pin, 'episodes': episodes,
            'predictions': predictions, 'collection': pair.pin(collection_body),
            'private_target_reads': 0, 'scoring_performed': False, 'model_calls': 0,
            'automatic_retry': False, 'read_bytes_charged': budget.read,
            'written_bytes_charged_before_arm': budget.written,
            'resource_charge_scope': 'Conservative source/session/child/collector reservations plus exact retained I/O.',
            'programme_selection': 'Frozen fixed reference; no cross-query fitting or answer-based programme selection. Fitting is restricted to the four permitted demonstrations.',
            'interpretation': 'Finite-cohort event-label classification; no physiological P3-presence claim.',
            'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
            'outer_campaign_and_resource_qualification_required': True,
            'escaped_descendant_containment_qualified': False, 'new_benchmarks': 0}
        reference.validate_reference_header(receipt, contract_pin, contract, modules=modules)
        body = pair.encode(receipt)
        pair.need(len(body) <= pair.ARM_CAP, 'Bounded complete arm receipt')
        pair.write(output / 'ARM.json', body, budget)
        return receipt
    except BaseException as error:
        failure = {'schema': 'erp-full32-fixed-reference-failure-v1', 'status': 'failed_no_partial_admission',
            'reference_scope': 'full32_fixed_reference_only', 'condition': condition,
            'contract': contract_pin, 'error_type': type(error).__name__,
            'attempted': attempted, 'succeeded': succeeded, 'failed_or_unresolved': attempted - succeeded,
            'unattempted': reference.COUNT - attempted, 'initial_inventory': initial_pin,
            'initial_roster_retained': True, 'last_known_scope_closed': last_closed,
            'automatic_retry': False, 'private_target_reads': 0, 'scoring_performed': False,
            'model_calls': 0, 'read_bytes_charged': budget.read, 'written_bytes_charged': budget.written,
            'outer_campaign_and_resource_qualification_required': True}
        # If the OS or the selected outer deadline prevents finalization, the
        # immutable initial roster and fsynced dispatch journal still remain.
        # No failed/partial directory receives an ARM.json admission receipt.
        pair.write(output / 'FAILED.json', pair.encode(failure), budget)
        raise
    finally:
        try:
            for stream in (journal, attempts):
                if stream is not None:
                    stream.close()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            for signum, handler in prior_handlers.items():
                signal.signal(signum, handler)
