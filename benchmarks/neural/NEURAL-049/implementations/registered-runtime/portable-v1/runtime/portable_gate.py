"""Bounded new-instance admission; no historical WORK or qualification creation.

u and legacy_launch are exact captured definitions injected by portable entry.
"""
from pathlib import Path
import sys

BODY_CAP = 131072
SINGLE_PASS_READ_BOUND = 6 * (BODY_CAP + 1)
TWO_PASS_READ_BOUND = 2 * SINGLE_PASS_READ_BOUND
TASK = 'NEURAL-049'
PROFILE = 'curated_retrospective_full_v1'


def python_launch(argv):
    return legacy_launch(argv)


def exact(value, keys, label):
    u.need(type(value) is dict and set(value) == set(keys), label)
    return value


def same(a, b):
    return u.encode(a) == u.encode(b)


def desc(value):
    exact(value, ('path', 'pin'), 'exact instance descriptor')
    u.path(value['path'])
    exact(value['pin'], ('bytes', 'sha256'), 'exact instance pin')
    u.only_pin(value['pin'])
    return value


def inside(value, root, direct=False):
    value = u.path(value); root = u.path(root)
    u.need(value.parent == root if direct else root in value.parents,
           'fixed selected protected metadata namespace')
    return value


def freeze_descriptor(env, doc):
    value = doc['program_execution']['source_freeze']
    return {'path':str(env['repo']/value['path']), 'pin':u.only_pin(value)}


def registered(doc, operation, condition):
    if operation == 'grade':
        return doc['protected_grading_execution']['entrypoint']['argv']
    if condition is None:
        return doc['program_execution']['entrypoint']['argv']
    return doc['program_conditions'][condition]['entrypoint']['argv']


def actual_command(template, cli, env):
    index = legacy_launch(template)
    u.need(index == 1 and template[0] == '{python}', 'exact portable legacy launch')
    values = {'{program}':cli['program'], '{submission}':cli['program'],
              '{output}':cli['output'], '{review}':cli['review'],
              '{other_reserve_bytes}':str(cli['other_reserve_bytes'])}
    result = [sys.executable, str(env['repo']/template[1]),
              *[values.get(v, v) for v in template[2:]]]
    u.need(cli['actual_argv'] == result and cli['actual_cwd'] == str(env['repo']),
           'literal actual interpreter wrapper arguments cwd')
    return result


