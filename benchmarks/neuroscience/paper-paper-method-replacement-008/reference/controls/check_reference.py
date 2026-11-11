"""Invented NumPy arrays and explicitly substituted native leaves ONLY.

This executes the actual source functions, not Torch/official F/G, autograd or
learning. For the tiny training-caller check only, session admission is replaced
by a named small-metadata leaf; the real full-roster validator is tested separately.
"""
import contextlib
import dataclasses
import pathlib
import sys
import types
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'source'))
from barista_reference import design, producer, training


class Tensor(np.ndarray):
    device = 'invented_cpu'
    requires_grad = True
    grad = None
    def __new__(cls, value, dtype=None):
        return np.asarray(value, dtype=dtype).view(cls)
    def clone(self): return Tensor(self.copy())
    def masked_fill_(self, mask, value):
        self[np.broadcast_to(mask, self.shape)] = value
        return self
    def any(self, dim=None, **kw): return Tensor(np.asarray(self).any(axis=dim, **kw))
    def all(self, dim=None, **kw): return Tensor(np.asarray(self).all(axis=dim, **kw))
    def sum(self, dim=None, **kw): return Tensor(np.asarray(self).sum(axis=dim, **kw))
    def mean(self, **kw): return Tensor(np.asarray(self).mean(**kw))
    def square(self): return Tensor(np.square(np.asarray(self)))
    def expand(self, *dims):
        return Tensor(np.broadcast_to(self, tuple(s if d == -1 else d for s, d in zip(self.shape, dims))))
    def permute(self, *dims): return Tensor(np.asarray(self).transpose(dims))
    def detach(self): return self
    def cpu(self): return self
    def numpy(self): return np.asarray(self)
    def backward(self): EVENTS.append('backward')
    def new_zeros(self, shape): return Tensor(np.zeros(shape, dtype=self.dtype))
    def copy_(self, other): self[...] = other; return self


EVENTS = []
OPTIMIZERS = []


class AdamW:
    def __init__(self, groups, **kwargs):
        self.param_groups, self.kwargs, self.rates = groups, kwargs, []
        OPTIMIZERS.append(self)
    def zero_grad(self, **kwargs): EVENTS.append('zero_grad')
    def step(self):
        self.rates.append(tuple(g['lr'] for g in self.param_groups))
        EVENTS.append('step')


TORCH = types.SimpleNamespace(
    bool=np.dtype('bool'), float32=np.dtype('float32'), float64=np.dtype('float64'),
    isfinite=lambda x: Tensor(np.isfinite(x)),
    tensor=lambda x, dtype=None, device=None: Tensor(x, dtype),
    zeros=lambda shape, dtype=None, device=None: Tensor(np.zeros(shape, dtype=dtype)),
    manual_seed=lambda seed: EVENTS.append(('seed', seed)),
    no_grad=contextlib.nullcontext, optim=types.SimpleNamespace(AdamW=AdamW))


