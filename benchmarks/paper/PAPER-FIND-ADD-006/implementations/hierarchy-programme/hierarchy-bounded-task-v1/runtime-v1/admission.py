"""Strict source, root authority, shared dynamic capacity and additive family cost."""
from pathlib import Path
from files import HERE, ROOT, ID, RUNTIME_ID, need, read, pin, json_read, descriptor, captured_module, freeze, accounting, current_metadata

WHOLE, WORK, CLEANUP = 780, 720, 60
OWN_RESERVE = 32000000
MINIMUM_OTHER = 400000000


def admit(args, run, admitted_state):
    review = json_read(args.review, 131072)
    need(type(review.get('schema_version')) is int and review.get('schema_version') == 1 and review.get('candidate_id') == ID and
         review.get('runtime_id') == RUNTIME_ID and
         review.get('decision') == 'authorize_one_hierarchy_program_attempt' and
         review.get('execution_authority') is True and review.get('mode') == 'ordinary',
         'Exact root-reviewed ordinary hierarchy attempt')
    need(all(type(review.get(k)) is int for k in ('whole_seconds','work_seconds','cleanup_seconds',
         'candidate_seconds','own_reserve_bytes','other_reserve_bytes')), 'Literal integer clocks and reserves')
    need(review.get('whole_seconds') == WHOLE and review.get('work_seconds') == WORK and
         review.get('cleanup_seconds') == CLEANUP and review.get('candidate_seconds') == 600 and
         review.get('own_reserve_bytes') == OWN_RESERVE and type(args.other_reserve_bytes) is int and
         args.other_reserve_bytes >= MINIMUM_OTHER and review.get('other_reserve_bytes') == args.other_reserve_bytes,
         'Exact declared task clocks and reserves')
    need(review.get('output_path') == str(run.relative_to(ROOT)) and
         review.get('no_whole_paper_or_fig3f_claim') is True and
         review.get('new_generated_grader_controls_required') is True,
         'Exact output, source-scope and future control admission')
    frozen = freeze(review)
    reports = review.get('source_reviews')
    need(type(reports) is list and 1 <= len(reports) <= 4, 'Bounded independent source review evidence')
    for item in reports:
        report = descriptor(item, 1000000)
        need(report.get('status') == 'passed' and report.get('findings') == [] and
             report.get('source_freeze_sha256') == review['freeze_sha256'], 'Reviews bind final executable source')
    allocation = descriptor(review['allocation'], 131072)
    need(all(type(allocation.get(k)) is int for k in ('whole_seconds','work_seconds','cleanup_seconds',
         'own_reserve_bytes','other_reserve_bytes')), 'Literal allocation clocks and reserves')
    need(allocation.get('candidate_id') == ID and allocation.get('runtime_id') == RUNTIME_ID and
         allocation.get('allocation_authority') is True and allocation.get('whole_seconds') == WHOLE and
         allocation.get('work_seconds') == WORK and allocation.get('cleanup_seconds') == CLEANUP and
         allocation.get('own_reserve_bytes') == OWN_RESERVE and allocation.get('other_reserve_bytes') == args.other_reserve_bytes and
         allocation.get('output_path') == review['output_path'] and
         allocation.get('source_freeze_sha256') == review['freeze_sha256'], 'Exact separately bound prospective allocation')
    prior = accounting(review, WHOLE)
    admitted_state.update(prior_known_seconds=prior, source_freeze_sha256=review['freeze_sha256'],
                          root_authority_and_prior_admitted=True)
    need(allocation.get('prior_known_seconds') == prior and allocation.get('known_after_seconds') == prior + WHOLE,
         'Allocation preserves complete known family allowance')
    program = read(args.program, 131072)
    program.decode('utf-8', errors='strict')
    need(args.program.suffix == '.py' and review.get('program_source') == {
        'path':str(args.program.resolve().relative_to(ROOT)), **pin(program)}, 'One exact reviewed source program')
    inputs = descriptor(review['public_allowlist'], 32768)
    assets = json_read(HERE/'ASSETS.json')
    need(review['public_allowlist'] == assets['public_allowlist'] and inputs['candidate_id'] == ID and
         len(inputs['public_inputs']) == 8 and inputs['public_inputs'] == assets['public_inputs'],
         'Unchanged complete public8-file boundary')
    shared = captured_module(current_metadata('IMPORTS.json')['dynamic_capacity'], '_hierarchy_dynamic_capacity')
    admitted = shared.validate(review, allocation, lambda desc: descriptor(desc, 2000000),
                               candidate_id=ID, own_reserve=OWN_RESERVE, minimum_other=MINIMUM_OTHER)
    need(admitted['other_reserve_bytes'] == args.other_reserve_bytes and
         review.get('other_reserves_exclude_images') is True and allocation.get('other_reserves_exclude_images') is True,
         'Nested/top-level/CLI reserves agree; full image census counted exactly once')
    return review, frozen, program, admitted, shared
