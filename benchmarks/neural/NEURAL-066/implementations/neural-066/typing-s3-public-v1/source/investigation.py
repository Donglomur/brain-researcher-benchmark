"""Concrete offline case-local authoring, frozen policy, fresh-state admission.

All candidate execution is transported to isolated workers. Host code never
imports candidate code or reads executable model state.
"""
import failures
import copy
from pathlib import Path
from core import MODES, encoded, exact, identity, need
from safe_io import pin, strict, child
from assembly import candidate_bindings
from transport.model import Session
from transport.vendor.bounds import mount_identity
from content_admission import request_and_wait
ACTION_SCHEMA = {'type': 'object', 'properties': {'action': {'enum': ['inspect', 'train_validate', 'finalize']}, 'source': {'type': 'object'}, 'recipe': {'type': 'object'}, 'rationale': {'type': 'string'}}, 'required': ['action', 'source', 'recipe', 'rationale'], 'additionalProperties': False}

def source(ws, value, name, limits):
    exact(value, ('entry', 'files'))
    need(type(value['files']) is dict and 0 < len(value['files']) <= limits['max_source_files'] and (value['entry'] in value['files']) and ('/' not in value['entry']), 'Complete bounded source bundle with root entry')
    total = 0
    bindings = {}
    for relative, body in sorted(value['files'].items()):
        need(relative.endswith('.py') and type(body) is str and ('\x00' not in body), 'UTF8 text source only')
        raw = body.encode()
        total += len(raw)
        need(total <= limits['source_bytes'], 'Complete source cap before publication')
        path = child(ws.root / name, relative)
        path.parent.mkdir(mode=448, parents=True, exist_ok=True)
        d = ws.budget.save(path, raw)
        bindings[relative] = {'source_path': str(path), 'bytes': d['bytes'], 'sha256': d['sha256']}
    return ({'entry': value['entry'], 'files': {p: {k: d[k] for k in ('bytes', 'sha256')} for p, d in bindings.items()}}, bindings)