def full_session(person):
    train, val, test, c = design.COUNTS[person]
    return {'person': person, 'recording': design.RECORDINGS[person],
            'channels': tuple(f'INVENTED-channel-{i}' for i in range(c)),
            'groups': {'channels': tuple(str(i) for i in range(c)),
                       'parcels': tuple(str(i//3) for i in range(c)),
                       'lobes': tuple(str(i//20) for i in range(c))},
            'splits': {role: tuple(f'INVENTED-{role}-{i}' for i in range(n))
                       for role, n in zip(('train', 'validation', 'test'), (train,val,test))}}


class Params:
    def __init__(self): self.p = Tensor([1.0])
    def parameters(self): return [self.p]


class Module:
    def __call__(self,*args,**kwargs): return self.forward(*args,**kwargs)
    def load_state_dict(self,state,strict): EVENTS.append(('strict_load',strict))


class Linear(Module):
    def __init__(self,a,b,bias): self.a,self.b,self.bias = a,b,bias
    def forward(self,x):
        if x.shape[-1] != self.a: raise AssertionError('Wrong invented linear width')
        return Tensor(np.broadcast_to(np.asarray(x).mean(axis=-1,keepdims=True),x.shape[:-1]+(self.b,)))


class GELU(Module):
    def forward(self,x): return x  # Explicit identity native leaf, not native GELU.


class Dropout(Module):
    def __init__(self,p): self.p=p
    def forward(self,x): return x  # No stochastic kernel is exercised.


class Sequential(Module):
    def __init__(self,*layers): self.layers=layers
    def forward(self,x):
        for layer in self.layers: x=layer(x)
        return x


class InventedBarista(Module):
    def __init__(self,config,metadata): self.metadata=metadata;self.contexts=[];self.g_calls=[]
    def tokenizer(self,inputs,sessions,**kwargs):
        x=inputs[0];self.contexts.append(x.copy());b,_,c=x.shape
        tokens=Tensor(np.repeat(np.asarray(x[:,::512,:]).reshape(1,b*12*c,1),64,axis=-1))
        return types.SimpleNamespace(tokens=tokens,spatial_embeddings=Tensor(np.full(tokens.shape,.25)),
                                     seq_lens=[12*c]*b,position_ids=Tensor(np.tile(np.repeat(np.arange(12),c),b)[None,:]))
    def backbone(self,**kwargs): self.g_calls.append(kwargs);return kwargs['x']


class InventedModel:
    def __init__(self):
        self.base, self.h, self.waveform_head = Params(), Params(), Params()
        self.mask_token = Tensor([0.0])
        self.reference_config = design.ReferenceConfig(batch_size=2)
        self.model_name = 'barista_channels_channels'
        self.fitted_training_ids = None
        self.history, self.calls = [], []
    def parameters(self):
        return self.base.parameters()+self.h.parameters()+[self.mask_token]+self.waveform_head.parameters()
    def train(self): EVENTS.append('train')
    def eval(self): EVENTS.append('eval')
    def __call__(self, x, mask, native):
        context = producer.sanitize_context(x, mask)
        self.calls.append((context.copy(), mask.copy(), native))
        # Declared invented producer leaf, intentionally no actual F/G/H learning.
        return (Tensor(np.zeros((len(x),12,x.shape[-1],512))),
                Tensor(np.zeros((len(x),12,x.shape[-1],512))))


class Controls(unittest.TestCase):
    def setUp(self):
        EVENTS.clear(); OPTIMIZERS.clear()
        self.torch_patch = patch.dict(sys.modules, {'torch': TORCH})
        self.torch_patch.start()
    def tearDown(self): self.torch_patch.stop()

    def test_full_programme_and_split_rejection(self):
        sessions = tuple(full_session(p) for p in design.PEOPLE)
        cells = design.programme_cells(sessions)
        self.assertEqual(len(cells),168)
        self.assertEqual({c['model'] for c in cells}, set(design.MODELS))
        self.assertEqual(sum(design.COUNTS[p][3] for p in design.PEOPLE)*24,22680)
        bad = full_session(1)
        bad['splits']['test'] = bad['splits']['train'][:348]
        with self.assertRaises(ValueError): design.validate_session(bad)
        with self.assertRaises(ValueError): design.programme_cells(sessions[:-1])

    def test_whole_group_nearest_fraction_and_no_context(self):
        groups = ('a','a','a','b','b','c','c','c','c','c')
        mask = design.choose_group_mask(groups,7)
        self.assertEqual(sum(mask),3)
        unequal = design.choose_group_mask(('a','a','b','b','b'),3)
        self.assertEqual(sum(unequal),2)  # 40%, explicitly not30%.
        self.assertEqual(mask, design.choose_group_mask(groups,7))
        with self.assertRaises(ValueError): design.choose_group_mask(('a','a'),0)

    def test_schedule_and_configuration(self):
        c = design.ReferenceConfig()
        self.assertEqual([design.epoch_schedule(i,c)['alpha'] for i in (0,9,10,19)], [1,1,.9,0])
        self.assertAlmostEqual(design.epoch_schedule(0,c)['pretrained_lr'],.0002)
        self.assertAlmostEqual(design.epoch_schedule(1,c)['head_lr'],.0036)
        self.assertAlmostEqual(design.epoch_schedule(4,c)['head_lr'],.0084)
        self.assertAlmostEqual(design.epoch_schedule(5,c)['head_lr'],.01)
        self.assertAlmostEqual(design.epoch_schedule(6,c)['head_lr'],.0099)
        with self.assertRaises(ValueError): dataclasses.replace(c,epochs=19).validate()

    def test_target_masking_before_model_and_input_unchanged(self):
        x = Tensor(np.ones((2,6144,3)))
        x[:,:,1] = 987
        mask = Tensor([[False,True,False],[True,False,False]],bool)
        result = producer.sanitize_context(x,mask)
        self.assertTrue((result[0,:,1] == 0).all())
        self.assertTrue((result[1,:,0] == 0).all())
        self.assertTrue((x[:,:,1] == 987).all())
        with self.assertRaises(ValueError): producer.sanitize_context(x,Tensor(np.ones((2,3),bool)))

    def test_loss_per_token_not_per_sample_and_branch_selection(self):
        gold = Tensor(np.zeros((1,12,2,512)))
        prediction = Tensor(np.full(gold.shape,2.0))
        observed = Tensor(np.full(gold.shape,3.0))
        mask = Tensor([[True,False]],bool)
        total, target, aux = producer.reconstruction_loss(prediction,observed,gold,mask,.5)
        self.assertEqual(float(target),2048)
        self.assertEqual(float(aux),4608)
        self.assertEqual(float(total),4352)
        prediction[:,:,1,:] = 1000
        observed[:,:,0,:] = 2000
        self.assertEqual(float(producer.reconstruction_loss(prediction,observed,gold,mask,.5)[0]),4352)

    def test_actual_training_and_query_callers_with_declared_small_leaves(self):
        model = InventedModel()
        session = {'person':1, 'channels':('x','y'),
                   'groups':{'channels':('x','y')},
                   'splits':{'train':('INVENTED-train0','INVENTED-train1'),
                             'test':('INVENTED-test0',)}}
        x = Tensor(np.full((2,6144,2),2.0))
        with patch.object(training,'_validate_model_session',return_value='INVENTED-native'):
            with self.assertRaises(ValueError):
                training.fit_cell(model,session,x,session['splits']['test'],arm=design.ARMS[0])
            self.assertFalse(OPTIMIZERS)
            history = training.fit_cell(model,session,x,session['splits']['train'],arm=design.ARMS[0])
            self.assertEqual(len(history),20)
            self.assertEqual(len(model.calls),20)
            self.assertEqual(EVENTS.count('backward'),20)
            self.assertEqual(EVENTS.count('step'),20)
            self.assertEqual(OPTIMIZERS[0].kwargs['weight_decay'],.01)
            self.assertEqual([g['name'] for g in OPTIMIZERS[0].param_groups],['FGH_mask','waveform_head'])
            self.assertEqual([len(g['params']) for g in OPTIMIZERS[0].param_groups],[3,1])
            for i,rates in enumerate(OPTIMIZERS[0].rates):
                s = design.epoch_schedule(i,model.reference_config)
                self.assertEqual(rates,(s['pretrained_lr'],s['head_lr']))
            self.assertEqual([h['alpha'] for h in history][9:11],[1,.9])
            self.assertEqual({h['realized_masked_token_fraction'] for h in history},{.5})
            before_steps = EVENTS.count('step')
            out = list(training.predict_channel(model,session,Tensor(np.full((1,6144,1),9.0)),
                       ('x',),session['splits']['test'],'y',arm=design.ARMS[0]))
            self.assertEqual(out[0].shape,(1,6144))
            self.assertTrue((model.calls[-1][0][:,:,1] == 0).all())
            self.assertTrue((model.calls[-1][0][:,:,0] == 9).all())
            self.assertEqual(EVENTS.count('step'),before_steps)
            with self.assertRaises(ValueError):
                list(training.predict_channel(model,session,Tensor(np.ones((1,6144,1))),
                     ('x',),session['splits']['train'],'y',arm=design.ARMS[0]))

    def test_parameter_partition_rejects_alias_and_frozen_state(self):
        m = InventedModel()
        m.waveform_head = m.h
        with self.assertRaises(ValueError): training.optimizer_groups(m)

    def test_actual_constructor_and_forward_with_explicit_native_leaves(self):
        backbone=types.SimpleNamespace(d_hidden=64,num_layers=12,num_heads=4,d_input=64,d_out=64,
            mlp_ratio=4,norm='rmsnorm',norm_eps=1e-8,activation='gelu',max_position=1024,dropout=.1)
        tokenizer=types.SimpleNamespace(spatial_grouping='coords',temporal_subsegment_len=512,
            temporal_subsegment_step=512,samp_frequency=2048,num_seconds=3,add_spatial_encoding=True,
            temporal_encoder=types.SimpleNamespace(hidden_dims=5,depth=4,kernel_size=3,stride=1))
        config=types.SimpleNamespace(backbone=backbone,tokenizer=tokenizer)
        nn=types.SimpleNamespace(Module=Module,Linear=Linear,GELU=GELU,Dropout=Dropout,
                                 Sequential=Sequential,Parameter=Tensor)
        with patch.object(TORCH,'nn',nn,create=True), \
             patch.object(TORCH,'random',types.SimpleNamespace(fork_rng=lambda **k: contextlib.nullcontext()),create=True), \
             patch.object(TORCH,'where',lambda m,a,b: Tensor(np.where(m,a,b)),create=True), \
             patch.dict(sys.modules,{'barista.models.model':types.SimpleNamespace(Barista=InventedBarista)}):
            model=producer.make_reconstructor(config,object(),'barista_channels_channels',
                design.ReferenceConfig(),initialization='pretrained_FG_fresh_H',backbone_state={})
            self.assertEqual(sum(isinstance(l,Linear) for l in model.h.layers),4)
            self.assertEqual(sum(isinstance(l,Dropout) for l in model.h.layers),3)
            self.assertEqual(sum(isinstance(l,GELU) for l in model.h.layers),4)
            self.assertEqual((model.waveform_head.a,model.waveform_head.b),(64,512))
            x=Tensor(np.ones((2,6144,3)));x[:,:,1]=987
            mask=Tensor([[False,True,False],[False,True,False]],bool)
            prediction,observed=model(x,mask,'INVENTED-native')
            self.assertEqual(prediction.shape,(2,12,3,512))
            self.assertTrue((model.base.contexts[0][:,:,1]==0).all())
            mixed=model.base.g_calls[0]['x'].reshape(2,12,3,64)
            self.assertTrue((mixed[:,:,1,:]==.25).all())  # M+E, never gold token.
            self.assertTrue((mixed[:,:,0,:]==1.25).all()) # F+E exactly once.
            x[:,:,1]=-2000
            self.assertTrue((model(x,mask,'INVENTED-native')[0] == prediction).all())
            with self.assertRaises(ValueError):
                producer.make_reconstructor(config,object(),'barista_channels_channels',
                    design.ReferenceConfig(),initialization='bound_FGH',backbone_state={})


if __name__ == '__main__': unittest.main(verbosity=2)
