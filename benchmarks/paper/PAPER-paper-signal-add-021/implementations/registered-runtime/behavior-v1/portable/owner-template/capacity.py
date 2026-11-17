"""Fresh TMS planning guard using the accepted donor arithmetic and owned capture."""
import base64
import decimal
import hashlib
import os
from pathlib import Path
import time
import capacity_policy
from common import encode, need, pin, plain, write

def tms_workload_decision(capacity, disk_free_bytes):
 """Pure prospective TMS planning decision; never mutates the NIDER report."""
 names={'actual_14cores','both_pressure_NORMAL_dispatch1',
        'potential_headroom_at_least8GiB','no_observed_swapout_increase',
        'no_observed_pageout_increase','CPU_with_selected6fits','disk_at_least128MiB'}
 inherited=capacity.get('checks')
 if type(inherited) is not dict or set(inherited)!=names or any(type(v) is not bool for v in inherited.values()):
  raise ValueError('exact_NIDER_check_population')
 if type(capacity.get('passed')) is not bool or capacity['passed']!=all(inherited.values()):
  raise ValueError('unchanged_NIDER_pass_summary')
 snapshots=capacity.get('snapshots');cpu=capacity.get('cpu_samples_cores')
 if type(snapshots) is not list or len(snapshots)!=2 or type(cpu) is not list or len(cpu)!=2:
  raise ValueError('two_capacity_observations')
 potentials=[s['potential_headroom_bytes'] for s in snapshots]
 if any(type(n) is not int or n<0 for n in potentials):
  raise ValueError('exact_potential_bytes')
 samples=[decimal.Decimal(s) for s in cpu]
 if any(not n.is_finite() or n<0 for n in samples):
  raise ValueError('finite_nonnegative_CPU_samples')
 if type(disk_free_bytes) is not int or disk_free_bytes<0 or capacity['disk_free_bytes']!=disk_free_bytes:
  raise ValueError('same_nonnegative_disk_observation')
 tms=2147483648;possible_intake=268435456;margin=1879048192
 floor=tms+possible_intake+margin
 # Preserve every donor predicate except the explicitly superseded 8 GiB floor.
 checks={k:v for k,v in inherited.items() if k!='potential_headroom_at_least8GiB'}
 checks.update({
  'TMS_potential_headroom_at_least4GiB':min(potentials)>=floor,
  'TMS_additional_margin_at_least1_75GiB':min(potentials)-tms-possible_intake>=margin,
  'TMS_full_roster_CPU_plus8_fits14':max(samples)+8<=14,
  'TMS_disk_at_least256MiB':disk_free_bytes>=268435456})
 return {'schema':'tms_full_paired_workload_planning_decision_v2','passed':all(checks.values()),
         'checks':checks,'donor8GiB_method_passed':capacity['passed'],
         'donor8GiB_floor_passed':inherited['potential_headroom_at_least8GiB'],
         'TMS_host_bytes':tms,'possible_light_intake_host_bytes':possible_intake,
         'combined_workload_host_bytes':tms+possible_intake,
         'required_additional_planning_margin_bytes':margin,
         'required_potential_floor_bytes':floor,
         'observed_minimum_potential_bytes':min(potentials),
         'observed_margin_after_workloads_bytes':min(potentials)-tms-possible_intake,
         'workload_CPUs':2,'background_CPU_allowance':6,
         'sample_plus_full_roster_cores':str(max(samples)+8),
         'reservation_acquired_by_this_pure_function':False,
         'hard_memory_bound_or_instant_reclamation_claim':False,
         'interpretation':'Separate prospective TMS planning heuristic. The complete byte-identical NIDER 8GiB/512MiB-method report remains unchanged, including refusal. No extra inactive/speculative/purgeable credit.'}


def observe(root, owner, budget, active_deadline):
    """Eight fixed metadata commands through the existing owned command engine.

    No process-launch or signal mechanism is introduced here. Every admission,
    original stream and terminal command record remains under the owned root.
    """
    root = plain(root); root.mkdir(mode=0o700)
    logs = root / 'logs'; logs.mkdir(mode=0o700)
    rows = []; records = []; started = time.monotonic_ns()
    deadline = min(active_deadline, time.monotonic() + 45)
    for number, (name, argv) in enumerate(capacity_policy.PROBES, 1):
        if name == 'pressure-2':
            need(time.monotonic() + 0.2 < deadline, 'capacity_sample_gap_fits')
            time.sleep(0.2)
        need(time.monotonic() + 5 < deadline, 'full_capacity_command_window')
        begin_mono = time.monotonic_ns(); begin_wall = time.time_ns()
        event_pins = []
        def observed(phase, record):
            try:
                event_pins.append(write(root / (name + '.' + phase + '.json'),
                                        encode(record), budget))
                return True
            except BaseException:
                return False
        # A refusal or cancellation still returns/preserves the existing
        # engine's complete cleanup record before this adapter fails closed.
        record, out, err = owner.command(list(argv), directory=logs,
            number=number, budget=budget, until=time.monotonic() + 3,
            observed=observed, cap=65536, host_capacity=True)
        end_mono = time.monotonic_ns(); end_wall = time.time_ns()
        original = {'name': name, 'record': record, 'event_pins': event_pins}
        records.append(write(root / (name + '.command.json'), encode(original), budget))
        good = (record.get('complete') is True and record.get('exit_code') == 0 and
                record.get('reaped') is True and record.get('group_absent') is True and
                record.get('EOF') == ['stderr', 'stdout'] and not record.get('signals'))
        row = {'name': name, 'argv': list(argv), 'invocations': 1,
               'complete': good, 'failure': record.get('failure'),
               'returncode': record.get('exit_code'), 'reaped': record.get('reaped'),
               'new_session': record.get('registered_before_signal_unblock') is True,
               'group_cleanup': {'complete': record.get('group_absent') is True,
                                 'explicit_ESRCH': record.get('group_absent') is True},
               'started_monotonic_ns': str(begin_mono), 'ended_monotonic_ns': str(end_mono),
               'active_ended_monotonic_ns': str(end_mono),
               'started_wall_ns': str(begin_wall), 'ended_wall_ns': str(end_wall),
               'elapsed_seconds': (end_mono - begin_mono) / 1e9}
        for stream, body in (('stdout', out), ('stderr', err)):
            row.update({stream + '_EOF': stream in record.get('EOF', []),
                        stream + '_base64': base64.b64encode(body).decode('ascii'),
                        stream + '_bytes': len(body),
                        stream + '_sha256': hashlib.sha256(body).hexdigest()})
        write(root / (name + '.receipt.json'), encode(row), budget)
        rows.append(row)
        need(good, 'capacity_command_not_naturally_closed')
    disk = os.statvfs(root); free_disk = disk.f_bavail * disk.f_frsize
    donor = capacity_policy.evaluate(rows, free_disk)
    decision = tms_workload_decision(donor, free_disk)
    outcome = {'schema': 'tms_fixed_region_whole_capacity_v1',
               'donor_report_unchanged': donor, 'TMS_workload_decision': decision,
               'commands': records, 'started_monotonic_ns': str(started),
               'ended_monotonic_ns': str(time.monotonic_ns()),
               'all_eight_owned_groups_closed': True,
               'root_resource_reservation_inferred': False,
               'scientific_payload_reads': 0}
    receipt = write(root / 'CAPACITY.private.json', encode(outcome), budget)
    need(decision['passed'], 'fresh_TMS_capacity_refused')
    need(time.monotonic() < deadline, 'capacity_original_deadline')
    return {'receipt': receipt, 'passed': True,
            'ended_monotonic_ns': outcome['ended_monotonic_ns']}
