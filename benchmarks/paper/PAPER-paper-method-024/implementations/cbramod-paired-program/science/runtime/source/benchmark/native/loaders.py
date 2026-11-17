"""TRAIN/validation-only use of exact official CustomDataset and collate bodies."""
from pathlib import Path
from .policy import digest,need
from preprocessing_current.observations import observe_loaded_dataset

def training_dataset(module,desc,inputs_root):
 """No official LoadDataset call: it opens test partitions eagerly."""
 root=Path(inputs_root)/desc['prepared_root'];keys=desc['source_keys'];kind=desc['dataset_id']
 if kind=='ISRUC':
  pairs=[(str(root/a),str(root/b))for a,b in keys]
  ds=module.CustomDataset(pairs)
 elif kind=='TUEV':ds=module.CustomDataset(str(root),list(keys))
 elif kind in ('CHB-MIT','TUAB'):
  # Bind explicit qualified order without an additional filesystem enumeration.
  # Preserve the exact official __getitem__ (CHB resampling) and collate methods.
  ds=module.CustomDataset.__new__(module.CustomDataset)
  ds.files=[str(root/desc['split']/k)for k in keys]
 else:
  ds=module.CustomDataset(str(root),mode=desc['split'])
  need(list(ds.keys)==keys,'LMDB source key order differs from qualified descriptor')
 need(len(ds)==len(keys),'complete training/validation source roster')
 lineage=observe_loaded_dataset(kind,desc['split'],ds,root,desc['group_by_key'])
 need(lineage['source_keys']==keys and lineage['lineage_sha256']==desc['lineage_sha256'],'actual loader metadata/declared lineage join before sample access')
 return ds

def loaders(components,plan,inputs_root):
 torch=components['torch'];module=components['loader'];out={}
 for split in ('train','val'):
  ds=training_dataset(module,plan[split],inputs_root)
  out[split]=torch.utils.data.DataLoader(ds,
   batch_size=1 if split=='val' and plan['dataset_id']=='ISRUC' else plan['params']['batch_size'],
   collate_fn=ds.collate,shuffle=split=='train')
 # The unmodified official Trainer constructor creates a test Evaluator. It gets
 # an empty inert iterable; the derived loop never invokes that evaluator.
 out['test']=()
 return out
