"""Real original-CNN and matched arm training, deferred until native admission.

Construction never imports torch/lightning/numpy or runs a fit. Empirical
competence is unmeasured; this is an implemented supervised reference recipe.
"""
from pathlib import Path
import hashlib,importlib,sys,types,copy
from programme.contracts import need
from .protocol import ARMS,SEEDS,BATCH,LEARNING_RATE,SOURCE_MAX_EPOCHS,CALIBRATION_EPOCHS,TIMING_L2

ORIGINAL={
 'libribrain_experiments/models/configurable_modules/classification_module.py':(7493,'10abe1a54a2d609a04fec51609097c451594a4a5e0041171eb1255e28eab67d6'),
 'libribrain_experiments/models/configurable_modules/utils.py':(4212,'28a7ae223678e2574375acea58bd61c2dbe86a9acf6a11e10bf640069a58d415'),
 'libribrain_experiments/models/util_layers.py':(200,'74a20ea3e741b5b32a43623708970966dc1c8d0949370f7df612caaeb1f5cd97'),
 'libribrain_experiments/models/average_groups.py':(872,'1a4d14c590eddcd6985c289b091b1c9770b1864deff68cdfaf7f56f06f592482')}

def original_config(channels=306):
    return [{'conv1d':{'in_channels':channels,'out_channels':128,'kernel_size':7,'stride':1,'padding':'same'}},
            {'resnet_block':{'model_config':[{'elu':None},{'conv1d':{'in_channels':128,'out_channels':128,'kernel_size':3,'stride':1,'padding':'same'}},
                                           {'elu':None},{'conv1d':{'in_channels':128,'out_channels':128,'kernel_size':1,'stride':1,'padding':'same'}}]}},
            {'elu':None},{'conv1d':{'in_channels':128,'out_channels':128,'kernel_size':50,'stride':25}},
            {'elu':None},{'conv1d':{'in_channels':128,'out_channels':128,'kernel_size':7,'stride':1,'padding':'same'}},
            {'elu':None},{'conv1d':{'in_channels':128,'out_channels':512,'kernel_size':4,'padding':0}},
            {'relu':None},{'dropout':{'p':0.5}},{'conv1d':{'in_channels':512,'out_channels':39,'kernel_size':1,'padding':0}},{'flatten':None}]

def source_identity(root,account=None,ledger=None):
    from .custody import open_pinned,Ledger,Accounting
    from programme.contracts import Asset,Pin
    ledger=ledger if ledger is not None else Ledger();account=account if account is not None else Accounting(1048576,1);observed={}
    for relative,(size,sha) in ORIGINAL.items():
        path='vendor/experiments/'+relative
        f,_=open_pinned(root,Asset(path,Pin(size,sha)),account,ledger)
        ledger.attempt('model-source-close:'+relative,f.close);ledger.raise_first()
        observed[relative]={'bytes':size,'sha256':sha}
    return observed

def original_class(root,account,ledger):
    root=Path(root);source_identity(root,account,ledger);vendor=(root/'vendor/experiments').resolve()
    # Do not accept an unrelated installed package with the same import name.
    for name,relative in [('libribrain_experiments','libribrain_experiments'),('libribrain_experiments.models','libribrain_experiments/models'),
                          ('libribrain_experiments.models.configurable_modules','libribrain_experiments/models/configurable_modules')]:
        location=str(vendor/relative)
        if name in sys.modules:need(tuple(sys.modules[name].__path__)==(location,),'original package namespace identity')
        else:
            module=types.ModuleType(name);module.__path__=[location];module.__package__=name;sys.modules[name]=module
    name='libribrain_experiments.models.configurable_modules.classification_module'
    module=importlib.import_module(name)
    for relative in ORIGINAL:
        key=relative[:-3].replace('/','.')
        loaded=sys.modules.get(key);need(loaded is not None and Path(loaded.__file__).resolve()==vendor/relative,'actual original imported dependency path')
    source_identity(root,account,ledger)
    return module.ClassificationModule

def make_model(root,arm,vocabulary_size,account,ledger):
    need(arm in ARMS,'selected five-arm architecture')
    import torch
    from torch import nn
    if arm in ('neural','time_shifted_neural','acoustic'):
        Klass=original_class(root,account,ledger)
        return Klass(original_config(80 if arm=='acoustic' else 306),39,
                     {'name':'adam','config':{'lr':LEARNING_RATE}}, {'name':'cross_entropy'})
    if arm=='timing':return nn.Sequential(nn.Linear(25,128),nn.ELU(),nn.Linear(128,39))
    need(type(vocabulary_size) is int and 2<=vocabulary_size<=50002,'training-only bounded vocabulary')
    class TranscriptClassifier(nn.Module):
        def __init__(self):
            super().__init__();self.embedding=nn.Embedding(vocabulary_size,128,padding_idx=0)
            self.gru=nn.GRU(128,128,batch_first=True);self.output=nn.Linear(128+25,39)
        def forward(self,batch):
            tokens,timing,lengths=batch
            # Feature encoder left-pads; repack each valid suffix before the GRU.
            packed_tokens=torch.zeros_like(tokens)
            for i,length in enumerate(lengths.tolist()):
                if length:packed_tokens[i,:length]=tokens[i,-length:]
            embedded=self.embedding(packed_tokens)
            lengths=lengths.clamp(min=1)
            # Empty contexts retain one explicit PAD token; no query words fit a vocabulary.
            packed=nn.utils.rnn.pack_padded_sequence(embedded,lengths.cpu(),batch_first=True,enforce_sorted=False)
            _,hidden=self.gru(packed)
            return self.output(torch.cat((hidden[-1],timing),dim=1))
    return TranscriptClassifier()