def author(controller, job, public):
    ws = controller.ws
    op = controller.op
    limits = op['candidate']
    context = identity([public['view']['case'], job['mode'], job['condition']])
    role = controller.role(job)
    prefix = 'contexts/' + job['phase_id']
    mode = job['mode']
    used = 0
    session = None
    closed = False
    history = []
    selected = None
    provider_close = None

    def tool(bundle, recipe, realm, stage):
        nonlocal used
        need(used < limits['max_preliminary_tools'], 'One shared author/policy T budget')
        used += 1
        name = prefix + '/tool-' + str(used)
        submitted, bindings = source(ws, bundle, name + '/source', limits)
        data, manifest = candidate_bindings(ws, public, realm, name + '/metadata')
        job_body = controller.candidate_request(job, 'candidate_policy', submitted, recipe, realm)
        job_body['policy_stage'] = stage
        result = controller.run_nested(job, used, job_body, data, bindings)
        observation = ws.read(ws.from_capture(result, 'OBSERVATION.json')['source_path'], result['output_files']['OBSERVATION.json'])
        need(type(observation) is dict and observation.get('action') in ('inspect', 'train_validate', 'select', 'finalize'), 'Typed complete observation')
        history.append({'stage': stage, 'realm': realm, 'result': result, 'observation': observation})
        return observation
    cfg = copy.deepcopy(op['model_transport'])
    mounts = controller.provider_mounts
    profile = controller.provider_profile
    models = controller.provider_models
    template = controller.provider_admission
    need(template['approved_rule'] == 'neural066_exact_fresh_context_model_v1' and template['source'] == cfg['source'] and (template['image'] == cfg['image']) and (template['immutable_mounts'] == mount_identity({**mounts, '/profile.json': profile, '/models': models})), 'Root-qualified mechanical derivation, not invented independent review')
    admission = {**template, 'context': context, 'mailbox_policy': 'fresh_readonly_append_only_current_context'}
    ad = ws.json(prefix + '/PROVIDER_ADMISSION.json', admission)
    cfg.update(admission_path=ad['source_path'], admission_pin={k: ad[k] for k in ('bytes', 'sha256')})
    controller.reserve_model(job, cfg)
    controller.model_started = True
    try:
        session = Session(cfg, ws.root / prefix / 'provider', context, controller.phase_clock(), mounts, profile, models)
        session.start()
        prompt = {'schema': 'neural066_case_author_prompt_v1', 'mode': mode, 'condition': job['condition'], 'context': {k: public['view'][k] for k in ('case', 'generation', 'condition', 'modality', 'feature_dimensions', 'channels', 'samples_per_key')}, 'input_ABI': controller.public_contract, 'query_access_before_source_seal': mode == MODES[1], 'remaining_shared_preliminary_tools': limits['max_preliminary_tools'], 'requirements': 'Propose Python run/fit/predict source. No external task corpus/checkpoints. Query diagnostics may propose; final model/settings/learned state selected on train/inner-validation only. No preliminary fitted state in final source or recipe. Provider language pretraining is admitted. Full query batch, zero labeled target calibration. All other cases forbidden.'}
        for turn in range(limits['max_provider_turns']):
            action, trace = session.generate(encoded(prompt).decode(), ACTION_SCHEMA)
            exact(action, ('action', 'source', 'recipe', 'rationale'))
            need(type(action['recipe']) is dict and type(action['rationale']) is str, 'Complete action')
            need(len(encoded(action['recipe'])) <= limits['recipe_bytes'], 'Full recipe cap')
            ws.json(prefix + '/action-' + str(turn) + '.json', {'action': action, 'trace': trace})
            if action['action'] == 'finalize':
                selected = action
                break
            need(used + 2 < limits['max_preliminary_tools'], 'Reserve the same shared T for the two mandatory post-seal policy realms')
            need(action['action'] in ('inspect', 'train_validate'), 'No arbitrary provider action')
            realm = 'diagnostic' if action['action'] == 'inspect' and mode == MODES[1] else 'train'
            observed = tool(action['source'], action['recipe'], realm, 'author_' + action['action'])
            prompt = {**prompt, 'previous_action': action['action'], 'observation': observed, 'remaining_shared_preliminary_tools': limits['max_preliminary_tools'] - used}
        need(selected is not None, 'Complete source seal within finite provider turns')
        source_desc, bindings = source(ws, selected['source'], prefix + '/final-source', limits)
        seal = ws.json(prefix + '/SOURCE_SEAL.json', {'source': source_desc, 'mode': mode, 'context': context, 'before_any_frozen_query_access': mode == MODES[0], 'rationale': selected['rationale']})
        close = session.close()
        provider_close = close
        closed = close['all_native_resources_closed'] is True
        controller.model_closed(job, close)
        need(closed, 'Provider completely retired before post-seal computations')
        proposal = tool(selected['source'], selected['recipe'], 'diagnostic', 'query_proposal')
        need(proposal['action'] in ('inspect', 'train_validate', 'select'), 'Query realm cannot finalize a fitted recipe')
        choice = tool(selected['source'], {'initial_recipe': selected['recipe'], 'proposal': proposal}, 'train', 'training_selection')
        need(choice['action'] == 'finalize' and type(choice.get('recipe')) is dict, 'Training-only final selection must emit explicit recipe')
        final_recipe = choice['recipe']
        need(len(encoded(final_recipe)) <= limits['recipe_bytes'], 'Complete selected recipe extent')
        rp = ws.json(prefix + '/RECIPE_SEAL.json', {'recipe': final_recipe, 'source_seal': seal, 'selection': 'training_only', 'shared_T_used': used})
        review_payload = {'source_seal': seal, 'recipe_seal': rp, 'provider_close': ws.json(prefix + '/PROVIDER_CLOSE.json', close), 'provisional_operator_only': ws.json(prefix + '/PROVISIONAL_EVIDENCE.json', history), 'selected_rationale': selected['rationale'], 'query_proposal_disclosed': True}
        admitted = request_and_wait(op['method_review']['root'], context, 'final_source_and_recipe', review_payload, op['method_review']['authority'], ws.budget, op['method_review']['limits'])
        return {'submitted': source_desc, 'bindings': bindings, 'recipe': final_recipe, 'source_seal': seal, 'recipe_seal': rp, 'independent_content_admission': admitted, 'preliminary_tools': used, 'provider_closed': True}
    except BaseException as exc:
        failures.hold(exc, 'caught')
        recovery = None
        secondary = []
        if provider_close is not None:
            failures.remember(exc, 'neural066_provider_close', provider_close)
        if session is not None and (not session.closed):
            try:
                recovery = session.abort()
                closed = recovery.get('custody') == 'closed'
            except BaseException as cleanup:
                failures.hold(cleanup, 'caught')
                closed = False
                secondary.append({'stage': 'provider_abort', 'type': failures.kind(cleanup), 'message': failures.describe(cleanup)})
                failures.note(exc, 'Provider abort failed: ' + failures.kind(cleanup))
            if recovery is not None:
                failures.remember(exc, 'neural066_provider_failure', recovery)
                try:
                    controller.record_model_failure(job, recovery)
                except BaseException as publication:
                    failures.hold(publication, 'caught')
                    secondary.append({'stage': 'provider_failure_journal', 'type': failures.kind(publication), 'message': failures.describe(publication)})
                    failures.note(exc, 'Provider failure journal unavailable: ' + failures.kind(publication))
        controller.model_closed_flags[job['phase_id']] = closed
        failures.remember(exc, 'neural066_secondary_failures', secondary)
        raise
