"""One closed mapping to26 operative typed and6 trusted parent constructors.

This module neither deserializes runtime-issued capabilities nor activates a
runtime. IDs are fixed internal call-site selectors, absent from policy JSON.
No history source, configurable import path, backend or callback is accepted.
"""
import hashlib
import json
import math
from .declaration import DeclarationError, _need, _sha, _absolute, CANDIDATE_CAPS, ACCEPTED_PARENT

_MANIFEST = {'trusted': [{'constructor_id': 'AuthorityVerifier',
              'module_relative': 'runtime.core.custody',
              'qualname': 'AuthorityVerifier',
              'signature': 'self, *, issuer_id: str, issuer_key: bytes, root_id: str, root_key: bytes, '
                           'expected_design: str, root_selection: bytes | None=None',
              'source': 'core/custody.py'},
             {'constructor_id': 'RoleIssuer',
              'module_relative': 'runtime.runner.authority',
              'qualname': 'RoleIssuer',
              'signature': 'self, verifier, *, global_bindings, domain',
              'source': 'runner/authority.py'},
             {'constructor_id': 'ReferenceData',
              'module_relative': 'runtime.runner.reference',
              'qualname': 'ReferenceData',
              'signature': 'self, *, catalogue, assessment, observations, values_by_id, original_descriptors, '
                           'context_key, permutation_key, source_contract_digest',
              'source': 'runner/reference.py'},
             {'constructor_id': 'PrivateRunStore',
              'module_relative': 'runtime.private_store.store',
              'qualname': 'PrivateRunStore',
              'signature': "self, admission, *, authority, role='reference_fit', domain='authentic'",
              'source': 'private_store/store.py'},
             {'constructor_id': 'ReferenceEngine',
              'module_relative': 'runtime.runner.reference',
              'qualname': 'ReferenceEngine',
              'signature': 'self, *, data: ReferenceData, capacity: ReferenceCapacity, authority: '
                           'VerifiedAuthority, source_digest: str, transform_source_digest: str, '
                           'numerical_contract_digest: str, store: PrivateRunStore',
              'source': 'runner/reference.py'},
             {'constructor_id': 'IntegratedFullStudy',
              'module_relative': 'integrated_study',
              'qualname': 'IntegratedFullStudy',
              'signature': 'self, *, reference_engine, issuer, policy, host_specs, tool_specs, export_key',
              'source': 'integrated_study.py'}],
 'typed': [{'constructor_id': 'Geometry',
            'fields': ['shape: tuple[int, int, int]',
                       'affine: tuple[float, ...]',
                       'orientation: tuple[str, str, str]'],
            'module_relative': 'runtime.admission.arrays',
            'qualname': 'Geometry',
            'source': 'admission/arrays.py'},
           {'constructor_id': 'OriginalReceipt',
            'fields': ['record_id: str',
                       'domain: str',
                       'original_sha256: str',
                       'original_bytes: int',
                       'source_version: str',
                       'source_locator_digest: str',
                       'rights_evidence_digest: str',
                       'decoder_contract_digest: str',
                       'conversion_evidence_digest: str'],
            'module_relative': 'runtime.admission.arrays',
            'qualname': 'OriginalReceipt',
            'source': 'admission/arrays.py'},
           {'constructor_id': 'IdentityConflict',
            'fields': ['record_ids: tuple[str, ...]', 'source_evidence_digest: str'],
            'module_relative': 'runtime.admission.arrays',
            'qualname': 'IdentityConflict',
            'source': 'admission/arrays.py'},
           {'constructor_id': 'Adjudication',
            'fields': ['flag_id: str', 'disposition: str', 'evidence_digest: str', 'decision_receipt_digest: str'],
            'module_relative': 'runtime.admission.arrays',
            'qualname': 'Adjudication',
            'source': 'admission/arrays.py'},
           {'constructor_id': 'OriginalDescriptor',
            'fields': ['record_id: str',
                       'original_decoded_sha256: str',
                       'producer_contract_digest: str',
                       'values: tuple[float, ...]'],
            'module_relative': 'runtime.admission.export',
            'qualname': 'OriginalDescriptor',
            'source': 'admission/export.py'},
           {'constructor_id': 'IOLimits',
            'fields': ['max_files: int',
                       'max_directories: int',
                       'max_depth: int',
                       'max_file_bytes: int',
                       'max_total_bytes: int',
                       'block_bytes: int = 65536'],
            'module_relative': 'runtime.context_io.filesystem',
            'qualname': 'IOLimits',
            'source': 'context_io/filesystem.py'},
           {'constructor_id': 'MountAPIContract',
            'fields': ['executable: str',
                       'executable_bytes: int',
                       'executable_sha256: str',
                       'implementation_version: str',
                       'source_api_closure: EvidencePin',
                       'native_command_controls: EvidencePin'],
            'module_relative': 'runtime.context_io.native_seal_v1.contracts',
            'qualname': 'MountAPIContract',
            'source': 'context_io/native_seal_v1/contracts.py'},
           {'constructor_id': 'SealAdmission',
            'fields': ['namespace_device: int',
                       'namespace_inode: int',
                       'host_reference_pid: int',
                       'host_namespace_device: int',
                       'host_namespace_inode: int',
                       'namespace_qualification: EvidencePin',
                       'expected_euid: int',
                       'target_parent: str',
                       'target_parent_device: int',
                       'target_parent_inode: int',
                       'target_parent_mount_id: int',
                       'target_name: str',
                       'mount_api: MountAPIContract',
                       'limits: IOLimits',
                       'source_closure_digest: str',
                       'timeout_seconds: int = 20',
                       'output_bytes_per_stream: int = 8192',
                       'mountinfo_byte_cap: int = 4194304'],
            'module_relative': 'runtime.context_io.native_seal_v1.contracts',
            'qualname': 'SealAdmission',
            'source': 'context_io/native_seal_v1/contracts.py'},
           {'constructor_id': 'EvidencePin',
            'fields': ['kind: str', 'sha256: str', 'bytes: int'],
            'module_relative': 'runtime.core.custody',
            'qualname': 'EvidencePin',
            'source': 'core/custody.py'},
           {'constructor_id': 'InferenceParameter',
            'fields': ['name: str', 'kind: str', 'value: object'],
            'module_relative': 'runtime.core.inference',
            'qualname': 'InferenceParameter',
            'source': 'core/inference.py'},
           {'constructor_id': 'InferenceSettings',
            'fields': ['parameters: tuple', 'completeness_evidence_digest: str'],
            'module_relative': 'runtime.core.inference',
            'qualname': 'InferenceSettings',
            'source': 'core/inference.py'},
           {'constructor_id': 'RepetitionSchedule',
            'fields': ['mode: str', 'seeds: tuple', 'randomness_evidence_digest: str'],
            'module_relative': 'runtime.core.inference',
            'qualname': 'RepetitionSchedule',
            'source': 'core/inference.py'},
           {'constructor_id': 'InferencePolicy',
            'fields': ['settings: InferenceSettings', 'schedule: RepetitionSchedule'],
            'module_relative': 'runtime.core.inference',
            'qualname': 'InferencePolicy',
            'source': 'core/inference.py'},
           {'constructor_id': 'StoreAdmission',
            'fields': ['root: str',
                       'run_id: str',
                       'single_artifact_bytes: int',
                       'total_write_bytes: int',
                       'journal_record_bytes: int',
                       'store_contract_digest: str',
                       'public_mount_roots: tuple'],
            'module_relative': 'runtime.private_store.store',
            'qualname': 'StoreAdmission',
            'source': 'private_store/store.py'},
           {'constructor_id': 'MonitorRuntime',
            'fields': ['python_path: str',
                       'python_bytes: int',
                       'python_sha256: str',
                       'source_path: str',
                       'source_bytes: int',
                       'source_sha256: str',
                       'native_contract_digest: str',
                       'oom_witness_evidence_digest: str'],
            'module_relative': 'runtime.process_guard.aggregate_v3',
            'qualname': 'MonitorRuntime',
            'source': 'process_guard/aggregate_v3.py'},
           {'constructor_id': 'MemberPin',
            'fields': ['path: str', 'bytes: int', 'sha256: str', 'mode: int'],
            'module_relative': 'runtime.process_guard.contracts',
            'qualname': 'MemberPin',
            'source': 'process_guard/contracts.py'},
           {'constructor_id': 'GuardAdmission',
            'fields': ['context_id: str',
                       'arm: str',
                       'bwrap_path: str',
                       'bwrap_bytes: int',
                       'bwrap_sha256: str',
                       'runtime_root: str',
                       'runtime_members: tuple',
                       'runtime_manifest_digest: str',
                       'environment_evidence_digest: str',
                       'control_source_digest: str',
                       'export_allowlist_digest: str',
                       'cgroup_parent: str',
                       'cgroup_parent_mount_id: int',
                       'scratch_mount: str',
                       'scratch_mount_id: int',
                       'scratch_device: str',
                       'scratch_capacity_bytes: int',
                       'scratch_exclusivity_evidence_digest: str',
                       'cpus: tuple',
                       'memory_nodes: tuple',
                       'initial_phase_mounts: tuple'],
            'module_relative': 'runtime.process_guard.contracts',
            'qualname': 'GuardAdmission',
            'source': 'process_guard/contracts.py'},
           {'constructor_id': 'SourcePin',
            'fields': ['path: str', 'bytes: int', 'sha256: str'],
            'module_relative': 'runtime.provider_transport.protocol',
            'qualname': 'SourcePin',
            'source': 'provider_transport/protocol.py'},
           {'constructor_id': 'AdapterAdmission',
            'fields': ['context_id: str',
                       'inference_policy: InferencePolicy',
                       'repetition: int',
                       'argv: tuple',
                       'source_closure: tuple',
                       'source_closure_digest: str',
                       'model_revision: str',
                       'fixed_model_evidence_digest: str',
                       'stateless_evidence_digest: str',
                       'tokenizer_evidence_digest: str',
                       'usage_evidence_digest: str',
                       'environment_evidence_digest: str',
                       'protocol_evidence_digest: str',
                       'capacity_evidence_digest: str',
                       'capacity_basis: str',
                       'max_frame_bytes: int',
                       'max_capture_bytes: int',
                       'capture_directory: str'],
            'module_relative': 'runtime.provider_transport.protocol',
            'qualname': 'AdapterAdmission',
            'source': 'provider_transport/protocol.py'},
           {'constructor_id': 'PublicModelLimits',
            'fields': ['max_elements: int', 'max_workspace_bytes: int', 'max_nodes: int', 'max_json_bytes: int'],
            'module_relative': 'runtime.public_models.model',
            'qualname': 'PublicModelLimits',
            'source': 'public_models/model.py'},
           {'constructor_id': 'Policy',
            'fields': ['policy_id: str',
                       'max_response_tokens: int',
                       'source_digest: str',
                       'inference_policy: InferencePolicy'],
            'module_relative': 'runtime.runner.policy',
            'qualname': 'Policy',
            'source': 'runner/policy.py'},
           {'constructor_id': 'HostPreparation',
            'fields': ['context_id: str',
                       'capsule_parent: str',
                       'capsule_name: str',
                       'capsule_limits: object',
                       'capsule_seal_admission: object',
                       'guard_admission: object',
                       'monitor_runtime: object',
                       'provider_admission: object',
                       'snapshot_parent: str',
                       'snapshot_name: str',
                       'snapshot_limits: object',
                       'snapshot_seal_admission: object'],
            'module_relative': 'runtime.runner.preparation',
            'qualname': 'HostPreparation',
            'source': 'runner/preparation.py'},
           {'constructor_id': 'ToolPreparation',
            'fields': ['parent: str',
                       'name: str',
                       'limits: object',
                       'seal_admission: object',
                       'model_limits: object',
                       'public_sources: tuple'],
            'module_relative': 'runtime.runner.preparation',
            'qualname': 'ToolPreparation',
            'source': 'runner/preparation.py'},
           {'constructor_id': 'PublicSource',
            'fields': ['name: str', 'body: bytes', 'sha256: str', 'mode: int'],
            'module_relative': 'runtime.runner.public_tools',
            'qualname': 'PublicSource',
            'source': 'runner/public_tools.py'},
           {'constructor_id': 'ReferenceCapacity',
            'fields': ['max_array_elements: int',
                       'max_workspace_bytes: int',
                       'max_fit_allocation_bytes: int',
                       'max_fit_work_units: int',
                       'max_graph_allocation_bytes: int',
                       'wall_seconds: int',
                       'max_scramble_cache_bytes: int'],
            'module_relative': 'runtime.runner.reference',
            'qualname': 'ReferenceCapacity',
            'source': 'runner/reference.py'},
           {'constructor_id': 'NumericLimits',
            'fields': ['max_elements: int', 'max_workspace_bytes: int'],
            'module_relative': 'runtime.transforms.numeric',
            'qualname': 'NumericLimits',
            'source': 'transforms/numeric.py'}]}
