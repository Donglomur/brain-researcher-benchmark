"""Named complete routes. Default is a source plan, never an implicit authentic run."""
import argparse
import json
from pathlib import Path
import sys
import shutil
from .common import need, load, read, pin, put, digest
from .spec import DOMAIN, cases, slots, mode_matrix, campaign


def selection(path, sha):
    body = read(path, 1 << 20)
    need(pin(body)['sha256'] == sha, 'Exact externally selected execution authority')
    value = json.loads(body)
    need(value.get('authority') == 'EXECUTE_AUTHENTIC_NEURAL054' and value.get('task') == 'NEURAL-054',
         'Current BUILD ONLY authority does not authorize this route')
    need(value.get('independent_executor_qualification') == 'ACCEPTED', 'Actual isolation qualification required')
    return value, sha


def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='route')
    sub.add_parser('plan')
    run = sub.add_parser('run')
    for key in ('manifest', 'programs', 'output', 'execution-selection'):
        run.add_argument('--' + key, type=Path, required=True)
    run.add_argument('--selection-sha256', required=True)
    for key in ('admission', 'features-root', 'issuer-secret', 'prior-report', 'prior-provenance'):
        run.add_argument('--' + key, type=Path)
    prep = sub.add_parser('prepare')
    for key in ('admission', 'source-root', 'image-root', 'output', 'execution-selection'):
        prep.add_argument('--' + key, type=Path, required=True)
    prep.add_argument('--selection-sha256', required=True)
    a = p.parse_args()
    if a.route in (None, 'plan'):
        print(json.dumps({'status': 'BUILD_ONLY_SOURCE_PLAN', 'task': 'NEURAL-054', 'new_task_count': 0,
                          'stages': 20, 'obligations': 42, 'folds': len(cases()), 'artifacts_per_family': len(slots()),
                          'full_core_reference_artifacts': 30000, 'summary_reference_artifacts': 12000,
                          'mode_graphs': mode_matrix(), 'scientifically_verified': False}, indent=2)); return
    authority, authority_id = selection(a.execution_selection, a.selection_sha256)
    if a.route == 'prepare':
        from .preparation import extract
        admission = load(a.admission)
        need(digest(admission) == authority['preparation_admission'], 'Selected full preparation admission')
        extract(admission, a.source_root, a.image_root, a.output, authority_id)
        return
    need(sys.platform == 'linux', 'Qualified same-host Linux Docker/cgroup executor required')
    from .views import FeatureIssuer
    from .launcher import Launcher
    from .controller import Controller
    from .report import score
    manifest = load(a.manifest); registry = load(a.programs)
    need(manifest['domain'] == DOMAIN and digest(manifest) == authority['campaign'] and
         digest(registry) == authority['program_registry'],
         'Exact source-owned campaign/admission/registry selection')
    # R-only has no source/features/key/target access and no hidden reference activation.
    requirements = campaign(manifest); prior = provenance = None
    if requirements['standalone_R']:
        need(a.prior_report is not None and a.prior_provenance is not None, 'R-only requires prior report/provenance')
        prior = load(a.prior_report, authority['process_limits']['request_bytes']); provenance = load(a.prior_provenance)
        need(digest(provenance) == authority['prior_provenance'], 'Exact prior report admission')
        class ReportIssuer:
            domain = DOMAIN
            panel = {'domain': DOMAIN, 'generation': manifest['source_generation'], 'slots': [],
                     'target_commitment': None, 'experimental_rows': 0, 'recorded_rows': 0}
            def protected_targets(self): raise ValueError('R-only has no target capability')
        issuer = ReportIssuer()
    else:
        need(a.admission is not None and a.features_root is not None and a.issuer_secret is not None,
             'Predictive routes require complete admitted source')
        admission = load(a.admission)
        need(digest(admission) == authority['feature_admission'], 'Selected full feature admission')
        secret = read(a.issuer_secret, 32)
        issuer = FeatureIssuer(admission, a.features_root, secret, authority_id)
    a.output.mkdir(exist_ok=False)
    launcher = Launcher(a.output / 'processes', DOMAIN, manifest['environment'], authority['process_limits'])
    package = a.output / 'trusted-runtime'
    package.mkdir()
    shutil.copytree(Path(__file__).resolve().parent, package / 'n054', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    controller = Controller(a.output / 'campaign', manifest, issuer, launcher, package, 'n054/trusted_worker.py')
    for record in registry:
        need(record['source_identity'] == digest(__import__('n054.common', fromlist=['tree']).tree(record['source'], 16 << 20, 512)),
             'Selected participant source changed')
        controller.register(record['id'], record['source'], record['entries'])
    disposition = controller.run(score if requirements['prediction'] else None, prior, provenance)
    print(json.dumps(disposition, indent=2))
    if disposition['failure']: raise SystemExit(2)

if __name__ == '__main__': main()
