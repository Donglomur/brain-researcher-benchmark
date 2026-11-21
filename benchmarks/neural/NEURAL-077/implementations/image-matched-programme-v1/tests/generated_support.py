"""Generated-only fixtures. Imported only by the coordinator's selected campaign.

No original packet, signal, key, target, provider or process is opened. The fixed
legacy asset pins are replaced only inside tests with generated asset pins. The
production source has no override. All declared query spans are written once.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import types

PROFILE = 'erp-full32-visual-v1'
CONDITIONS = ('visual_direct_four_demo', 'visual_program_four_demo')
WRITE_CAP = 92 * 1024**2 - 128 * 1024  # Prior zero-fixture setup reserve stays charged.
# Separate120MiB covers source/packet/PNG/snapshot file reads.
READ_CAP = 160 * 1024**2
WRITTEN = 0
SUPPLIED = 0


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def charge_write(body):
    global WRITTEN
    if WRITTEN + len(body) > WRITE_CAP:
        raise AssertionError('Cumulative generated fixture writes exceed selected cap')
    WRITTEN += len(body)


def write(path, body):
    charge_write(body)
    Path(path).write_bytes(body)


def load(name, path):
    path = Path(path)
    body = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


class Packet:
    """Exactly6400 generated queries, four generated demos,32 complete shards."""
    def __init__(self, root, consumer):
        self.root = Path(root)
        self.root.mkdir()
        (self.root / 'queries').mkdir()
        self.ids = tuple('q-' + format(i + 1, '032x') for i in range(6400))
        channels = [[(i % 17 - 8) for i in range(1024)], [(i % 13 - 6) for i in range(1024)]]
        demos = [{'trial_id': 'generated-demo-' + str(i), 'channels': channels, 'target': i % 2} for i in range(4)]
        assets = {'demonstrations.json': encode(demos),
                  'prompt.txt': (consumer.NO_TOOLS + '\n{{demonstrations_json}}\n{{query_json}}\n').encode(),
                  'response_schema.json': encode({'generated': True})}
        self.legacy_pins = {k: pin(v) for k, v in assets.items()}
        self.files = dict(self.legacy_pins)
        self.roster = []
        for name, body in assets.items():
            write(self.root / name, body)
        for shard in range(32):
            name = 'queries/p-' + format(shard + 1, '024x') + '.jsonl'
            chunks = []
            position = 0
            for i in range(shard * 200, (shard + 1) * 200):
                body = encode({'trial_id': self.ids[i], 'channels': channels})
                assert len(body) == 5121, 'Exact generated query fixture extent'
                self.roster.append({'trial_id': self.ids[i], 'path': name, 'offset': position, **pin(body)})
                chunks.append(body)
                position += len(body)
            body = b''.join(chunks)
            write(self.root / name, body)
            self.files[name] = pin(body)
        self.manifest = {'schema': 'erp-core-full32-public-packet-v1', 'benchmark_id': 'NEURAL-077',
                         'condition_id': consumer.CONDITION_ID, 'people': 32, 'query_count': 6400,
                         'demonstration_count': 4, 'natural_class_prior_supplied': False, 'files': self.files}
        self.restore()

    def roster_variant(self, rows):
        raw = encode(rows)
        assert len(raw) <= 1920000, 'Generated roster fixture cap'
        write(self.root / 'roster.json', raw)
        self.files['roster.json'] = pin(raw)
        raw = encode(self.manifest)
        assert len(raw) <= 65536, 'Generated manifest fixture cap'
        write(self.root / 'PACKET.json', raw)
        self.manifest_pin = pin(raw)
        return self.manifest_pin

    def restore(self):
        return self.roster_variant(self.roster)


class Alarm:
    """Existing sender alarm boundary; no real signal or worker is launched."""
    def arm(self, deadline):
        self.deadline = deadline


class Response:
    status = 200
    def __init__(self, raw):
        self.raw, self.at, self.length = raw, 0, len(raw)
    def read(self, size):
        value = self.raw[self.at:self.at + size]
        self.at += len(value)
        self.length -= len(value)
        return value
    def getheader(self, key, default=None):
        return 'identity' if key.lower() == 'content-encoding' else default
    def close(self):
        pass


class HTTP:
    """Finite injected HTTP boundary; no socket or provider call is permitted."""
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.requests = []
    def __call__(self, host, port, timeout, context):
        assert host == 'api.openai.com' and port == 443 and timeout > 0
        owner = self
        class Connection:
            sock = None
            def set_debuglevel(self, level):
                assert level == 0
            def request(self, method, path, body, headers, encode_chunked):
                assert method == 'POST' and path == '/v1/responses' and not encode_chunked
                owner.requests.append(body)
            def getresponse(self):
                assert owner.bodies, 'Unplanned provider request after terminal action'
                return Response(owner.bodies.pop(0))
            def close(self):
                pass
        return Connection()


def provider(action):
    return encode({'object': 'response', 'status': 'completed', 'error': None, 'incomplete_details': None,
                   'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False, 'store': False,
                   'truncation': 'disabled', 'previous_response_id': None, 'conversation': None,
                   'model': 'generated-model', 'max_output_tokens': 100, 'id': 'resp_generated_one',
                   'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                               'content': [{'type': 'output_text', 'text': action.decode()}]}],
                   'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}})


class ByteMap:
    """Explicit retained-capture supplier, preserving exact pin/cap checks.

    Small synthetic frames and per-case audit records stand in for a live retained
    capture tree. This is not a claim that6400 real renders or children existed.
    """
    def __init__(self):
        self.bodies = {}
        self.directories = {}
        self.reads = []
    def add(self, path, value):
        body = value if isinstance(value, bytes) else encode(value)
        self.bodies[Path(path)] = body
        return pin(body)
    def read(self, path, cap=1048576, expected=None, *, budget=None):
        global SUPPLIED
        path = Path(path)
        body = self.bodies[path]
        if not 0 < len(body) <= cap:
            raise ValueError('Generated retained-capture size cap mismatch')
        if budget is not None:
            budget.input(len(body) + 1)
        SUPPLIED += len(body) + 1
        if SUPPLIED > READ_CAP:
            raise AssertionError('Generated retained-capture supplied bytes exceed selected cap')
        self.reads.append((str(path), len(body)))
        if expected is not None and pin(body) != expected:
            raise ValueError('Generated retained-capture pin mismatch')
        return body
    def iterdir(self, path):
        return iter(Path(path) / name for name in self.directories[Path(path)])