_FIELDS = {'AdapterAdmission': {'argv': {'optional': False, 'type': 'tuple'},
                      'capacity_basis': {'optional': False, 'type': 'str'},
                      'capacity_evidence_digest': {'optional': False, 'type': 'str'},
                      'capture_directory': {'optional': False, 'type': 'str'},
                      'context_id': {'optional': False, 'type': 'str'},
                      'environment_evidence_digest': {'optional': False, 'type': 'str'},
                      'fixed_model_evidence_digest': {'optional': False, 'type': 'str'},
                      'inference_policy': {'optional': False, 'type': 'InferencePolicy'},
                      'max_capture_bytes': {'optional': False, 'type': 'int'},
                      'max_frame_bytes': {'optional': False, 'type': 'int'},
                      'model_revision': {'optional': False, 'type': 'str'},
                      'protocol_evidence_digest': {'optional': False, 'type': 'str'},
                      'repetition': {'optional': False, 'type': 'int'},
                      'source_closure': {'optional': False, 'type': 'tuple'},
                      'source_closure_digest': {'optional': False, 'type': 'str'},
                      'stateless_evidence_digest': {'optional': False, 'type': 'str'},
                      'tokenizer_evidence_digest': {'optional': False, 'type': 'str'},
                      'usage_evidence_digest': {'optional': False, 'type': 'str'}},
 'Adjudication': {'decision_receipt_digest': {'optional': False, 'type': 'str'},
                  'disposition': {'optional': False, 'type': 'str'},
                  'evidence_digest': {'optional': False, 'type': 'str'},
                  'flag_id': {'optional': False, 'type': 'str'}},
 'EvidencePin': {'bytes': {'optional': False, 'type': 'int'},
                 'kind': {'optional': False, 'type': 'str'},
                 'sha256': {'optional': False, 'type': 'str'}},
 'Geometry': {'affine': {'optional': False, 'type': 'tuple[float, ...]'},
              'orientation': {'optional': False, 'type': 'tuple[str, str, str]'},
              'shape': {'optional': False, 'type': 'tuple[int, int, int]'}},
 'GuardAdmission': {'arm': {'optional': False, 'type': 'str'},
                    'bwrap_bytes': {'optional': False, 'type': 'int'},
                    'bwrap_path': {'optional': False, 'type': 'str'},
                    'bwrap_sha256': {'optional': False, 'type': 'str'},
                    'cgroup_parent': {'optional': False, 'type': 'str'},
                    'cgroup_parent_mount_id': {'optional': False, 'type': 'int'},
                    'context_id': {'optional': False, 'type': 'str'},
                    'control_source_digest': {'optional': False, 'type': 'str'},
                    'cpus': {'optional': False, 'type': 'tuple'},
                    'environment_evidence_digest': {'optional': False, 'type': 'str'},
                    'export_allowlist_digest': {'optional': False, 'type': 'str'},
                    'initial_phase_mounts': {'optional': False, 'type': 'tuple'},
                    'memory_nodes': {'optional': False, 'type': 'tuple'},
                    'runtime_manifest_digest': {'optional': False, 'type': 'str'},
                    'runtime_members': {'optional': False, 'type': 'tuple'},
                    'runtime_root': {'optional': False, 'type': 'str'},
                    'scratch_capacity_bytes': {'optional': False, 'type': 'int'},
                    'scratch_device': {'optional': False, 'type': 'str'},
                    'scratch_exclusivity_evidence_digest': {'optional': False, 'type': 'str'},
                    'scratch_mount': {'optional': False, 'type': 'str'},
                    'scratch_mount_id': {'optional': False, 'type': 'int'}},
 'HostPreparation': {'capsule_limits': {'optional': False, 'type': 'object'},
                     'capsule_name': {'optional': False, 'type': 'str'},
                     'capsule_parent': {'optional': False, 'type': 'str'},
                     'capsule_seal_admission': {'optional': False, 'type': 'object'},
                     'context_id': {'optional': False, 'type': 'str'},
                     'guard_admission': {'optional': False, 'type': 'object'},
                     'monitor_runtime': {'optional': False, 'type': 'object'},
                     'provider_admission': {'optional': False, 'type': 'object'},
                     'snapshot_limits': {'optional': False, 'type': 'object'},
                     'snapshot_name': {'optional': False, 'type': 'str'},
                     'snapshot_parent': {'optional': False, 'type': 'str'},
                     'snapshot_seal_admission': {'optional': False, 'type': 'object'}},
 'IOLimits': {'block_bytes': {'optional': True, 'type': 'int'},
              'max_depth': {'optional': False, 'type': 'int'},
              'max_directories': {'optional': False, 'type': 'int'},
              'max_file_bytes': {'optional': False, 'type': 'int'},
              'max_files': {'optional': False, 'type': 'int'},
              'max_total_bytes': {'optional': False, 'type': 'int'}},
 'IdentityConflict': {'record_ids': {'optional': False, 'type': 'tuple[str, ...]'},
                      'source_evidence_digest': {'optional': False, 'type': 'str'}},
 'InferenceParameter': {'kind': {'optional': False, 'type': 'str'},
                        'name': {'optional': False, 'type': 'str'},
                        'value': {'optional': False, 'type': 'object'}},
 'InferencePolicy': {'schedule': {'optional': False, 'type': 'RepetitionSchedule'},
                     'settings': {'optional': False, 'type': 'InferenceSettings'}},
 'InferenceSettings': {'completeness_evidence_digest': {'optional': False, 'type': 'str'},
                       'parameters': {'optional': False, 'type': 'tuple'}},
 'MemberPin': {'bytes': {'optional': False, 'type': 'int'},
               'mode': {'optional': False, 'type': 'int'},
               'path': {'optional': False, 'type': 'str'},
               'sha256': {'optional': False, 'type': 'str'}},
 'MonitorRuntime': {'native_contract_digest': {'optional': False, 'type': 'str'},
                    'oom_witness_evidence_digest': {'optional': False, 'type': 'str'},
                    'python_bytes': {'optional': False, 'type': 'int'},
                    'python_path': {'optional': False, 'type': 'str'},
                    'python_sha256': {'optional': False, 'type': 'str'},
                    'source_bytes': {'optional': False, 'type': 'int'},
                    'source_path': {'optional': False, 'type': 'str'},
                    'source_sha256': {'optional': False, 'type': 'str'}},
 'MountAPIContract': {'executable': {'optional': False, 'type': 'str'},
                      'executable_bytes': {'optional': False, 'type': 'int'},
                      'executable_sha256': {'optional': False, 'type': 'str'},
                      'implementation_version': {'optional': False, 'type': 'str'},
                      'native_command_controls': {'optional': False, 'type': 'EvidencePin'},
                      'source_api_closure': {'optional': False, 'type': 'EvidencePin'}},
 'NumericLimits': {'max_elements': {'optional': False, 'type': 'int'},
                   'max_workspace_bytes': {'optional': False, 'type': 'int'}},
 'OriginalDescriptor': {'original_decoded_sha256': {'optional': False, 'type': 'str'},
                        'producer_contract_digest': {'optional': False, 'type': 'str'},
                        'record_id': {'optional': False, 'type': 'str'},
                        'values': {'optional': False, 'type': 'tuple[float, ...]'}},
 'OriginalReceipt': {'conversion_evidence_digest': {'optional': False, 'type': 'str'},
                     'decoder_contract_digest': {'optional': False, 'type': 'str'},
                     'domain': {'optional': False, 'type': 'str'},
                     'original_bytes': {'optional': False, 'type': 'int'},
                     'original_sha256': {'optional': False, 'type': 'str'},
                     'record_id': {'optional': False, 'type': 'str'},
                     'rights_evidence_digest': {'optional': False, 'type': 'str'},
                     'source_locator_digest': {'optional': False, 'type': 'str'},
                     'source_version': {'optional': False, 'type': 'str'}},
 'Policy': {'inference_policy': {'optional': False, 'type': 'InferencePolicy'},
            'max_response_tokens': {'optional': False, 'type': 'int'},
            'policy_id': {'optional': False, 'type': 'str'},
            'source_digest': {'optional': False, 'type': 'str'}},
 'PublicModelLimits': {'max_elements': {'optional': False, 'type': 'int'},
                       'max_json_bytes': {'optional': False, 'type': 'int'},
                       'max_nodes': {'optional': False, 'type': 'int'},
                       'max_workspace_bytes': {'optional': False, 'type': 'int'}},
 'PublicSource': {'body': {'optional': False, 'type': 'bytes'},
                  'mode': {'optional': False, 'type': 'int'},
                  'name': {'optional': False, 'type': 'str'},
                  'sha256': {'optional': False, 'type': 'str'}},
 'ReferenceCapacity': {'max_array_elements': {'optional': False, 'type': 'int'},
                       'max_fit_allocation_bytes': {'optional': False, 'type': 'int'},
                       'max_fit_work_units': {'optional': False, 'type': 'int'},
                       'max_graph_allocation_bytes': {'optional': False, 'type': 'int'},
                       'max_scramble_cache_bytes': {'optional': False, 'type': 'int'},
                       'max_workspace_bytes': {'optional': False, 'type': 'int'},
                       'wall_seconds': {'optional': False, 'type': 'int'}},
 'RepetitionSchedule': {'mode': {'optional': False, 'type': 'str'},
                        'randomness_evidence_digest': {'optional': False, 'type': 'str'},
                        'seeds': {'optional': False, 'type': 'tuple'}},
 'SealAdmission': {'expected_euid': {'optional': False, 'type': 'int'},
                   'host_namespace_device': {'optional': False, 'type': 'int'},
                   'host_namespace_inode': {'optional': False, 'type': 'int'},
                   'host_reference_pid': {'optional': False, 'type': 'int'},
                   'limits': {'optional': False, 'type': 'IOLimits'},
                   'mount_api': {'optional': False, 'type': 'MountAPIContract'},
                   'mountinfo_byte_cap': {'optional': True, 'type': 'int'},
                   'namespace_device': {'optional': False, 'type': 'int'},
                   'namespace_inode': {'optional': False, 'type': 'int'},
                   'namespace_qualification': {'optional': False, 'type': 'EvidencePin'},
                   'output_bytes_per_stream': {'optional': True, 'type': 'int'},
                   'source_closure_digest': {'optional': False, 'type': 'str'},
                   'target_name': {'optional': False, 'type': 'str'},
                   'target_parent': {'optional': False, 'type': 'str'},
                   'target_parent_device': {'optional': False, 'type': 'int'},
                   'target_parent_inode': {'optional': False, 'type': 'int'},
                   'target_parent_mount_id': {'optional': False, 'type': 'int'},
                   'timeout_seconds': {'optional': True, 'type': 'int'}},
 'SourcePin': {'bytes': {'optional': False, 'type': 'int'},
               'path': {'optional': False, 'type': 'str'},
               'sha256': {'optional': False, 'type': 'str'}},
 'StoreAdmission': {'journal_record_bytes': {'optional': False, 'type': 'int'},
                    'public_mount_roots': {'optional': False, 'type': 'tuple'},
                    'root': {'optional': False, 'type': 'str'},
                    'run_id': {'optional': False, 'type': 'str'},
                    'single_artifact_bytes': {'optional': False, 'type': 'int'},
                    'store_contract_digest': {'optional': False, 'type': 'str'},
                    'total_write_bytes': {'optional': False, 'type': 'int'}},
 'ToolPreparation': {'limits': {'optional': False, 'type': 'object'},
                     'model_limits': {'optional': False, 'type': 'object'},
                     'name': {'optional': False, 'type': 'str'},
                     'parent': {'optional': False, 'type': 'str'},
                     'public_sources': {'optional': False, 'type': 'tuple'},
                     'seal_admission': {'optional': False, 'type': 'object'}}}


