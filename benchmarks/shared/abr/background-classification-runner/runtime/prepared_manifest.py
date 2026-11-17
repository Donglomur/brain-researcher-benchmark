"""Root-pinned private preparation boundary, never candidate-provided authority.

Receipts are maintainer assertions supported by private deterministic-validation
evidence. Pins/structure alone do not prove labels or biological provenance.
"""
from pathlib import Path
import common as c

SCHEMA = 'abr-opaque-private-preparation-receipt/v1'
PROJECTION = 'abr-validated-private-to-opaque/v1'
COMPLETION_SCHEMA = 'abr-background-opaque-packet-completion/v1'
COUNTS = {'animals':104, 'labels':104, 'outer_partitions':5,
          'inner_partitions':20, 'animal_files':104}
FLAGS = ('full_private_validation', 'canonical_animal_order_preserved',
         'labels_preserved', 'outer_partitions_preserved',
         'inner_partitions_preserved', 'state_policy_preserved', 'animal_files_unchanged')
PINS = ('original_manifest', 'original_completion', 'private_validator',
        'opaque_manifest', 'opaque_completion')

def validate_receipt(receipt, manifest_pin, completion_pin):
    keys = {'schema', 'projection', 'counts', *FLAGS, *PINS}
    c.need(type(receipt) is dict and set(receipt) == keys and receipt['schema'] == SCHEMA and
           receipt['projection'] == PROJECTION and receipt['counts'] == COUNTS,
           'complete private preparation contract')
    counts = receipt['counts']
    c.need(type(counts) is dict and set(counts) == set(COUNTS) and
           all(type(value) is int for value in counts.values()), 'literal preparation-count integers')
    for field in FLAGS:
        c.need(receipt[field] is True, 'proved preparation correspondence: ' + field)
    for field in PINS:
        c.admit_pin(receipt[field], 1048576)
        c.need(receipt[field]['bytes'] > 0, 'nonempty preparation operand')
    c.need(receipt['opaque_manifest'] == manifest_pin and
           receipt['opaque_completion'] == completion_pin, 'preparation exact opaque operands')
    return receipt

def admit(selection, manifest_raw, completion_raw, budget):
    """Authenticate selected bytes before trusting any canonical assignment."""
    c.need(selection['root_execution_selected'] is True, 'root-selected prepared operands')
    item = selection['preparation']
    c.need(type(item) is dict and set(item) == {'path', 'bytes', 'sha256'} and
           item['path'] == str(Path(selection['packet_root'])/'evaluator/PREPARATION_RECEIPT.json'),
           'fixed operator-private preparation location')
    expected = {k:item[k] for k in ('bytes', 'sha256')}
    raw = c.read(item['path'], expected, budget, cap=1048576)
    manifest_pin = c.pin(manifest_raw); completion_pin = c.pin(completion_raw)
    c.need(manifest_pin == {k:selection['manifest'][k] for k in ('bytes', 'sha256')} and
           completion_pin == {k:selection['completion'][k] for k in ('bytes', 'sha256')},
           'root-pinned manifest and completion bodies')
    return validate_receipt(c.decode(raw), manifest_pin, completion_pin)
