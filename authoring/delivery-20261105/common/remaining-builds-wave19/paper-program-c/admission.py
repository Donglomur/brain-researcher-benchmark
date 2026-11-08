"""Pinned semantic output admission before any private assessment observations."""
import re
from core import HMM, TASK, identity, need
from safe_io import capture, child, strict
from likelihood import validate_hmm


def output_pins(outputs):
    need(type(outputs) is dict and outputs, 'Nonempty complete external output inventory')
    for name, pin in outputs.items():
        need(type(name) is str and re.fullmatch(r'[a-zA-Z0-9_.-]+', name), 'Flat output path')
        need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
             type(pin['bytes']) is int and pin['bytes'] >= 0 and
             type(pin['sha256']) is str and re.fullmatch('[a-f0-9]{64}', pin['sha256']),
             'Actual independently observed complete output bytes/SHA')
    return sum(v['bytes'] for v in outputs.values())


def held(root, disposition, representation_id, max_bytes):
    job = disposition['job']
    need(disposition['status'] == 'completed' and job['phase'] == 'held_hmm', 'Closed successful held attempt')
    outputs = disposition['outputs']
    need(output_pins(outputs) <= max_bytes and set(outputs) == {'MODEL.json'},
         'One complete primitive parameter artifact, no submitted scorer/code')
    raw = capture(child(root, 'MODEL.json'), max_bytes, outputs['MODEL.json'])
    model = strict(raw)
    need(set(model) == {'schema', 'task_id', 'job_id', 'representation_id', 'parameters'}
         and model['schema'] == 'osl_held_model_v1' and model['task_id'] == TASK
         and model['job_id'] == job['id'] and model['representation_id'] == representation_id,
         'Complete exact job/input coordinate identity')
    d, k, _ = HMM[job['branch']]
    validate_hmm(model['parameters'], d, k)
    return {'kind': 'held_model', 'job_id': job['id'], 'role': job['role'],
            'parameters': model['parameters'], 'representation_id': representation_id,
            'external_closure_pin': disposition['capture_pin'], 'artifact': outputs['MODEL.json']}


def native(root, disposition, context, max_bytes):
    from native.assemble import assemble, primitive_npy
    need(disposition['status'] == 'completed' and disposition['job']['phase'] == 'native',
         'Closed successful native attempt')
    job = disposition['job']
    need(context['attempt_id'] == job['id'] and context['role'] == job['role']
         and context['branch'] == job['branch'], 'Operator-authenticated actual attempt context')
    outputs = disposition['outputs']
    need(output_pins(outputs) <= max_bytes and 'CAPTURE.json' in outputs, 'Complete bounded native capture inventory')
    accessed = set()
    def reader(name, remaining):
        need(name in outputs, 'No capture file outside external output commitment')
        accessed.add(name)
        return capture(child(root, name), min(max_bytes, remaining), outputs[name])
    assembled = assemble(root, job['branch'], context, max_total_bytes=max_bytes, read_bytes=reader)
    need(accessed == set(outputs), 'No omitted or unadmitted capture files')
    def load(spec):
        name = spec['artifact']['file']
        raw = capture(child(root, name), max_bytes, outputs[name])
        return primitive_npy(raw)
    return {'kind': 'native_output', 'job_id': job['id'], 'role': job['role'],
            'assembled': assembled, 'load': load, 'read_bytes': reader,
            'external_closure_pin': disposition['capture_pin']}