def active_constructor_manifest():
    return json.loads(json.dumps(_MANIFEST))


def _class(ident):
    if ident == 'Geometry':
        from .runtime.admission.arrays import Geometry
        return Geometry
    if ident == 'OriginalReceipt':
        from .runtime.admission.arrays import OriginalReceipt
        return OriginalReceipt
    if ident == 'IdentityConflict':
        from .runtime.admission.arrays import IdentityConflict
        return IdentityConflict
    if ident == 'Adjudication':
        from .runtime.admission.arrays import Adjudication
        return Adjudication
    if ident == 'OriginalDescriptor':
        from .runtime.admission.export import OriginalDescriptor
        return OriginalDescriptor
    if ident == 'IOLimits':
        from .runtime.context_io.filesystem import IOLimits
        return IOLimits
    if ident == 'MountAPIContract':
        from .runtime.context_io.native_seal_v1.contracts import MountAPIContract
        return MountAPIContract
    if ident == 'SealAdmission':
        from .runtime.context_io.native_seal_v1.contracts import SealAdmission
        return SealAdmission
    if ident == 'EvidencePin':
        from .runtime.core.custody import EvidencePin
        return EvidencePin
    if ident == 'InferenceParameter':
        from .runtime.core.inference import InferenceParameter
        return InferenceParameter
    if ident == 'InferenceSettings':
        from .runtime.core.inference import InferenceSettings
        return InferenceSettings
    if ident == 'RepetitionSchedule':
        from .runtime.core.inference import RepetitionSchedule
        return RepetitionSchedule
    if ident == 'InferencePolicy':
        from .runtime.core.inference import InferencePolicy
        return InferencePolicy
    if ident == 'StoreAdmission':
        from .runtime.private_store.store import StoreAdmission
        return StoreAdmission
    if ident == 'MonitorRuntime':
        from .runtime.process_guard.aggregate_v3 import MonitorRuntime
        return MonitorRuntime
    if ident == 'MemberPin':
        from .runtime.process_guard.contracts import MemberPin
        return MemberPin
    if ident == 'GuardAdmission':
        from .runtime.process_guard.contracts import GuardAdmission
        return GuardAdmission
    if ident == 'SourcePin':
        from .runtime.provider_transport.protocol import SourcePin
        return SourcePin
    if ident == 'AdapterAdmission':
        from .runtime.provider_transport.protocol import AdapterAdmission
        return AdapterAdmission
    if ident == 'PublicModelLimits':
        from .runtime.public_models.model import PublicModelLimits
        return PublicModelLimits
    if ident == 'Policy':
        from .runtime.runner.policy import Policy
        return Policy
    if ident == 'HostPreparation':
        from .runtime.runner.preparation import HostPreparation
        return HostPreparation
    if ident == 'ToolPreparation':
        from .runtime.runner.preparation import ToolPreparation
        return ToolPreparation
    if ident == 'PublicSource':
        from .runtime.runner.public_tools import PublicSource
        return PublicSource
    if ident == 'ReferenceCapacity':
        from .runtime.runner.reference import ReferenceCapacity
        return ReferenceCapacity
    if ident == 'NumericLimits':
        from .runtime.transforms.numeric import NumericLimits
        return NumericLimits
    if ident == 'AuthorityVerifier':
        from .runtime.core.custody import AuthorityVerifier
        return AuthorityVerifier
    if ident == 'RoleIssuer':
        from .runtime.runner.authority import RoleIssuer
        return RoleIssuer
    if ident == 'ReferenceData':
        from .runtime.runner.reference import ReferenceData
        return ReferenceData
    if ident == 'PrivateRunStore':
        from .runtime.private_store.store import PrivateRunStore
        return PrivateRunStore
    if ident == 'ReferenceEngine':
        from .runtime.runner.reference import ReferenceEngine
        return ReferenceEngine
    if ident == 'IntegratedFullStudy':
        from .integrated_study import IntegratedFullStudy
        return IntegratedFullStudy
    raise DeclarationError('unknown or inactive constructor ID')


