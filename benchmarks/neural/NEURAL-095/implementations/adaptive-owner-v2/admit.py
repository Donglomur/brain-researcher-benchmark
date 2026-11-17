"""Attach an existing request or delegate to the actual deployed owner.

No grants, capacity witnesses, data or daemon identities are manufactured here.
The caller explicitly pins the construction record and complete configuration.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def support(root, deployment_sha256):
    spec = importlib.util.spec_from_file_location('_adaptive_owner_builder', HERE / 'configure.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    c, unused = builder.helpers()
    root = c.ordinary(root)
    raw = c.capture(root / 'DEPLOYMENT.json')
    c.need(c.pin(raw)['sha256'] == deployment_sha256, 'exact prospective deployment selection')
    record = c.decode(raw)
    c.need(record['schema'] == 'dmfc-stateful-owner-deployment/v2' and record['execution_authority'] is False,
           'source-only successor deployment')
    path = c.BASE + '/configuration.py'
    raw = c.capture(root / path)
    c.need(c.pin(raw) == record['rendered_sources'][path], 'selected actual configuration gate')
    cm = builder.module('_adaptive_owner_deployed_gate', root / path, raw)
    return c, cm, record


def attach(root, deployment_sha256, payload, payload_sha256, request, request_sha256, output):
    c, cm, record = support(root, deployment_sha256)
    root = c.ordinary(root)
    raw = c.capture(payload)
    c.need(c.pin(raw)['sha256'] == payload_sha256 and c.pin(raw) ==
           {k: record['payload'][k] for k in ('bytes', 'sha256')}, 'exact constructed payload')
    value = c.decode(raw)
    request = c.ordinary(request); output = c.ordinary(output)
    c.need(request.is_relative_to(root) and output.is_relative_to(root) and
           output.parent.is_dir() and not output.exists(), 'ordinary local existing request and fresh configuration')
    body = c.capture(request)
    c.need(c.pin(body)['sha256'] == request_sha256, 'explicit existing request pin')
    existing = c.decode(body)
    c.need(existing['configuration_payload_sha256'] == c.pin(c.canonical(value))['sha256'],
           'existing request selects complete successor payload')
    value['request'] = {'path': request.relative_to(root).as_posix(), **c.pin(body)}
    raw = c.encode(value)
    # Construction only: current authority/capacity still checked by the owner.
    with output.open('xb') as stream:
        c.need(stream.write(raw) == len(raw), 'complete configuration write')
    output.chmod(0o444)
    return {'configuration': {'path': str(output), **c.pin(raw)}, 'execution_authority': False}


def command(root, deployment_sha256, configuration, configuration_sha256):
    c, cm, record = support(root, deployment_sha256)
    root = c.ordinary(root)
    config, captured, freeze = cm.load(configuration, configuration_sha256)
    c.need(config.value['repository_root'] == str(c.ordinary(root)), 'same deployed root')
    # Bind this source selection to the construction record, in addition to the
    # config/request/closure joins validated by the actual configuration loader.
    payload = {k: v for k, v in config.value.items() if k != 'request'}
    c.need(c.pin(c.canonical(payload))['sha256'] == record['payload_sha256_for_operator_request'],
           'runtime selects the constructed successor payload')
    entry = freeze['entrypoint']
    c.need(record['rendered_sources'][entry['path']] == {k: entry[k] for k in ('bytes', 'sha256')},
           'original selected owner entrypoint')
    return [sys.executable, '-I', '-B', str(Path(root) / entry['path']), '--config',
            str(Path(configuration).absolute()), '--config-sha256', configuration_sha256]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--deployment-sha256', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('attach')
    for name in ('payload', 'payload-sha256', 'request', 'request-sha256', 'output'):
        prepare.add_argument('--' + name, required=True)
    run = sub.add_parser('run')
    run.add_argument('--configuration', required=True); run.add_argument('--configuration-sha256', required=True)
    run.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.action == 'attach':
        result = attach(args.root, args.deployment_sha256, args.payload, args.payload_sha256,
                        args.request, args.request_sha256, args.output)
    else:
        cmd = command(args.root, args.deployment_sha256, args.configuration, args.configuration_sha256)
        if not args.dry_run:
            os.execv(sys.executable, cmd)
        result = {'argv': cmd, 'execution_authority': False, 'runtime_qualified': False}
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