def admit(r, doc, cli, env, host):
    """Exactly six bounded captures; actual issuer trust is separately qualified."""
    before = host.reads
    root = env['repo']; central = env['here']
    operator = u.path(r['roots']['operator'])
    u.need(all(u.disjoint(root, p) for k,p in r['roots'].items()
               if k not in ('source','targets')), 'all external operation roots outside complete instance')
    u.need(u.path(r['roots']['source']) == env['parent_root'], 'fixed parent source root')
    declaration = desc(r['instance_declaration'])
    u.need(declaration['path'] == str(root/'SELECTION.json'), 'fixed instance declaration')
    selection = u.parse(host.read(declaration['path'], BODY_CAP, declaration['pin'], readonly=True))
    registry_raw = host.read(root/'benchmarks/neuroscience/neural-049/manifest.json',
                             BODY_CAP, r['registry'], readonly=True)
    u.need(same(u.parse(registry_raw), doc), 'current admitted registry unchanged')
    pair = exact(r['instance_request'], ('request','approval'), 'exact request/approval pair')
    for d in pair.values():
        desc(d); inside(d['path'], operator)
    request = u.parse(host.read(pair['request']['path'], BODY_CAP,
                                pair['request']['pin'], readonly=True))
    approval = u.parse(host.read(pair['approval']['path'], BODY_CAP,
                                 pair['approval']['pin'], readonly=True))
    approvals_path = central/'operator-selections/APPROVAL_REGISTRY.json'
    approvals_raw = host.read(approvals_path, BODY_CAP, readonly=True)
    approvals = u.parse(approvals_raw)
    exact(approvals, ('schema','instance','issuer','source_freeze','entries','evidence_set'),
          'positive final review approvals')
    evidence_d = desc(approvals['evidence_set']); inside(evidence_d['path'], operator)
    evidence = u.parse(host.read(evidence_d['path'], BODY_CAP, evidence_d['pin'], readonly=True))
    host.tick()
    u.need(host.reads-before <= SINGLE_PASS_READ_BOUND, 'exact six-capture local bound')

    freeze = freeze_descriptor(env, doc)
    exact(selection, ('schema','task_id','profile','root','construction','central_source',
                      'parent_source','source_freeze','registered_templates','module_options',
                      'status','scientific_qualification'), 'positive local source declaration')
    u.need(selection['schema'] == 'neural049_portable_source_selection_v1'
           and selection['task_id'] == TASK and selection['profile'] == PROFILE
           and selection['root'] == str(root) and selection['construction'] == env['instance']
           and selection['central_source'] == env['source']
           and selection['parent_source'] == env['parent_pin']
           and selection['source_freeze'] == freeze
           and selection['status'] == 'selected_source_only'
           and selection['scientific_qualification'] is False,
           'new source selection is not historical operational authority')
    u.need(selection['module_options'] == ['core','T1','D'], 'full exact selectable modules')
    templates = exact(selection['registered_templates'], ('default','named','grade'),
                      'three declared synonymous/full routes')
    u.need(templates['default'] == registered(doc,'collect',None)
           and templates['named'] == registered(doc,'collect',PROFILE)
           and templates['grade'] == registered(doc,'grade',None), 'registry/declaration template equality')
    template = templates['grade' if cli['operation']=='grade' else
                         'default' if cli['condition'] is None else 'named']
    actual = actual_command(template,cli,env)
    if cli['operation'] == 'grade':
        score = doc['entrypoints']['score']['argv']
        u.need([v if v != '{submission}' else '{program}' for v in score] == template,
               'generic score/program aliases differ only by operand placeholder')

    request_fields = ('schema','task_id','profile','instance_declaration','central_source',
                      'parent_source','source_freeze','registry','run','authority','operation',
                      'condition','program','output','review_slot','original_origin','parent_clock',
                      'central_observation_deadline','central_validation_deadline','selected_modules',
                      'cache','limits','other_reserve_bytes')
    exact(request, request_fields, 'positive selected instance request')
    u.need(request['schema'] == 'neural049_portable_request_v1'
           and request['task_id'] == TASK and request['profile'] == PROFILE, 'request identity')
    desc(request['run']); inside(request['run']['path'], operator)
    for key in ('instance_declaration','central_source','parent_source','registry','authority',
                'operation','condition','original_origin','central_observation_deadline',
                'central_validation_deadline','selected_modules','cache','limits','other_reserve_bytes'):
        u.need(same(request[key],r[key]), 'request/review exact field: '+key)
    u.need(request['source_freeze'] == freeze and request['program'] == cli['program']
           and request['output'] == cli['output'] and request['review_slot'] == cli['review'],
           'actual request operands and final review slot')
    clock = exact(request['parent_clock'], ('origin','production_end','observation_end','readback_end'),
                  'original full parent clock')
    values = [u.finite(clock[k]) for k in ('origin','production_end','observation_end','readback_end')]
    u.need(values == sorted(set(values)) and clock['origin'] == r['original_origin'],
           'unchanged ordered original clock')
    exact(approval, ('schema','issuer','realm','approved','instance','request','source_freeze','evidence'),
          'positive independent request approval')
    issuer = approval['issuer']
    u.need(type(issuer) is str and 0 < len(issuer) <= 256
           and approval['schema'] == 'neural049_portable_request_approval_v1'
           and approval['realm'] == 'actual_external_evidence' and approval['approved'] is True
           and approval['instance'] == env['instance'] and approval['request'] == pair['request']
           and approval['source_freeze'] == freeze, 'request independently approved for exact instance')
    u.need(type(approval['evidence']) is list and 1 <= len(approval['evidence']) <= 32,
           'bounded independent request evidence')
    for item in approval['evidence']:
        desc(item); inside(item['path'], operator)

    u.need(approvals['schema'] == 'neural049_portable_review_approvals_v1'
           and approvals['instance'] == env['instance'] and approvals['issuer'] == issuer
           and approvals['source_freeze'] == freeze, 'exact independent final review registry')
    entries = approvals['entries']
    u.need(type(entries) is list and 1 <= len(entries) <= 32, 'bounded final approval entries')
    current_review = {'path':cli['review'],'pin':env['review_pin']}
    matches = []
    for entry in entries:
        exact(entry, ('review','request','registry','actual_argv','cwd','environment_pin','approved','evidence'),
              'positive final review approval entry')
        desc(entry['review']); inside(entry['review']['path'],central/'operator-selections',direct=True)
        desc(entry['request']); inside(entry['request']['path'],operator)
        exact(entry['environment_pin'], ('bytes','sha256'), 'environment pin')
        u.only_pin(entry['environment_pin'])
        u.need(type(entry['evidence']) is list and 1 <= len(entry['evidence']) <= 32,
               'actual final approval evidence descriptors')
        for item in entry['evidence']:
            desc(item); inside(item['path'],operator)
        if entry['review'] == current_review:
            matches.append(entry)
    u.need(len(matches) == 1, 'one exact final review approval')
    chosen = matches[0]
    u.need(chosen['approved'] is True and chosen['request'] == pair['request']
           and chosen['registry'] == r['registry'] and chosen['actual_argv'] == actual
           and chosen['cwd'] == str(root), 'independent approval binds exact actual invocation')
    exact(evidence, ('schema','instance','issuer','realm','approved_entries_pin','evidence',
                     'independent_producer'), 'bounded approval evidence-set metadata')
    u.need(evidence['schema'] == 'neural049_portable_approval_evidence_set_v1'
           and evidence['instance'] == env['instance'] and evidence['issuer'] == issuer
           and evidence['realm'] == 'actual_external_evidence'
           and evidence['approved_entries_pin'] == u.pin(u.encode(entries))
           and type(evidence['independent_producer']) is str and evidence['independent_producer'],
           'separate original issuer evidence for exact entry set')
    u.need(type(evidence['evidence']) is list and 1 <= len(evidence['evidence']) <= 32,
           'bounded issuer evidence set')
    for item in evidence['evidence']:
        desc(item); inside(item['path'],operator)
    # The caller then joins issuer/environment/parent_clock to the exact parent
    # authority before any resource effect or operation. Real issuer custody is
    # also an independently qualified central/parent gate, not a JSON assertion.
    return {'schema':'neural049_portable_instance_admission_v1','task_id':TASK,
            'instance':env['instance'],'declaration':declaration,'registry':r['registry'],
            'request':pair['request'],'request_approval':pair['approval'],
            'review':current_review,'approval_registry':{'path':str(approvals_path),'pin':u.pin(approvals_raw)},
            'approval_evidence':evidence_d,'issuer':issuer,'environment_pin':chosen['environment_pin'],
            'parent_clock':clock,'registered_argv':template,'actual_argv':actual,'cwd':str(root),
            'source_freeze':freeze,'metadata_read_charge_bytes':host.reads-before,
            'scope':'local source/request/approval recheck only; no WORK or scientific qualification'}


def finish(first, second, command, cwd):
    u.need(type(first) is dict and type(second) is dict
           and same({k:v for k,v in first.items() if k!='metadata_read_charge_bytes'},
                    {k:v for k,v in second.items() if k!='metadata_read_charge_bytes'}),
           'local authority changed between two admissions')
    u.need(second['actual_argv'] == command and second['cwd'] == str(cwd),
           'final exact command/cwd joins admission')
    legacy_launch(second['registered_argv'])
    result = {**second,'invocation':u.pin(u.encode({'argv':command,'working_directory':str(cwd)})),
              'metadata_read_charge_bytes':first['metadata_read_charge_bytes']+second['metadata_read_charge_bytes'],
              'local_instance_request_and_registry_rechecked_before_launch':True}
    u.need(len(u.encode(result)) <= 16384, 'bounded original CAMPAIGN.json portable admission body')
    return result