_NESTED = {
    ('MountAPIContract', 'source_api_closure'): 'EvidencePin',
    ('MountAPIContract', 'native_command_controls'): 'EvidencePin',
    ('SealAdmission', 'namespace_qualification'): 'EvidencePin',
    ('SealAdmission', 'mount_api'): 'MountAPIContract',
    ('SealAdmission', 'limits'): 'IOLimits',
    ('InferencePolicy', 'settings'): 'InferenceSettings',
    ('InferencePolicy', 'schedule'): 'RepetitionSchedule',
    ('AdapterAdmission', 'inference_policy'): 'InferencePolicy',
    ('Policy', 'inference_policy'): 'InferencePolicy',
    ('HostPreparation', 'capsule_limits'): 'IOLimits',
    ('HostPreparation', 'capsule_seal_admission'): 'SealAdmission',
    ('HostPreparation', 'guard_admission'): 'GuardAdmission',
    ('HostPreparation', 'monitor_runtime'): 'MonitorRuntime',
    ('HostPreparation', 'provider_admission'): 'AdapterAdmission',
    ('HostPreparation', 'snapshot_limits'): 'IOLimits',
    ('HostPreparation', 'snapshot_seal_admission'): 'SealAdmission',
    ('ToolPreparation', 'limits'): 'IOLimits',
    ('ToolPreparation', 'seal_admission'): 'SealAdmission',
    ('ToolPreparation', 'model_limits'): 'PublicModelLimits',
}
_TUPLE_NESTED = {
    ('InferenceSettings', 'parameters'): 'InferenceParameter',
    ('GuardAdmission', 'runtime_members'): 'MemberPin',
    ('AdapterAdmission', 'source_closure'): 'SourcePin',
    ('ToolPreparation', 'public_sources'): 'PublicSource',
}


