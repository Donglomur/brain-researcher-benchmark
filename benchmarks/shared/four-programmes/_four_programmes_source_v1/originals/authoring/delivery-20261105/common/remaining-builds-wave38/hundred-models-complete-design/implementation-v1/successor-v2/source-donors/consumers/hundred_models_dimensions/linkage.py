"""Derive compact consumer links from complete, nonexecuting operation contracts.

The operator separately admits the referenced records and future numerical
artifacts. A dataclass or SHA256 alone cannot authenticate execution/provenance.
Child operation JSON has no newline; frozen catalog JSON has one. Each digest
uses its explicitly corresponding serialization, never a renamed digest.
"""
from hashlib import sha256

from . import operations as ops
from . import _catalog_gate as gate
from ._scope import METHOD_FOLDERS, ROIS, SUBJECTS


def _operation_pin(contract,budget):
    raw=ops.canonical_bytes(contract,budget)
    return {'bytes':len(raw),'sha256':sha256(raw).hexdigest()}


def model_condition_link(contract,folder,evaluation_layers,split_emission_receipt,score_provenance_receipt,*,budget):
    gate.need(type(contract) is ops.ModelContract,'complete model-operation contract')
    gate.need(contract.source_pins==ops.SOURCE_PINS and not contract.native_executed
              and not contract.historical_runtime_equivalence and not contract.scientific_qualified
              and not contract.metadata_authenticity_verified,
              'unqualified exact held-source operation contract')
    gate.need(type(evaluation_layers) is tuple and evaluation_layers
              and all(type(name) is str and name for name in evaluation_layers)
              and len(set(evaluation_layers))==len(evaluation_layers)
              and set(evaluation_layers)<=set(gate.normalize(contract.source_axis_layer_order)),
              'evaluation layers are explicit subset of full emitted producer axis')
    gate.need(type(folder) is str and 0<len(folder)<=256,'declared source folder')
    spec=contract.run_spec
    if contract.split==ops.TEST_SPLIT:
        gate.need(folder in dict(METHOD_FOLDERS) and dict(METHOD_FOLDERS)[folder]==spec.method,
                  'test dimension folder matches declared method')
    else:
        gate.need(contract.split==ops.TRAIN_SPLIT and spec.method=='pca','image-train source PCA branch')
    if spec.method=='pca':
        gate.need((spec.n_samples_estim,spec.n_components,spec.max_dim_allowed)==(102,100,None),
                  'literal held PCA arguments, no silent train fit-size change')
        profile='literal_held_script_pca100_fit102'
    else:
        gate.need(spec.branch=='explicit_run_spec' and type(contract.run_admission) is ops.RunAdmission,
                  'historical alternative settings require explicit admitted run metadata')
        profile='explicit_admitted_srp_run_metadata' if spec.method=='srp' else 'explicit_admitted_no_reduction_run_metadata'
    for descriptor in (split_emission_receipt,score_provenance_receipt):gate.descriptor(descriptor)
    return {'model':contract.model_id,'folder':folder,
        'stimulus_order':gate.pin(gate.encoded(contract.stimulus_order)),
        'layer_order':gate.pin(gate.encoded(evaluation_layers)),
        'producer_layer_order':gate.pin(gate.encoded(contract.source_axis_layer_order)),
        'n_stimuli':contract.split.stimuli,'split_emission_receipt':dict(split_emission_receipt),
        'operation_contract':_operation_pin(contract,budget),'score_provenance_receipt':dict(score_provenance_receipt),
        'operation_profile':profile,'reduction':{'method':spec.method,'n_samples_estim':spec.n_samples_estim,
            'n_components':spec.n_components,'max_dim_allowed':spec.max_dim_allowed,
            'standardize_on_dim':None,'distance':'pearson',
            'sklearn_kwargs_policy':'constructor-only-n_components;other-keywords-omitted'}}


def brain_support_link(contract,shape_manifest,noise_ceiling_receipt,*,budget):
    gate.need(type(contract) is ops.BrainContract and contract.source_pins==ops.SOURCE_PINS
              and contract.subject_order==SUBJECTS and contract.roi_order==ROIS
              and contract.split in (ops.TEST_SPLIT,ops.TRAIN_SPLIT),
              'complete source brain-operation contract')
    gate.need(not contract.native_executed and not contract.historical_runtime_equivalence
              and not contract.scientific_qualified and not contract.metadata_authenticity_verified,
              'unqualified source operations only')
    for descriptor in (shape_manifest,noise_ceiling_receipt):gate.descriptor(descriptor)
    gate.need(shape_manifest['sha256']==contract.input_metadata_sha256,
              'separately admitted metadata body must match compiled brain support')
    return {'subjects':list(SUBJECTS),'rois':list(ROIS),'n_stimuli':contract.split.stimuli,
        'repetitions':contract.split.repetitions,'average_external':False,
        'operation_contract':_operation_pin(contract,budget),'shape_manifest':dict(shape_manifest),
        'noise_ceiling_receipt':dict(noise_ceiling_receipt)}
