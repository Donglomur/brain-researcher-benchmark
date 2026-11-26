"""Trusted one-request N031 client. Credentials enter an inherited private pipe."""
import http.client
import math
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parent))
import common as c


def configuration(raw, source_sha256):
    value = c.decode(raw)
    c.need(type(value) is dict and set(value) == {'schema', 'model', 'max_output_tokens',
           'deadline', 'trial_id', 'context_sha256', 'source_sha256'} and
           value['schema'] == 'neural031_provider_client_v1' and value['source_sha256'] == source_sha256,
           'exact_client_configuration')
    c.need(type(value['model']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', value['model']) and
           type(value['max_output_tokens']) is int and 1 <= value['max_output_tokens'] <= 32768,
           'selected_model_output')
    c.need(type(value['deadline']) in (int, float) and math.isfinite(value['deadline']) and
           2 < value['deadline'] - time.monotonic() <= 3600, 'client_deadline')
    for key in ('trial_id', 'context_sha256'):
        c.need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}', value[key]), 'client_context_identity')
    return value


def main(argv=None, *, http_factory=http.client.HTTPSConnection, inp=None, out=None):
    """One production binding path; injected HTTP is solely a generated-test seam."""
    argv = list(sys.argv[1:] if argv is None else argv)
    c.need(len(argv) == 8 and argv[:1] == ['--source-sha256'], 'client_arguments')
    source_sha = argv[1]
    modules = c.load(source_sha)
    donor, bridge = modules['http'], modules['bridge']
    fds = donor.arguments(argv[2:])
    started = time.monotonic()
    alarm = donor.Alarm(started + donor.BOOTSTRAP_SECONDS)
    config = custody = sender = None
    recorded = success = False
    try:
        raw = donor.pipe_body(fds['--config-fd'], donor.CONFIG_CAP, started + donor.BOOTSTRAP_SECONDS)
        os.close(fds.pop('--config-fd'))
        config = configuration(raw, source_sha)
        custody = donor.Custody(fds['--custody-fd'], c.pin(raw), config['deadline'])
        alarm.arm(config['deadline'] - donor.CUSTODY_SECONDS)
        secret = donor.pipe_body(fds['--credential-fd'], donor.CREDENTIAL_CAP,
                                 config['deadline'] - donor.CUSTODY_SECONDS)
        os.close(fds.pop('--credential-fd'))
        c.need(1 <= len(secret) <= donor.CREDENTIAL_CAP and all(33 <= x <= 126 for x in secret), 'credential')
        sender = donor.Sender(config, c.pin(raw), secret.decode('ascii'), custody, bridge, alarm, http_factory)
        del secret

        def record(receipt):
            nonlocal recorded
            c.need(not recorded, 'second_bridge_receipt')
            c.need(sender.credential.encode() not in c.encode(receipt), 'credential_echo')
            custody.json('BRIDGE.json', {'schema': 'neural031_provider_binding_v1',
                         'config_pin': c.pin(raw), 'receipt': receipt})
            c.need(custody.created == donor.FILES and set(os.listdir(custody.fd)) == donor.FILES,
                   'complete_custody_before_output')
            recorded = True

        bridge.serve(sys.stdin.buffer if inp is None else inp, sys.stdout.buffer if out is None else out,
                     model=config['model'], max_output_tokens=config['max_output_tokens'],
                     send_json=sender, record=record)
        c.need(recorded, 'captured_before_emission')
        success = True
    except Exception:
        # Network exceptions can embed secret material. Preserve donor raw custody
        # and fixed categories, never arbitrary exception text.
        success = False
    finally:
        if sender is not None:
            sender.credential = None
        if custody is not None:
            try:
                alarm.arm(config['deadline'])
                if 'REQUEST.bin' not in custody.created:
                    custody.put('REQUEST.bin', b'')
                if 'RESPONSE.bin' not in custody.created:
                    custody.put('RESPONSE.bin', b'')
                if 'HTTP.json' not in custody.created:
                    custody.json('HTTP.json', {'schema': 'neural031_unsent_client_failure_v1',
                                 'requests_attempted': 0, 'failure': 'before_sender'})
                if 'BRIDGE.json' not in custody.created:
                    custody.json('BRIDGE.json', {'schema': 'neural031_provider_binding_v1',
                                 'config_pin': custody.config_pin, 'receipt': None})
            except Exception:
                success = False
        alarm.close()
        for fd in fds.values():
            try:
                os.close(fd)
            except OSError:
                success = False
    return 0 if success else 3


if __name__ == '__main__':
    raise SystemExit(main())