def _sequence(value):
    _need(type(value) in (list, tuple) and len(value) <= 100000,
          'bounded explicit list/tuple required; no iterable callback')
    return tuple(value)


def _convert(ident, field, value, annotation):
    key = (ident, field)
    if key in _NESTED:
        _need(type(value) is _class(_NESTED[key]), 'exact nested operative type: ' + ident + '.' + field)
        return value
    if key in _TUPLE_NESTED:
        values = _sequence(value)
        cls = _class(_TUPLE_NESTED[key])
        _need(all(type(item) is cls for item in values), 'exact typed sequence members')
        return values
    if key == ('GuardAdmission', 'initial_phase_mounts'):
        values = _sequence(value)
        # Empty is an unadmitted template; actual issued mounts replace it during
        # preparation. A JSON object cannot claim to be an issued mount.
        from .runtime.process_guard.contracts import PublicMount
        _need(all(type(item) is PublicMount for item in values), 'issued PublicMount objects only')
        return values
    if annotation == 'str':
        _need(type(value) is str and '\x00' not in value and len(value.encode('utf-8')) <= 65536,
              'bounded exact text')
        return value
    if annotation == 'int':
        _need(type(value) is int and -(2**63) <= value <= 2**63-1, 'bounded exact integer; bool rejected')
        return value
    if annotation == 'bytes':
        _need(type(value) is bytes and len(value) <= 16*1024*1024, 'explicit bounded bytes')
        return value
    if annotation.startswith('tuple'):
        values = _sequence(value)
        if 'int' in annotation or key in (('GuardAdmission', 'cpus'), ('GuardAdmission', 'memory_nodes'), ('RepetitionSchedule', 'seeds')):
            _need(all(type(x) is int and -(2**63) <= x <= 2**63-1 for x in values), 'exact integer sequence')
        elif 'float' in annotation:
            _need(all(type(x) in (int, float) and math.isfinite(x) for x in values), 'finite numeric sequence')
            values = tuple(float(x) for x in values)
        elif 'str' in annotation or key in (('StoreAdmission', 'public_mount_roots'), ('AdapterAdmission', 'argv')):
            _need(all(type(x) is str and '\x00' not in x and len(x.encode('utf-8')) <= 4096 for x in values),
                  'bounded string sequence')
        return values
    if key == ('InferenceParameter', 'value'):
        _need(type(value) in (str, int, float, list, tuple), 'closed inference parameter value')
        return tuple(value) if type(value) is list else value
    raise DeclarationError('no operative field converter: ' + ident + '.' + field)


