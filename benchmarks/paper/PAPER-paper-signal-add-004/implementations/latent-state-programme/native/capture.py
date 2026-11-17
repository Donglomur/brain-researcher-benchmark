"""Build pinned observation-only AST derivatives; never execute author source.

Only the exact added import/calls may be removed by the preservation proof.
The source expressions in POINTS are fixed implementation, never user input.
The future trusted process installs native.sink before running a derivative.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path

REVISION = "cded3b2ea95efef7b6c089c5e111fd565b716922"
WRAPPERS = "osl_dynamics/config_api/wrappers.py"
SCRIPTS = {
    "ctf_bursts": "examples/toolbox_paper/ctf_rest/tde_hmm_bursts.py",
    "elekta_ae": "examples/toolbox_paper/elekta_task/ae_hmm.py",
    "elekta_tde": "examples/toolbox_paper/elekta_task/tde_hmm.py",
    "ctf_tde": "examples/toolbox_paper/ctf_rest/tde_hmm_networks.py",
    "ctf_dynemo": "examples/toolbox_paper/ctf_rest/tde_dynemo_networks.py",
    "ctf_static": "examples/toolbox_paper/ctf_rest/static_networks.py",
}


def point(scope, target, label, values, occurrence=1, before=False, kind="arrays"):
    return dict(scope=scope, target=target, label=label, values=values,
                occurrence=occurrence, before=before, kind=kind)


POINTS = {path: [] for path in SCRIPTS.values()}
POINTS[WRAPPERS] = []
for func, kind in [("train_hmm", "model_hmm"), ("train_dynemo", "model_dynemo")]:
    POINTS[WRAPPERS] += [
        point(func, "ENTRY", "coordinates", "{'data': data}", kind="coordinates"),
        point(func, "history['free_energy']", "model", "{'free_energy': history['free_energy']}"),
        point(func, "history['free_energy']", "training", "{'config': vars(config), 'config_kwargs': config_kwargs, 'init_kwargs': init_kwargs, 'fit_kwargs': fit_kwargs, 'init_history': init_history, 'history': history}", kind="structured"),
        point(func, "(means, covs)", "model", "{'means': means, 'covs': covs, 'alpha': alpha, 'model': model}", kind=kind),
    ]
for func in ["multitaper_spectra", "regression_spectra"]:
    POINTS[WRAPPERS] += [
        point(func, "data", "spectral_input", "{'runs': data}", kind="run_identity"),
        point(func, "(f, psd, coh)", "spectra", "{'f': f, 'psd': psd, 'coh': coh}"),
    ]
POINTS[WRAPPERS] += [
    point("multitaper_spectra", "nnmf", "spectra", "{'nnmf': nnmf}"),
    point("plot_state_psds", "psd", "burst_group", "{'psd': psd}", 2),
    point("plot_tde_covariances", "CALL:plotting.plot_matrices", "burst_group", "{'tde_covs': covs}", before=True),
    point("plot_burst_summary_stats", "amp", "summary", "{'lt': lt, 'intv': intv, 'bc': bc, 'amp': amp}"),
    point("plot_hmm_network_summary_stats", "sr", "summary", "{'fo': fo, 'lt': lt, 'intv': intv, 'sr': sr}"),
    point("plot_dynemo_network_summary_stats", "CALL:save", "summary", "{'alp_mean': alp_mean, 'alp_std': alp_std, 'alp_corr': alp_corr}", before=True),
    point("plot_group_ae_networks", "CALL:connectivity.save", "ae_network", "{'aecs': aecs}", before=True),
]
for func in ["plot_group_nnmf_tde_hmm_networks", "plot_group_tde_dynemo_networks"]:
    POINTS[WRAPPERS] += [
        point(func, "w", "source_weights", "{'weights': w}", 2, kind="weights"),
        point(func, "gcoh", "group_spectra", "{'psd': gpsd, 'coh': gcoh}"),
        point(func, "e", "group_spectra", "{'channel_mean': p, 'channel_sem': e}"),
        point(func, "gp", "network", "{'power': gp}"),
        point(func, "gc", "network", "{'coherence_unthresholded': gc}"),
        point(func, "gc", "network", "{'coherence_thresholded': gc}", 2),
    ]
POINTS[SCRIPTS['ctf_bursts']] += [
    point("plot_amplitude_envelopes_and_alpha", "corr", "burst_envelopes", "{'correlation': corr, 'envelopes': x}"),
]
for branch in ['elekta_ae', 'elekta_tde']:
    POINTS[SCRIPTS[branch]] += [
        point("epoch_state_time_course", "parc_files", "event", "{'stc': stc, 'parc_files': parc_files}", kind="event_input"),
        point("epoch_state_time_course", "CALL:epochs_.append", "event_trials", "{'trials': epochs_[-1], 'events_found': events, 'events_retained': e.events, 'times': e.times, 'parc_file': p, 'event_id': event_id}", kind="event_trials"),
        point("epoch_state_time_course", "RETURN", "event", "{'t': t, 'epochs': epochs}", before=True),
        point("plot_evoked_response", "pvalues", "event", "{'pvalues': pvalues}"),
    ]
POINTS[SCRIPTS['ctf_tde']] += [
    point("compare_summary_stats", "sum_stats", "age_summary", "{'values': sum_stats, 'assignments': assignments}"),
    point("compare_summary_stats", "(_, p)", "age_summary", "{'effect': _, 'pvalues': p}"),
    point("compare_power_maps", "power_maps", "age_power", "{'values': power_maps, 'assignments': assignments}"),
    point("compare_power_maps", "(power_map_diff, p)", "age_power", "{'effect': power_map_diff, 'pvalues': p}"),
    point("compare_power_maps", "power_map_diff[~significant]", "age_power", "{'masked_effect': power_map_diff}"),
    point("compare_coherence_networks", "(c_diff, p)", "age_coherence", "{'values': c, 'effect': c_diff, 'pvalues': p, 'assignments': assignments}"),
    point("compare_coherence_networks", "CALL:connectivity.save", "age_coherence", "{'masked_matrix': coh_diff}", before=True),
]
POINTS[SCRIPTS['ctf_dynemo']] += [
    point("compare_summary_stats", "sum_stats", "age_summary", "{'values': sum_stats, 'assignments': assignments}"),
    point("compare_summary_stats", "(_, p)", "age_summary", "{'effect': _, 'pvalues': p}"),
]
POINTS[SCRIPTS['ctf_static']] += [
    point("<module>", "data", "coordinates", "{'data': data}", kind="coordinates"),
    point("<module>", "(f, psd, coh)", "spectra", "{'f': f, 'psd': psd, 'coh': coh}"),
    point("<module>", "pow_map", "static", "{'power': pow_map}", 2),
    point("<module>", "coh_net", "static", "{'coherence': coh_net}", 2),
    point("<module>", "aec", "static", "{'aec': aec}", 3),
    point("<module>", "CALL:power.save", "static_group", "{'power': mean_pow_map}", before=True),
    point("<module>", "CALL:connectivity.save", "static_group", "{'coherence': mean_coh_net}", before=True),
    point("<module>", "CALL:connectivity.save", "static_group", "{'aec': mean_aec}", 2, before=True),
    point("<module>", "(pow_diff, pvalues)", "age_power", "{'effect': pow_diff, 'pvalues': pvalues, 'assignments': assignments}"),
    point("<module>", "(aec_diffs, pvalues)", "age_aec", "{'effect': aec_diffs, 'pvalues': pvalues, 'values': aec}"),
    point("<module>", "aec_diffs", "age_aec", "{'masked_matrix': aec_diffs}"),
]


def instrument(body, key):
    """Return derivative bytes and an exact removable-node preservation proof."""
    tree = ast.parse(body)
    if any(isinstance(n, ast.Name) and n.id == '_osl19_observe' for n in ast.walk(tree)):
        raise ValueError('Capture name already exists in original')
    original = ast.dump(tree, include_attributes=False)
    points = POINTS[key]
    seen = [0] * len(points)
    inserted = []
    locations = []

    class Add(ast.NodeTransformer):
        scope = '<module>'

        def hooks(self, target, node):
            before, after = [], []
            for i, p in enumerate(points):
                if p['scope'] == self.scope and p['target'] == target:
                    seen[i] += 1
                    if seen[i] == p['occurrence']:
                        call = ast.parse('_osl19_observe(' + repr(p['label']) + ',' + p['values'] + ',' + repr(p['kind']) + ')').body[0]
                        inserted.append(ast.dump(call, include_attributes=False))
                        locations.append(dict(point=i, source_line=node.lineno, **p))
                        (before if p['before'] else after).append(call)
            return before, after

        def visit_FunctionDef(self, node):
            prior = self.scope
            self.scope = node.name
            b, a = self.hooks('ENTRY', node)
            self.generic_visit(node)
            index = int(bool(node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)))
            node.body[index:index] = b + a
            self.scope = prior
            return node

        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0]) if len(node.targets) == 1 else ''
            b, a = self.hooks(target, node)
            return b + [node] + a

        def visit_Expr(self, node):
            target = 'CALL:' + ast.unparse(node.value.func) if isinstance(node.value, ast.Call) else ''
            b, a = self.hooks(target, node)
            return b + [node] + a

        def visit_Return(self, node):
            b, a = self.hooks('RETURN', node)
            if a:
                raise ValueError('Return capture must occur before return')
            return b + [node]

    tree = Add().visit(tree)
    if sorted(p['point'] for p in locations) != list(range(len(points))):
        raise ValueError('Missing exact source capture point: ' + str(locations))
    imp = ast.parse('from native.sink import observe as _osl19_observe').body[0]
    index = int(bool(tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str)))
    tree.body.insert(index, imp)
    added = inserted + [ast.dump(imp, include_attributes=False)]
    derivative = (ast.unparse(ast.fix_missing_locations(tree)) + '\n').encode()
    counts = {x: added.count(x) for x in added}

    class Strip(ast.NodeTransformer):
        def generic_visit(self, node):
            stamp = ast.dump(node, include_attributes=False)
            if stamp in counts and counts[stamp]:
                counts[stamp] -= 1
                return None
            return super().generic_visit(node)

    stripped = Strip().visit(ast.parse(derivative))
    if any(counts.values()) or ast.dump(stripped, include_attributes=False) != original:
        raise ValueError('Original noncapture AST changed')
    return derivative, {'source_sha256': hashlib.sha256(body).hexdigest(),
                        'derivative_sha256': hashlib.sha256(derivative).hexdigest(),
                        'original_noncapture_ast_sha256': hashlib.sha256(original.encode()).hexdigest(),
                        'noncapture_ast_preserved': True, 'locations': locations}


def build(source_root, out, bindings):
    """Fresh source-only tree. Does not import, install or execute author code."""
    source_root, out = Path(source_root), Path(out)
    if out.exists():
        raise ValueError('Fresh derivative directory required')
    staged = []
    for key in list(SCRIPTS.values()) + [WRAPPERS]:
        body = (source_root / key).read_bytes()
        pin = bindings['files'][key]
        if len(body) != pin['bytes'] or hashlib.sha256(body).hexdigest() != pin['sha256']:
            raise ValueError('Original source pin mismatch: ' + key)
        derivative, proof = instrument(body, key)
        staged.append((key, derivative, proof))
    out.mkdir(parents=True)
    for key, derivative, _ in staged:
        target = out / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(derivative)
    receipt = {'schema': 'osl19_observation_derivatives_v1', 'revision': REVISION,
               'sink_module': 'native.sink', 'installation': 'install_sink(CaptureSink(...)) in same trusted interpreter before runpy',
               'author_execution': False, 'files': [{'path': k, **p} for k, _, p in staged]}
    (out / 'CAPTURE_MAP.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt
