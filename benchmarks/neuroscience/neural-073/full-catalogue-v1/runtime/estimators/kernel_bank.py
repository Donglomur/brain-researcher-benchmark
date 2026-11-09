"""Concrete immutable training-kernel banks, issued inside a trusted worker.

The weak issuance ledger stores only seals and does not retain matrix bodies.
A caller cannot qualify bare deserialized precomputed K by declaring metadata.
This is a trusted-process mechanism, not a sandbox against arbitrary Python in
that process. Parent worker/source/role isolation remains mandatory.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import sys
import weakref
from ._common import (EstimatorError, FrozenArray, numpy, matrix, context,
                      finite_number, strict_keys)

_ISSUED = weakref.WeakKeyDictionary()
_FIELDS = ('schema','outer_context_token','condition','view','training_subset_token',
           'representation','pca_rank','data_generation_sha256','transform_source_sha256')


def component_key(value, family):
    strict_keys(value,_FIELDS,'kernel_component_key')
    if value['schema']!='n073_kernel_component_key_v1':
        raise EstimatorError('unknown_kernel_key_schema')
    for name in ('outer_context_token','training_subset_token'):
        if type(value[name]) is not str or re.fullmatch('[0-9a-f]{32,64}',value[name]) is None:
            raise EstimatorError('invalid_kernel_key_token')
    for name in ('data_generation_sha256','transform_source_sha256'):
        if type(value[name]) is not str or re.fullmatch('[0-9a-f]{64}',value[name]) is None:
            raise EstimatorError('invalid_kernel_key_source_pin')
    if value['condition'] not in ('original','spatial_scrambled','C_only') or value['view'] not in ('N','C','NC'):
        raise EstimatorError('invalid_kernel_key_scope')
    if value['condition']=='C_only' and value['view']!='C':
        raise EstimatorError('kernel_key_control_violation')
    if value['view']=='C':
        if value['representation'] is not None or value['pca_rank'] is not None:
            raise EstimatorError('kernel_C_has_neural_transform')
    else:
        if value['representation'] not in ('raw','rms'):
            raise EstimatorError('invalid_kernel_representation')
        if family=='linear_ovr_svm' and value['pca_rank'] is not None:
            raise EstimatorError('linear_kernel_rank_not_applicable')
        if family=='rbf_ovr_svm' and (type(value['pca_rank']) is not int or value['pca_rank'] not in (64,256)):
            raise EstimatorError('invalid_kernel_PCA_rank')
    return tuple(value[name] for name in _FIELDS)


def _key_width(X,key,family):
    values=dict(zip(_FIELDS,key));d=X.shape[1];view=values['view']
    if view=='C' and d!=105:
        raise EstimatorError('kernel_C_width_mismatch')
    if view!='C' and family=='rbf_ovr_svm':
        if d!=values['pca_rank']+(105 if view=='NC' else 0):
            raise EstimatorError('kernel_rank_width_mismatch')
    if view!='C' and family=='linear_ovr_svm' and d<256+(105 if view=='NC' else 0):
        raise EstimatorError('kernel_linear_grid_width_too_small')


def _key_dict(key):
    return dict(zip(_FIELDS,key))


def _digest_array(value,budget,role):
    if sys.byteorder!='little':
        raise EstimatorError('unbound_numeric_byte_order')
    header=json.dumps({'dtype':'<f8','shape':list(value.shape)},sort_keys=True,separators=(',',':')).encode('ascii')
    budget.tick('hashed_'+role+'_bytes',value.nbytes)
    digest=hashlib.sha256(header+b'\0')
    digest.update(memoryview(value).cast('B'))
    return digest.hexdigest()


def _row_digest(rows,n,budget):
    if (type(rows) not in (list,tuple) or len(rows)!=n or
            any(type(x) is not str or re.fullmatch('[A-Za-z0-9_-]{16,128}',x) is None for x in rows) or
            len(set(rows))!=n):
        raise EstimatorError('invalid_kernel_opaque_row_ids')
    size=sum(len(x) for x in rows)+3*n+2
    budget.charge(size,'kernel_row_identity_encoding_bound')
    encoded=json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def _weights(weights,n,budget):
    np=numpy()
    if (type(weights) is not np.ndarray or weights.dtype!=np.dtype('float64') or
            weights.shape!=(n,) or not weights.flags.c_contiguous or
            any(not math.isfinite(float(x)) or x<=0 for x in weights)):
        raise EstimatorError('invalid_kernel_weights')
    if abs(math.fsum(float(x) for x in weights)-1.0)>1e-12:
        raise EstimatorError('kernel_weights_not_normalized')
    return _digest_array(weights,budget,'kernel_weights')


@dataclass(frozen=True,eq=False)
class KernelBank:
    family: str
    gamma_factor: float | None
    gamma: float | None
    key: tuple
    X_sha256: str
    weights_sha256: str
    rows_sha256: str
    rows: int
    features: int
    gram: FrozenArray

    def summary(self):
        return {'schema':'n073_inprocess_kernel_bank_v1','family':self.family,
                'gamma_factor':self.gamma_factor,'gamma':self.gamma,
                'component_key':_key_dict(self.key),'X_sha256':self.X_sha256,
                'weights_sha256':self.weights_sha256,'rows_sha256':self.rows_sha256,
                'rows':self.rows,'features':self.features,
                'gram_sha256':hashlib.sha256(self.gram.body).hexdigest(),
                'gram_bytes':len(self.gram.body),'restore_policy':'No bare deserialize; rebuild in trusted worker.'}


def _seal(bank):
    return hashlib.sha256(json.dumps(bank.summary(),sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')).hexdigest()


def build_kernel_bank(X,weights,row_ids,family,gamma_factor,dependency_key,budget):
    """Build the actual complete training Gram, then issue its immutable bank."""
    from .svm import training_gamma,kernel_matrix
    matrix(X,budget)
    if family not in ('linear_ovr_svm','rbf_ovr_svm'):
        raise EstimatorError('unknown_kernel_bank_family')
    key=component_key(dependency_key,family)
    _key_width(X,key,family)
    wd=_weights(weights,X.shape[0],budget)
    xd=_digest_array(X,budget,'kernel_X')
    rd=_row_digest(row_ids,X.shape[0],budget)
    if family=='linear_ovr_svm':
        if gamma_factor is not None:
            raise EstimatorError('linear_gamma_not_applicable')
        gamma=None;kernel='linear'
    else:
        gamma_factor=finite_number(gamma_factor,'gamma_factor',True)
        if gamma_factor not in (.1,1.,10.):
            raise EstimatorError('gamma_factor_outside_frozen_grid')
        gamma=training_gamma(X,weights,gamma_factor,budget);kernel='rbf'
    K=kernel_matrix(X,X,kernel,gamma,budget)
    frozen=FrozenArray.freeze(K,budget,'training_kernel_bank')
    bank=KernelBank(family,gamma_factor,gamma,key,xd,wd,rd,X.shape[0],X.shape[1],frozen)
    budget.tick('kernel_bank_seal_bytes',len(frozen.body))
    _ISSUED[bank]=_seal(bank)
    budget.tick(kernel+'_training_gram_banks_built')
    budget.tick('kernel_bank_numeric_bytes_retained',len(frozen.body))
    return bank


def validate_kernel_bank(bank,X,weights,row_ids,family,gamma_factor,dependency_key,fit_context,budget):
    """Verify issuer, exact data/row/key identity and gamma before borrowing K."""
    if type(bank) is not KernelBank or _ISSUED.get(bank) is None:
        raise EstimatorError('kernel_bank_not_issued_by_worker')
    budget.tick('kernel_bank_digest_bytes_checked',len(bank.gram.body))
    if _ISSUED[bank]!=_seal(bank):
        raise EstimatorError('kernel_bank_not_issued_by_worker')
    if family=='rbf_ovr_svm':
        gamma_factor=finite_number(gamma_factor,'gamma_factor',True)
    elif family=='linear_ovr_svm' and gamma_factor is not None:
        raise EstimatorError('linear_gamma_not_applicable')
    key=component_key(dependency_key,family)
    _key_width(X,key,family)
    ctx=context(fit_context)
    expected=_key_dict(key)
    if (expected['outer_context_token']!=ctx[0] or expected['condition']!=ctx[1] or expected['view']!=ctx[2]):
        raise EstimatorError('kernel_bank_fit_scope_mismatch')
    if bank.family!=family or bank.gamma_factor!=gamma_factor or bank.key!=key:
        raise EstimatorError('kernel_bank_parameter_or_key_mismatch')
    if bank.rows!=X.shape[0] or bank.features!=X.shape[1] or bank.gram.shape!=(bank.rows,bank.rows):
        raise EstimatorError('kernel_bank_shape_mismatch')
    if _digest_array(X,budget,'kernel_X')!=bank.X_sha256:
        raise EstimatorError('kernel_bank_X_identity_mismatch')
    if _weights(weights,X.shape[0],budget)!=bank.weights_sha256:
        raise EstimatorError('kernel_bank_weight_identity_mismatch')
    if _row_digest(row_ids,X.shape[0],budget)!=bank.rows_sha256:
        raise EstimatorError('kernel_bank_row_identity_mismatch')
    budget.tick('kernel_bank_reuses')
    return bank.gram.array(),bank.gamma