def construct_typed(constructor_id, values):
    _need(type(constructor_id) is str and constructor_id in _FIELDS,
          'unknown, historical or runtime-issued typed constructor')
    _need(type(values) is dict, 'explicit closed constructor values required')
    fields = _FIELDS[constructor_id]
    required = {k for k, v in fields.items() if not v['optional']}
    _need(required <= set(values) <= set(fields), 'missing/unknown constructor fields')
    converted = {k: _convert(constructor_id, k, v, fields[k]['type']) for k, v in values.items()}
    if constructor_id in ('NumericLimits', 'PublicModelLimits'):
        _need(all(type(x) is int and x > 0 for x in converted.values()), 'positive numerical source capacities')
    if constructor_id == 'PublicSource':
        names = {'reference_cli.py': 'runtime/runner/reference_cli.py',
                 'public_transform.py': 'runtime/runner/public_transform.py',
                 'public_model.py': 'runtime/public_models/model.py'}
        name = converted['name']
        _need(name in names, 'fixed public source allowlist')
        pin = ACCEPTED_PARENT[names[name]]
        _need(len(converted['body']) == pin['bytes'] and
              hashlib.sha256(converted['body']).hexdigest() == converted['sha256'] == pin['sha256'],
              'public source must be exact accepted fixed code body')
    if constructor_id == 'ToolPreparation':
        sources = converted['public_sources']
        _need(len(sources) == 3 and {x.name for x in sources} ==
              {'reference_cli.py', 'public_transform.py', 'public_model.py'}, 'all three fixed public sources')
    cls = _class(constructor_id)
    try:
        obj = cls(**converted)
        if constructor_id == 'Geometry':
            obj.validate(full=True)
        elif constructor_id in ('OriginalReceipt', 'IOLimits', 'MountAPIContract', 'SealAdmission',
                                 'StoreAdmission', 'MonitorRuntime', 'MemberPin', 'SourcePin',
                                 'AdapterAdmission', 'PublicSource'):
            obj.validate()
        elif constructor_id == 'GuardAdmission':
            # Full validate needs real exports not available in an unadmitted
            # host template. Never construct a fake positive mount to satisfy it.
            if obj.initial_phase_mounts:
                obj.validate()
            else:
                _guard_template(obj)
        return obj
    except (ValueError, TypeError, KeyError) as error:
        raise DeclarationError('invalid operative ' + constructor_id) from error


