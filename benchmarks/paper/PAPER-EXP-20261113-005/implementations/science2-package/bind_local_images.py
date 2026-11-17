"""Pure, exact PFC task.toml overlay for separately admitted complete images.

No file writes or Docker operations. These IDs must identify the COMPLETE agent
and verifier task images, never the shared numerical bases. The operation owner
must authenticate build receipts/content and perform the guarded owned write.
"""
import hashlib
import re
import tomllib

TASK_BYTES = 1218
TASK_SHA256 = '76ded1e377885c474118c9235cbaa01712ce5c3a6a8c49475ce91ebe51271d2f'
CONFIG_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')


def overlay_complete_images(body, agent_image_id, verifier_image_id):
    if type(body) is not bytes or (len(body), hashlib.sha256(body).hexdigest()) != (TASK_BYTES, TASK_SHA256):
        raise ValueError('unchanged exact task.toml required')
    for image in (agent_image_id, verifier_image_id):
        if type(image) is not str or CONFIG_ID.fullmatch(image) is None:
            raise ValueError('complete local config ID required')
    # Contexts differ and carry different evaluator/participant assets.
    if agent_image_id == verifier_image_id:
        raise ValueError('distinct complete agent and verifier images required')
    text = body.decode('utf8')
    before = tomllib.loads(text)
    if any('docker_image' in table for table in (before['environment'], before['verifier']['environment'])):
        raise ValueError('preexisting image override')
    for heading, image in (('[environment]\n', agent_image_id),
                           ('[verifier.environment]\n', verifier_image_id)):
        if text.count(heading) != 1:
            raise ValueError('exact section boundary')
        text = text.replace(heading, heading + 'docker_image = "' + image + '"\n', 1)
    after = tomllib.loads(text)
    if after['environment'].pop('docker_image') != agent_image_id:
        raise ValueError('agent binding')
    if after['verifier']['environment'].pop('docker_image') != verifier_image_id or after != before:
        raise ValueError('unrelated task semantics changed')
    return text.encode('utf8')
