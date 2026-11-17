"""Closed metadata-to-original-CLI adaptation. No new scientific executor."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def closed(value, keys, name):
    need(type(value) is dict and set(value) == set(keys), name)
    return value


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def named(base, value):
    need(type(value) is str and value, 'named operand path')
    path = PurePosixPath(value)
    need(not path.is_absolute() and str(path) == value and
         all(x not in ('', '.', '..') and x.casefold() != '.git' for x in path.parts), 'canonical operand path')
    return base / value


def descriptor(base, value, prefix, cap):
    closed(value, ('path', 'bytes', 'sha256'), 'exact metadata operand descriptor')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap, 'metadata operand cap')
    path = named(base, value['path'])
    raw = prefix.read(path, value['bytes'], {k: value[k] for k in ('bytes', 'sha256')})
    return path, loads(raw), raw


def call_original(argv):
    from n054.cli import main
    previous = sys.argv
    try:
        sys.argv = ['n054.cli', *argv]
        return main()
    finally:
        sys.argv = previous


def selected_modes(condition, actual):
    if condition == 'selected_campaign':
        return
    need(condition.startswith('modes_'), 'known campaign route')
    mode_string = condition[6:]
    need(mode_string and mode_string == ''.join(m for m in 'PIDR' if m in mode_string), 'canonical nonempty mode subset')
    need(set(mode_string) == set(actual), 'named route may not discard or add selected modes')


def _dispatch(args, prefix, source_pin):
    prefix.dispatch_context = {'route': args.route, 'condition': args.condition}
    if args.route == 'plan':
        # Central operands are not opened on the inherited metadata-only default.
        need(args.condition in ('selected_campaign', 'plan'), 'plan route condition')
        return call_original(['plan'])
    need(args.program is not None and args.review is not None and args.output is not None,
         'run/prepare requires bundle, execution review and fresh output')
    need(type(args.other_reserve_bytes) is int and args.other_reserve_bytes >= 0, 'explicit other reservation')
    review_raw = prefix.read(args.review, 32768); review = loads(review_raw)
    closed(review, ('schema', 'task', 'authority', 'package_source', 'bundle', 'route', 'condition',
                    'other_reserved_bytes', 'central_runtime_qualification', 'original_execution_selection'), 'closed central review')
    need(review['schema'] == 'n054_central_execution_review_v1' and review['task'] == 'NEURAL-054'
         and review['authority'] == 'EXECUTE_AUTHENTIC_NEURAL054', 'separate execution authority required')
    need(review['central_runtime_qualification'] == 'ACCEPTED', 'packaging/host qualification required')
    need(review['package_source'] == source_pin and review['route'] == args.route
         and review['condition'] == args.condition and review['other_reserved_bytes'] == args.other_reserve_bytes,
         'exact reviewed source/route/reservation')
    closed(review['bundle'], ('bytes', 'sha256'), 'exact bundle pin')
    raw = prefix.read(args.program, 32768, review['bundle']); bundle = loads(raw)
    base = Path(args.program).absolute().parent
    closed(bundle, ('schema', 'task', 'execution_selection', 'manifest', 'programs', 'admission',
                   'features_root', 'issuer_secret', 'prior_report', 'prior_provenance', 'source_root', 'image_root'),
           'closed full programme bundle')
    need(bundle['schema'] == 'n054_central_programme_bundle_v1' and bundle['task'] == 'NEURAL-054', 'bundle schema')
    authority_path, authority, _ = descriptor(base, bundle['execution_selection'], prefix, 1 << 20)
    need({k: bundle['execution_selection'][k] for k in ('bytes', 'sha256')} == review['original_execution_selection'], 'original selection pin')
    need(authority.get('authority') == 'EXECUTE_AUTHENTIC_NEURAL054' and authority.get('task') == 'NEURAL-054'
         and authority.get('independent_executor_qualification') == 'ACCEPTED', 'original CLI execution admission')
    argv = [args.route, '--output', str(args.output.absolute()), '--execution-selection', str(authority_path),
            '--selection-sha256', bundle['execution_selection']['sha256']]
    need(not args.output.exists() and not any(p.is_symlink() for p in (args.output, *args.output.parents)), 'fresh output without aliases')
    if args.route == 'prepare':
        need(args.condition == 'selected_campaign', 'separate operator preparation route')
        need(all(bundle[k] is None for k in ('manifest', 'programs', 'features_root', 'issuer_secret', 'prior_report', 'prior_provenance')), 'prepare has no campaign/key operands')
        admission, _, _ = descriptor(base, bundle['admission'], prefix, 16 << 20)
        argv += ['--admission', str(admission), '--source-root', str(named(base, bundle['source_root'])),
                 '--image-root', str(named(base, bundle['image_root']))]
    else:
        from n054.spec import campaign, DOMAIN
        from n054.common import digest
        manifest_path, manifest, _ = descriptor(base, bundle['manifest'], prefix, 16 << 20)
        registry_path, registry, _ = descriptor(base, bundle['programs'], prefix, 16 << 20)
        requirements = campaign(manifest)
        need(manifest['domain'] == DOMAIN and digest(manifest) == authority['campaign']
             and digest(registry) == authority['program_registry'], 'original manifest/registry authority')
        selected_modes(args.condition, requirements['modes'])
        need(type(registry) is list and registry, 'actual source registry')
        ids = []
        for record in registry:
            closed(record, ('id', 'source', 'entries', 'source_identity'), 'original source registry row')
            closed(record['entries'], ('build', 'train', 'predict', 'interpret'), 'all original entrypoints')
            need(type(record['id']) is str and record['id'] and record['id'] not in ids, 'unique programme')
            need(type(record['source']) is str and Path(record['source']).is_absolute(), 'absolute original source root')
            ids.append(record['id'])
        need(set(ids) == {c['program'] for c in manifest['conditions']}, 'exact full selected programme registry')
        need(bundle['source_root'] is None and bundle['image_root'] is None, 'run has no preparation inputs')
        argv += ['--manifest', str(manifest_path), '--programs', str(registry_path)]
        if requirements['standalone_R']:
            need(all(bundle[k] is None for k in ('admission', 'features_root', 'issuer_secret')), 'R-only has no target/source/key capability')
            for key in ('prior_report', 'prior_provenance'):
                # These are paths, not unchecked pins: the original CLI and
                # Controller.interpret own exact prior report/provenance admission.
                argv += ['--' + key.replace('_', '-'), str(named(base, bundle[key]))]
        else:
            need(bundle['prior_report'] is None and bundle['prior_provenance'] is None, 'predictive route has no prior substitute')
            admission, _, _ = descriptor(base, bundle['admission'], prefix, 16 << 20)
            argv += ['--admission', str(admission), '--features-root', str(named(base, bundle['features_root'])),
                     '--issuer-secret', str(named(base, bundle['issuer_secret']))]
    prefix.dispatch_context = {'review_pin': pin(review_raw), 'bundle_pin': pin(raw),
                               'route': args.route, 'condition': args.condition}
    return call_original(argv)


def dispatch(args, prefix, source_pin):
    try:
        return _dispatch(args, prefix, source_pin)
    except BaseException as error:
        prefix.retain_failure(error, 'bridge.dispatch')
        try:
            prefix.enrich_failure(error, 'bridge.dispatch', 'n054_original_dispatch',
                                  prefix.dispatch_context)
        except BaseException as secondary:
            prefix.retain_secondary(secondary, 'bridge.dispatch.enrichment')
        raise
