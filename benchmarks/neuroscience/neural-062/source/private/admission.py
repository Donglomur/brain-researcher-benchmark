"""Independently selected signature authority; no issuer or qualification is fabricated."""
import hashlib
from pathlib import Path
from contract import exact,pin,require,programme,path
EVIDENCE_ROLES=('full_release_source_admission','native_schema_clock_roi_projection','protected_split_and_target_barrier','linux_isolation_retirement_and_resources','fixed_reference_and_grader_validation')
def admit(root,root_pin,grant,public_key,public_key_pin,owner):
 with owner.stage('independent_execution_admission'):
  import delivery_io as io
  raw=io.read(root,4_000_000,root_pin);key=io.read(public_key,32,public_key_pin)
  signed=io.json_file(grant,1_000_000);exact(signed,['payload','signature_hex']);payload=signed['payload']
  exact(payload,['schema','root_sha256','source_sha256','environment','purposes','qualification_evidence'])
  require(payload['schema']=='neural062.execution-grant.v1'and payload['root_sha256']==hashlib.sha256(raw).hexdigest(),'root binding')
  config=programme(io.decode(raw))
  require(payload['source_sha256']==hashlib.sha256(io.canonical(config['source'])).hexdigest()and payload['environment']==config['environment'],'source/environment binding')
  require(payload['purposes']==['prepare','reference','candidate_fit','candidate_infer','protected_score'],'exact execution purposes')
  # Authenticate the real independently chosen issuer before any evidence pathname effect.
  from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
  require(type(signed['signature_hex'])is str and len(signed['signature_hex'])==128,'Ed25519 signature')
  Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(signed['signature_hex']),io.canonical(payload))
  evidence=payload['qualification_evidence'];require(type(evidence)is list and len(evidence)==len(EVIDENCE_ROLES),'complete external evidence roles')
  require([r['role']for r in evidence]==list(EVIDENCE_ROLES),'source-fixed evidence order')
  for r in evidence:
   exact(r,['role','path','pin']);path(r['path']);pin(r['pin']);require(r['pin']['bytes']<=1_000_000,'bounded operator metadata evidence')
   io.read(io.resolve(Path(root).absolute().parent,r['path']),1_000_000,r['pin'])
  # Trust establishment and adjudication of these evidence bodies is an external root
  # operation. This package has no trusted key, signed grant, evidence or issuer.
  return config
