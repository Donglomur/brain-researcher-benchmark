"""Appended to the pinned configuration module in the versioned deployment.

Uses that module's strict capture/decode helpers. No candidate code executes.
Source/procedure review is an operator assertion, not a scientific certificate.
"""
import ast
import base64

INVESTIGATOR_TEMPLATE_PIN = {'bytes': 13945, 'sha256': '063df6a6320e784ba13b675c6363f12c460e68cc6b59821b0a5752b87b90c145'}
FROZEN_ACTOR_PIN = {'bytes': 2623, 'sha256': '9b7b1c647e122a56ee2d50c0a7bcb4a4fb221b6a354b74477fd8941c2293f8a6'}
REVIEW_CHECKS = (
    'two_stage_numerical_abi', 'training_only_preparation', 'no_query_fitting',
    'same_procedure_across_views', 'allowed_view_specific_changes_reviewed',
    'no_private_assets_or_case_id_shortcuts', 'within_existing_resource_profile',
    'callback_observes_only_allowed_tool_results', 'cell_state_and_full_query_access_declared',
    'fresh_actor_namespace_across_views', 'frozen_branch_returns_original_batch',
)


def validate_adaptive_binding(value, captured, freeze):
    binding = value['adaptive_admission']
    need(type(binding) is dict and set(binding) == {
        'schema', 'review', 'callback', 'actor_template', 'assembled_actor', 'program',
        'method', 'execution_authority', 'matched_method_proven_by_grader'}, 'exact successor binding')
    need(binding['schema'] == 'dmfc-stateful-investigator-admission/v2' and
         binding['execution_authority'] is False and binding['matched_method_proven_by_grader'] is False,
         'source admission is not runtime or scientific qualification')
    need(freeze.get('adaptive_admission') == binding, 'closure binds adaptive admission')
    raw = {}
    for name, cap in (('review', 32768), ('callback', 65536), ('actor_template', 65536),
                      ('assembled_actor', 65536), ('program', 65536), ('method', 32768)):
        descriptor = binding[name]
        raw[name] = checked(ROOT, descriptor, cap)
        need(captured.get(descriptor['path']) == raw[name] and
             freeze['files'].get(descriptor['path']) == {k: descriptor[k] for k in ('bytes', 'sha256')},
             'every adaptive operand belongs to the actual captured runtime closure')
    need(len({binding[k]['path'] for k in raw}) == 6, 'distinct source and review operands')
    need({k: binding['actor_template'][k] for k in ('bytes', 'sha256')} == INVESTIGATOR_TEMPLATE_PIN,
         'original case-investigator template')
    need(value['numerical_tool'] == binding['program'] and value['method'] == binding['method'],
         'same reviewed numerical procedure in all four cells')
    review = decode(raw['review'])
    need(type(review) is dict and set(review) == {'schema', 'candidate_id', 'decision', 'reviewer',
         'execution_authority', 'matched_method_proven_by_grader', 'callback', 'program', 'method',
         'method_field_findings', 'checks', 'findings'}, 'exact substantive review')
    need(review['schema'] == 'dmfc-stateful-investigator-review/v2' and review['candidate_id'] == 'NEURAL-095' and
         review['decision'] == 'source_and_procedure_reviewed_for_original_contract' and
         review['execution_authority'] is False and review['matched_method_proven_by_grader'] is False,
         'explicit prospective source review only')
    for name in ('callback', 'program', 'method'):
        need(review[name] == {k: binding[name][k] for k in ('bytes', 'sha256')}, 'reviewed exact operand: ' + name)
    need(type(review['reviewer']) is str and 0 < len(review['reviewer'].strip()) <= 256 and
         type(review['findings']) is str and 0 < len(review['findings'].strip()) <= 8192,
         'attributed substantive review; not authenticated reviewer identity')
    need(type(review['checks']) is dict and set(review['checks']) == set(REVIEW_CHECKS) and
         all(v is True for v in review['checks'].values()), 'all adaptive and frozen procedure checks')
    need(type(review['method_field_findings']) is dict and set(review['method_field_findings']) == set(METHOD_FIELDS)
         and all(type(x) is str and 0 < len(x.strip()) <= 2048 for x in review['method_field_findings'].values()),
         'findings for all original method fields')
    method = read_method(raw['method'])
    profile = method.get('execution_profile', {})
    need(profile.get('schema') == 'dmfc-prepare-frozen-predict-v1' and
         profile.get('training_only_prepare') is True and profile.get('query_tool_has_no_fit_call') is True and
         type(profile.get('fitted_artifact_cap_bytes')) is int and profile['fitted_artifact_cap_bytes'] == 65536 and
         type(profile.get('new_reference_fits')) is int and profile['new_reference_fits'] == 0,
         'original training-only preparation and frozen numerical ABI')
    ast.parse(raw['program'].decode('utf-8'))
    tree = ast.parse(raw['callback'].decode('utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'decide']
    need(len(functions) == 1 and not functions[0].decorator_list, 'one undecorated callback')
    args = functions[0].args
    need(len(args.posonlyargs) + len(args.args) == 1 and not args.vararg and not args.kwarg and
         not args.kwonlyargs and not args.defaults, 'exact decide(context) signature')
    expected = raw['actor_template']
    callback_pin = {k: binding['callback'][k] for k in ('bytes', 'sha256')}
    for old, new in (
        (b'CALLBACK_BASE64 = None  # ASSEMBLED_CALLBACK_BYTES',
         ('CALLBACK_BASE64 = ' + repr(base64.b64encode(raw['callback']).decode('ascii')) + '  # ASSEMBLED_CALLBACK_BYTES').encode()),
        (b'CALLBACK_PIN = None  # ASSEMBLED_CALLBACK_PIN',
         ('CALLBACK_PIN = ' + repr(callback_pin) + '  # ASSEMBLED_CALLBACK_PIN').encode()),
    ):
        need(expected.count(old) == 1, 'single original assembly marker')
        expected = expected.replace(old, new)
    need(raw['assembled_actor'] == expected and len(encode({'op': 'freeze', 'source': expected.decode()}) + b'\n') <= 65536,
         'exact original assembled actor including reviewed callback')
    for key in CONTEXTS:
        arm = value['actor']['arms'][key]
        if key.startswith('case_adaptive__'):
            need(arm['program'] == binding['assembled_actor'], 'same actual adaptive source across views')
        else:
            need({k: arm['program'][k] for k in ('bytes', 'sha256')} == FROZEN_ACTOR_PIN,
                 'byte-identical frozen offline actor')
