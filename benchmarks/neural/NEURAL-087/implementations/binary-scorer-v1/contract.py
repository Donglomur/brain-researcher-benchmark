"""NEURAL-087 source contract. No I/O, array loading or fitting on import."""
import hashlib

TASK = 'NEURAL-087'
VIEWS = ('anatomy', 'anatomy_plus_in_vivo')
PROJECTIONS = ('V1->V1', 'HVA->HVA', 'V1->HVA', 'HVA->V1')
# Deliberately preserve the existing 088 split/exposure group, not a new seed.
NODE_DOMAIN = b'NEURAL-088/node-partition-v1\n'
COUNTS = {'train': 105146, 'fit': 97717, 'validation': 7429, 'query': 6691}
COMMON_FIELDS = ('edge_position', 'pre_id', 'post_id', 'projection', 'exposure_mm', 'x')
TRAIN_FIELDS = (*COMMON_FIELDS, 'role', 'connected')
NEURAL_FIELDS = ('train_edge_position', 'query_edge_position', 'train_correlation', 'query_correlation')
COLUMNS = ('log_dend_len', 'delta_x_um', 'delta_y_um', 'delta_z_um', 'soma_distance_um',
           'pre_cc_max_cvt', 'post_cc_max_cvt', 'pre_cc_abs_cvt', 'post_cc_abs_cvt',
           'pre_brain_area', 'post_brain_area', 'pre_layer', 'post_layer',
           'pre_proofread_status', 'post_proofread_status', 'proj_hva')
CATEGORY_SIZES = (4, 4, 4, 4, 2, 3, 4)
MAX_QUERY = 6691


def need(ok, message):
    if not ok:
        raise ValueError(message)


def int64(v):
    return type(v) is int and -(2**63) <= v < 2**63


def node_role(node):
    need(int64(node), 'Canonical signed-int64 neuron identity')
    bucket = int.from_bytes(hashlib.sha256(NODE_DOMAIN + str(node).encode('ascii') + b'\n').digest(), 'big') % 10000
    return 0 if bucket < 6000 else 1 if bucket < 8000 else 2


def binary_count(count):
    need(type(count) is int and 0 <= count <= 2**53, 'Nonboolean nonnegative integer released count')
    return int(count > 0)
