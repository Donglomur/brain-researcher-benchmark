"""Selected combined-view/programme commands; existing owners retain execution."""
import argparse
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deployment as d

ROOT = HERE.parents[4]
PORTABLE = HERE.parent / 'neural034-portable'
VIEWER = HERE.parent / 'viewer-transport-v1'
OWNER = 'authoring/glial-context-v1/ordinary-completion-v1/run.py'
MANIFEST_SHA = 'fe66143cda6de7f54c4e63b8751262aa6d892f0ae9074c8cbc86665795c9e4f3'


def verify_files(root, files):
    d.need(type(files) is dict and 1 <= len(files) <= 64, 'Finite source closure')
    for name, expected in files.items():
        p = Path(name)
        d.need(type(name) is str and p.as_posix() == name and not p.is_absolute() and
               '..' not in p.parts and set(expected) == {'bytes', 'sha256'}, 'Literal source member')
        d.need(d.pin(d.read(root / name, 1048576)) == expected, 'Source changed: ' + name)


def release(sha):
    body = d.read(HERE / 'SOURCE.json', 65536)
    d.need(d.pin(body)['sha256'] == sha, 'Externally selected release descriptor')
    source = d.decode(body)
    d.need(source['schema'] == 'neural034-combined-workflow-source/v1' and
           source['execution_authority'] is False, 'Source identity is not execution authority')
    verify_files(HERE, source['members'])
    verify_files(ROOT, source['dependencies'])
    manifest_body = d.read(PORTABLE / 'SOURCE_MANIFEST.json', 65536)
    d.need(d.pin(manifest_body)['sha256'] == MANIFEST_SHA, 'Original portable release selected')
    manifest = d.decode(manifest_body)
    current = d.decode(d.read(HERE / 'CURRENT_SOURCE.json', 65536))
    d.need(current['schema'] == 'neural034-current-source/v1' and
           current['historical_manifest'] == {'path': 'SOURCE_MANIFEST.json', **d.pin(manifest_body)} and
           current['execution_authority'] is False and current['native_qualification'] is False and
           set(current['files']) == set(manifest['files']), 'Explicit existing source successor')
    changed = sorted(name for name in current['files'] if current['files'][name] != manifest['files'][name])
    d.need(changed == current['changed_members'] == ['check_result.py', 'provision.py', 'tests/test_relocation.py'],
           'Only existing inspection/provisioning changes; owner/science remain original')
    verify_files(PORTABLE, current['files'])
    return current


def workspace_source(workspace, manifest):
    workspace = d.literal(workspace)
    d.need(workspace.is_dir() and workspace.stat().st_mode & 0o077 == 0,
           'Provisioned operator-only workspace, never participant access')
    d.need(d.pin(d.read(workspace / 'SOURCE_MANIFEST.json', 65536))['sha256'] == MANIFEST_SHA,
           'Same original workspace source release')
    d.need(d.read(workspace / 'CURRENT_SOURCE_MANIFEST.json', 65536) ==
           d.read(HERE / 'CURRENT_SOURCE.json', 65536), 'Selected existing successor in workspace')
    verify_files(workspace, manifest['files'])
    # This is source verification, not a claim that provisioning terminated or
    # that authentic input bodies have been revalidated. Existing owners do that.
    return workspace


def packets(workspace):
    return [str(workspace / f'artifacts-build/glial-context-002/fold-{fold:02d}/public.npz')
            for fold in range(7)]