def logits(model,batch,arm,device):
    x=batch['values'].to(device)
    if arm=='transcript':return model((x.long(),batch['timing'].to(device),batch['lengths']))
    return model(x)

def reset_seed(seed,torch):
    need(seed in SEEDS,'all ten selected seeds; no arbitrary seed')
    torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    # Actual deterministic support or refusal belongs to selected library/device qualification.
    torch.use_deterministic_algorithms(True)

def train_epoch(model,loader,optimizer,arm,device,torch):
    model.train();seen=0
    for batch in loader:
        y=batch['labels'].to(device);optimizer.zero_grad(set_to_none=True)
        out=logits(model,batch,arm,device)
        need(tuple(out.shape)==(len(y),39),'actual complete39-logit producer')
        loss=torch.nn.functional.cross_entropy(out,y)
        need(bool(torch.isfinite(loss).item()),'finite training objective')
        loss.backward();optimizer.step();seen+=len(y)
    need(seen==len(loader.dataset),'every training row exactly once per epoch')
    return seen

def validation_loss(model,loader,arm,device,torch):
    from .probability import normalize_probability,row_loss,mean_loss
    model.eval();losses=[];seen=0
    with torch.no_grad():
        for batch in loader:
            y=batch['labels'].to(device);out=logits(model,batch,arm,device)
            need(tuple(out.shape)==(len(y),39),'validation full shape')
            probabilities=torch.softmax(out,dim=1).cpu().tolist();labels=y.cpu().tolist()
            losses.extend(row_loss(normalize_probability(p),int(label)) for p,label in zip(probabilities,labels))
            seen+=len(y)
    need(seen==len(loader.dataset) and seen>0,'all source validation rows')
    return mean_loss(losses,seen)

def fit_and_predict(root,arm,seed,views,device,checkpoint_capture):
    """Consume materialized arm-only inner/final views and produce all queries.

    views.loader(stage,role,seed,shuffle) must return the concrete ArmDataset
    loader defined in views.py. No full source catalogue or target loader is
    accepted by this worker. Native owner admits this whole process beforehand.
    """
    import torch
    before=source_identity(root,views.accounting,views.ledger)
    reset_seed(seed,torch)
    inner=make_model(root,arm,views.vocabulary_size('inner'),views.accounting,views.ledger).to(device)
    opt=torch.optim.Adam(inner.parameters(),lr=LEARNING_RATE,betas=(.9,.999),eps=1e-8,weight_decay=TIMING_L2 if arm=='timing' else 0.)
    train=views.loader('inner','train',seed,True);tune=views.loader('inner','tune',seed,False)
    history=[];selected_epoch=None;best=None
    for epoch in range(1,SOURCE_MAX_EPOCHS+1):
        train_epoch(inner,train,opt,arm,device,torch);loss=validation_loss(inner,tune,arm,device,torch)
        history.append({'epoch':epoch,'source_validation_loss':loss})
        if best is None or loss<best:best=loss;selected_epoch=epoch
    need(selected_epoch is not None,'source-selected finite epoch count')
    # Fresh same-seed refit includes all final source TRAIN, never CAL or query.
    del inner,opt,train,tune
    views.release_stage('inner')
    reset_seed(seed,torch);model=make_model(root,arm,views.vocabulary_size('final'),views.accounting,views.ledger).to(device)
    opt=torch.optim.Adam(model.parameters(),lr=LEARNING_RATE,betas=(.9,.999),eps=1e-8,weight_decay=TIMING_L2 if arm=='timing' else 0.)
    refit=views.loader('final','train',seed,True)
    for _ in range(selected_epoch):train_epoch(model,refit,opt,arm,device,torch)
    source_capture=checkpoint_capture('source',model.state_dict(),{'seed':seed,'epochs':selected_epoch,'history':history})
    count=views.count('final','calibration')
    if count:
        need(count==1024,'complete equal1024-label adaptation')
        opt=torch.optim.Adam(model.parameters(),lr=LEARNING_RATE,betas=(.9,.999),eps=1e-8,weight_decay=TIMING_L2 if arm=='timing' else 0.)
        cal=views.loader('final','calibration',seed,True)
        for _ in range(CALIBRATION_EPOCHS):train_epoch(model,cal,opt,arm,device,torch)
    final_capture=checkpoint_capture('final',model.state_dict(),{'source':source_capture,'seed':seed,'calibration_rows':count,'calibration_epochs':10 if count else 0})
    query=views.loader('final','query',seed,False);model.eval();predictions=[]
    with torch.no_grad():
        for batch in query:
            need('labels' not in batch,'query target absent from actual worker dataset')
            out=logits(model,batch,arm,device);need(tuple(out.shape)==(len(batch['ids']),39),'all original query rows')
            p=torch.softmax(out,dim=1);need(bool(torch.isfinite(p).all().item()),'finite complete probabilities')
            predictions.extend({'query_id':i,'probabilities':r} for i,r in zip(batch['ids'],p.cpu().tolist()))
    need(len(predictions)==len(query.dataset) and len({r['query_id'] for r in predictions})==len(predictions),'complete unique worker capture')
    need(source_identity(root,views.accounting,views.ledger)==before,'actual original reference sources stable through fitting/inference')
    return {'predictions':predictions,'seed':seed,'arm':arm,'source_checkpoint':source_capture,'final_checkpoint':final_capture,
            'source_validation':history,'selected_epoch':selected_epoch,'calibration_labels':count,'reference_executed':True,
            'research_qualified':False,'empirical_competence':'unassessed by source construction'}