def _guard_template(obj):
    import re
    from dataclasses import asdict
    from .runtime.core.custody import digest
    _need(re.fullmatch('[A-Za-z0-9_-]{1,128}', obj.context_id) is not None and obj.arm in ('F', 'I'),
          'explicit host context/arm')
    for path in (obj.bwrap_path, obj.runtime_root, obj.cgroup_parent, obj.scratch_mount):
        _absolute(path)
    _need(obj.cgroup_parent.startswith('/sys/fs/cgroup/'), 'delegated cgroup parent')
    for name in ('bwrap_sha256', 'runtime_manifest_digest', 'environment_evidence_digest',
                 'control_source_digest', 'export_allowlist_digest', 'scratch_exclusivity_evidence_digest'):
        _sha(getattr(obj, name))
    _need(type(obj.bwrap_bytes) is int and 0 < obj.bwrap_bytes <= 64*1024*1024, 'bounded bwrap identity')
    for member in obj.runtime_members:
        member.validate()
    _need(obj.runtime_members and [x.path for x in obj.runtime_members] == sorted({x.path for x in obj.runtime_members}),
          'exact sorted runtime member set')
    _need(digest([asdict(x) for x in obj.runtime_members]) == obj.runtime_manifest_digest, 'runtime member binding')
    for values, count in ((obj.cpus, 16), (obj.memory_nodes, None)):
        _need(bool(values) and values == tuple(sorted(set(values))) and all(type(x) is int and x >= 0 for x in values)
              and (count is None or len(values) == count), 'CPU16/NUMA source template')
    _need(type(obj.scratch_capacity_bytes) is int and 0 < obj.scratch_capacity_bytes <= CANDIDATE_CAPS['writable_bytes']
          and type(obj.scratch_mount_id) is int and obj.scratch_mount_id > 0
          and type(obj.cgroup_parent_mount_id) is int and obj.cgroup_parent_mount_id > 0
          and re.fullmatch('[0-9]+:[0-9]+', obj.scratch_device) is not None, 'bounded dedicated scratch template')
    # export_allowlist_digest is only syntax-checked here. Actual prepared sealed
    # exports replace/bind it and GuardAdmission.validate before native admission.


