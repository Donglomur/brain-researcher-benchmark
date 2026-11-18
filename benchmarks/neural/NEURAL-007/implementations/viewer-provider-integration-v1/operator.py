"""Trusted N007 launcher; no data/provider operation occurs on import.

The client receives only three inherited descriptors and the original viewer
wire. This callable operator is separate from the participant sandbox and does
not claim that canonical full-history provider capacity has been qualified.
"""
from pathlib import Path
import os
import signal
import subprocess
import time


def launch(command, cwd, credential, config_body, directory, transport, deadline):
    """Reuse the N077 descriptor-launch pattern, without dataset paths in child config."""
    owned, child = set(), None
    try:
        ar, aw = os.pipe(); owned.update((ar, aw))
        cr, cw = os.pipe(); owned.update((cr, cw))
        custody = os.dup(directory); owned.add(custody)
        transport.need(len(command) == 5 and command[1:4] == ['-I', '-S', '-B'], 'Original captured-client command')
        # This trusted operator uses the selected site's existing NumPy. The
        # default participant launcher retains -S and its original sandbox.
        argv = [command[0], '-I', '-B', command[4]] + [
            '--credential-fd', str(ar), '--config-fd', str(cr), '--custody-fd', str(custody)]
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 cwd=cwd, env={'LANG': 'C', 'LC_ALL': 'C'}, close_fds=True,
                                 pass_fds=(ar, cr, custody), start_new_session=True)
        for fd in (ar, cr, custody):
            os.close(fd); owned.remove(fd)
        for fd, raw in ((cw, config_body), (aw, credential)):
            os.set_blocking(fd, False)
            transport.write_frame(fd, raw, deadline)
            os.close(fd); owned.remove(fd)
        return child
    except BaseException:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            child.stdin.close(); child.stdout.close()
        raise
    finally:
        for fd in owned:
            os.close(fd)


def run_person_provider(client, runtime, config, packet, session_root, provider_root,
                        credential, python, limits):
    """Existing whole-person transport plus explicit trusted descriptor launcher."""
    budget = client.checked_config(config, runtime)
    transport = runtime['transport']
    transport.need(packet.case == config['case_id'] and packet.epochs == client.CASES[packet.case],
                   'Complete configured original person')
    transport.need(type(credential) is bytes and 0 < len(credential) <= runtime['sender'].CREDENTIAL_CAP
                   and all(33 <= x <= 126 for x in credential), 'Explicit credential bytes')
    transport.need(limits.wall_seconds >= budget.wall_seconds + 2, 'Outer transport must reserve child closure')
    root = Path(provider_root)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    config_body = client.encode(config)
    client_path = Path(config['integration_root']) / 'client.py'
    deadline = time.monotonic() + limits.wall_seconds
    try:
        return transport.run_person(packet, session_root, client_path, python=python, sandbox='protocol_only',
                                    limits=limits,
                                    client_launcher=lambda command, cwd: launch(command, cwd, credential,
                                        config_body, directory, transport, deadline))
    finally:
        os.close(directory)


def run_complete(client, runtime, configs, packets, session_roots, provider_roots,
                 collection_root, credential, python, limits):
    """All 5450 cases or failure; no partial collection or automatic retry.

    Canonical capacity currently fails on the first person's ready frame, so this
    source entry cannot produce a complete provider arm under the fixed policy.
    """
    cases = list(client.CASES)
    client.need(len(configs) == len(packets) == len(session_roots) == len(provider_roots) == 2,
                'Both original people required')
    client.need([p.case for p in packets] == cases and [c['case_id'] for c in configs] == cases
                and [p.epochs for p in packets] == list(client.CASES.values()), 'Exact 5450-case roster')
    common = lambda c: {key: value for key, value in c.items() if key != 'case_id'}
    client.need(common(configs[0]) == common(configs[1]), 'Same declared provider condition and allocations')
    for config, packet, session, provider in zip(configs, packets, session_roots, provider_roots):
        result = run_person_provider(client, runtime, config, packet, session, provider,
                                     credential, python, limits)
        client.need(result['status'] == 'complete_unscored', 'Incomplete provider person; no admission or retry')
    return runtime['transport'].collect(packets, session_roots, collection_root)
