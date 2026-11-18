"""Explicit aggregate budget for the full, fixed nonlearning engineering pair."""
from pathlib import Path
import math

from source import BANK_SHA, IMAGE, need

FIELDS = {'schema', 'scope', 'bank', 'assets', 'output', 'docker', 'docker_socket',
          'bank_manifest_sha256', 'image', 'purpose', 'output_unit',
          'candidate_seconds', 'memory_bytes', 'campaign_seconds', 'other_reserve_bytes'}


def validate(plan):
    need(type(plan) is dict and set(plan) == FIELDS, 'exact complete plan fields')
    need(plan['schema'] == 'spinal_current_completion_plan_v1'
         and plan['scope'] == 'fixed_one_hz_nonlearning_engineering_pair', 'fixed engineering scope')
    need(plan['bank_manifest_sha256'] == BANK_SHA and plan['image'] == IMAGE,
         'unchanged original bank and image')
    need(plan['purpose'] in ('reproduction', 'improvement') and plan['output_unit'] == 'hz',
         'declared purpose and exact fixed-control units')
    # This is a separate fixed-control profile, not a reduced budget silently
    # applied to a participant training episode or historical paper recipe.
    need(type(plan['candidate_seconds']) is int and 1 <= plan['candidate_seconds'] <= 60,
         'bounded fixed nonlearning candidate duration')
    need(type(plan['memory_bytes']) is int and 536870912 <= plan['memory_bytes'] <= 4294967296,
         'unchanged candidate memory range')
    seconds = plan['campaign_seconds']
    need(type(seconds) is int and plan['candidate_seconds'] + 600 <= seconds
         <= 88 * (plan['candidate_seconds'] + 420) + 240, 'explicit whole campaign bound')
    need(type(plan['other_reserve_bytes']) is int and plan['other_reserve_bytes'] >= 0,
         'explicit other outstanding reservations')
    for name in ('bank', 'assets', 'output', 'docker', 'docker_socket'):
        value = plan[name]
        need(type(value) is str and len(value) <= 4096 and Path(value).is_absolute()
             and str(Path(value)) == value and '..' not in Path(value).parts,
             'canonical absolute operator path')
    need(plan['output'] not in (plan['bank'], plan['assets']), 'separate attempt destination')
    return plan


def runtime(plan, delivery, completion_pin, plan_pin, *, deadline, now):
    validate(plan)
    need(math.isfinite(deadline) and math.isfinite(now), 'finite original monotonic deadline')
    remaining = deadline - now
    need(plan['candidate_seconds'] + 540 < remaining <= plan['campaign_seconds'],
         'remaining whole bound fits one complete old fold plus terminal reserve')
    selected = delivery.runtime_selection(plan['candidate_seconds'], plan['memory_bytes'],
                                           plan['other_reserve_bytes'])
    original = {k: selected[k] for k in ('worker_wall_seconds', 'outer_wall_seconds')}
    selected.update(worker_wall_seconds=remaining - 60, outer_wall_seconds=remaining,
                    profile='spinal_full_pair_fixed_control_aggregate_v1',
                    completion_source=completion_pin, plan=plan_pin,
                    aggregate_deadline_monotonic=deadline,
                    aggregate_observed_remaining_seconds=remaining,
                    selected_campaign_seconds=plan['campaign_seconds'],
                    original_sum_of_all_fold_maxima=original,
                    all_88_contexts_required=True, partial_success_allowed=False)
    return selected