_TRUSTED_FIELDS = {
    'AuthorityVerifier': ({'issuer_id','issuer_key','root_id','root_key','expected_design'}, {'root_selection'}),
    'RoleIssuer': ({'verifier','global_bindings','domain'}, set()),
    'ReferenceData': ({'catalogue','assessment','observations','values_by_id','original_descriptors',
                       'context_key','permutation_key','source_contract_digest'}, set()),
    'PrivateRunStore': ({'admission','authority'}, {'role','domain'}),
    'ReferenceEngine': ({'data','capacity','authority','source_digest','transform_source_digest',
                         'numerical_contract_digest','store'}, set()),
    'IntegratedFullStudy': ({'reference_engine','issuer','policy','host_specs','tool_specs','export_key'}, set()),
}


def _exact(value, ident):
    _need(type(value) is _class(ident), 'trusted composition requires exact operative ' + ident)


def construct_trusted(constructor_id, values):
    _need(type(constructor_id) is str and constructor_id in _TRUSTED_FIELDS,
          'unknown/historical trusted constructor')
    _need(type(values) is dict, 'closed trusted argument dictionary')
    required, optional = _TRUSTED_FIELDS[constructor_id]
    _need(required <= set(values) <= required | optional, 'missing/unknown trusted arguments')
    v = dict(values)
    if constructor_id == 'AuthorityVerifier':
        for name in ('issuer_key', 'root_key'):
            _need(type(v[name]) is bytes and len(v[name]) >= 32, 'independently selected private key bytes required')
        for name in ('issuer_id', 'root_id'):
            _need(type(v[name]) is str and bool(v[name]), 'explicit trusted identity')
        _sha(v['expected_design'])
        _need(v.get('root_selection') is None or type(v['root_selection']) is bytes, 'exact signed envelope bytes')
    elif constructor_id == 'RoleIssuer':
        _exact(v['verifier'], 'AuthorityVerifier')
        _need(type(v['global_bindings']) is dict, 'explicit immutable digest bindings')
    elif constructor_id == 'ReferenceData':
        from .runtime.admission.catalogue import Catalogue
        from .runtime.admission.arrays import CorpusAssessment, Observation
        from .runtime.admission.export import OriginalDescriptor
        from .corpus import CanonicalMapping
        _need(type(v['catalogue']) is Catalogue and type(v['assessment']) is CorpusAssessment,
              'actual catalogue producer and assessment required')
        _need(type(v['values_by_id']) is CanonicalMapping, 'concrete selected canonical corpus mapping only')
        for name, cls in (('observations', Observation), ('original_descriptors', OriginalDescriptor)):
            _need(type(v[name]) is dict and all(type(x) is cls for x in v[name].values()),
                  'actual produced per-record objects required')
        for name in ('context_key', 'permutation_key'):
            _need(type(v[name]) is bytes and len(v[name]) >= 32, 'private selected key bytes required')
        _sha(v['source_contract_digest'])
    elif constructor_id == 'PrivateRunStore':
        from .runtime.core.custody import VerifiedAuthority
        _exact(v['admission'], 'StoreAdmission')
        _need(type(v['authority']) is VerifiedAuthority, 'actual verifier-issued authority required')
    elif constructor_id == 'ReferenceEngine':
        from .runtime.core.custody import VerifiedAuthority
        for field, ident in (('data','ReferenceData'),('capacity','ReferenceCapacity'),('store','PrivateRunStore')):
            _exact(v[field], ident)
        _need(type(v['authority']) is VerifiedAuthority, 'actual verifier-issued authority required')
        for name in ('source_digest','transform_source_digest','numerical_contract_digest'):
            _sha(v[name])
    else:
        for field, ident in (('reference_engine','ReferenceEngine'),('issuer','RoleIssuer'),('policy','Policy')):
            _exact(v[field], ident)
        for field, ident, size in (('host_specs','HostPreparation',234),('tool_specs','ToolPreparation',39)):
            _need(type(v[field]) is dict and len(v[field]) == size, 'complete actual host/tool mapping')
            for item in v[field].values():
                _exact(item, ident)
        _need(type(v['export_key']) is bytes and len(v['export_key']) >= 32, 'private export key')
    # Dispatch is statically closed; caller JSON cannot choose a module/class.
    return _class(constructor_id)(**v)