def command(args, manifest):
    """Build exact existing command; no import of task arrays, viewer or scorer."""
    # Preserve the selected virtual environment. Resolving its interpreter
    # symlink would silently switch the operator back to the system environment.
    python = str(Path(sys.executable).absolute())
    env = dict(os.environ)
    cwd = ROOT
    if args.operation == 'provision':
        argv = [python, '-I', '-B', str(PORTABLE / 'provision.py'), '--manifest-sha256',
                MANIFEST_SHA, '--inputs', str(d.literal(args.inputs)),
                '--workspace', str(d.literal(args.workspace)), '--current-source-manifest',
                str(HERE / 'CURRENT_SOURCE.json'), '--current-source-manifest-sha256',
                d.pin(d.read(HERE / 'CURRENT_SOURCE.json', 65536))['sha256']]
    else:
        workspace = workspace_source(args.workspace, manifest)
        cwd = workspace
        if args.operation == 'program':
            d.need(args.other_reserve_bytes >= 400000000, 'Complete other reservation floor')
            # No template is promoted and no authority/cost field is synthesized.
            for key in list(env):
                if key.startswith('DOCKER_'):
                    del env[key]
            env['NEURAL034_DOCKER'] = str(d.literal(args.docker))
            env['NEURAL034_DOCKER_HOST'] = args.host
            argv = [python, '-I', '-B', str(workspace / OWNER), '--program',
                    str(d.literal(args.program)), '--out', str(d.literal(args.output)),
                    '--review', str(d.literal(args.review)), '--other-reserve-bytes',
                    str(args.other_reserve_bytes)]
        elif args.operation == 'check-program':
            argv = [python, '-I', '-B', str(workspace / 'check_result.py'),
                    '--output', str(d.literal(args.output))]
        elif args.operation == 'viewer-fold':
            argv = [python, '-I', '-B', str(VIEWER / 'transport.py'), 'fold', '--fold', str(args.fold),
                    '--packet', packets(workspace)[args.fold], '--client', str(d.literal(args.client)),
                    '--python', str(d.literal(args.client_python)), '--sandbox', 'macos',
                    '--max-actions', str(args.max_actions), '--max-images', str(args.max_images),
                    '--max-output-bytes', str(args.max_output_bytes), '--wall-seconds', str(args.wall_seconds),
                    '--output', str(d.literal(args.output))]
        else:
            d.need(args.operation == 'viewer-collect', 'Fixed operation set')
            sessions = d.literal(args.sessions)
            argv = [python, '-I', '-B', str(VIEWER / 'transport.py'), 'collect',
                    '--packets', *packets(workspace), '--sessions',
                    *[str(sessions / f'fold-{i:02d}') for i in range(7)],
                    '--output', str(d.literal(args.output))]
    return argv, env, str(cwd)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release-sha256', required=True)
    p.add_argument('--plan-only', action='store_true', help='Source checks and command only; no task/Engine invocation')
    sub = p.add_subparsers(dest='operation', required=True)
    probe = sub.add_parser('runtime-check')
    probe.add_argument('--docker', required=True); probe.add_argument('--host', required=True)
    probe.add_argument('--config', required=True)
    for name in ('provision', 'program', 'check-program', 'viewer-fold', 'viewer-collect'):
        part = sub.add_parser(name)
        part.add_argument('--workspace', type=Path, required=True)
        if name == 'provision':
            part.add_argument('--inputs', type=Path, required=True)
            continue
        part.add_argument('--output', type=Path, required=True)
        if name == 'program':
            part.add_argument('--program', type=Path, required=True)
            part.add_argument('--review', type=Path, required=True)
            part.add_argument('--other-reserve-bytes', type=int, required=True)
            part.add_argument('--docker', required=True); part.add_argument('--host', required=True)
        elif name == 'viewer-fold':
            part.add_argument('--fold', type=int, choices=range(7), required=True)
            part.add_argument('--client', type=Path, required=True)
            part.add_argument('--client-python', type=Path, required=True)
            part.add_argument('--max-actions', type=int, required=True)
            part.add_argument('--max-images', type=int, required=True)
            part.add_argument('--max-output-bytes', type=int, required=True)
            part.add_argument('--wall-seconds', type=float, required=True)
        elif name == 'viewer-collect':
            part.add_argument('--sessions', type=Path, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    manifest = release(args.release_sha256)
    if args.operation == 'runtime-check':
        d.need(not args.plan_only, 'runtime-check is itself read-only; omit plan-only')
        print(__import__('json').dumps(d.observe(args.docker, args.host, args.config), sort_keys=True))
        return
    argv, env, cwd = command(args, manifest)
    if args.plan_only:
        print(__import__('json').dumps({'argv': argv, 'cwd': cwd, 'execution_authority': False,
              'runtime_qualified': False, 'authentic_inputs_opened': False}, sort_keys=True))
        return
    if args.operation == 'program':
        # Still only availability. The unchanged owner subsequently checks the
        # independent runtime qualification, attempt authority, cost and census.
        d.observe(args.docker, args.host, Path(args.workspace) / '.cache-build/docker-config')
    os.chdir(cwd)
    os.execve(argv[0], argv, env)  # No second owner, background job or timeout/retry layer.


if __name__ == '__main__':
    main()
