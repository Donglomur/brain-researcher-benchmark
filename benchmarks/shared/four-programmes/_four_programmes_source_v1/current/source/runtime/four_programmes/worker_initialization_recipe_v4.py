"""Actual source-derived base/five-artifact recipe over original V3 owners.

Logical requirements reuse the real consumers' equations. Physical values come
only from the same immutable installed expectation and its existing whole hold.
"""
from pathlib import PurePosixPath
from .common import need
from .worker_backend_v3 import WorkerBackendOwnerV3,_metadata_floor
from .worker_native_io_v3 import artifact_requirements_v3
from .worker_initialization_profile_v4 import WorkerInitializationPhysicalProfileV4,OPERATIONS
from .worker_channel_v3 import require_capture
from .worker_meter_v3 import WorkerEffectAttempt
from .worker_context_records_v3 import validate

_RECIPE=object();_OPERATION=object()
_DIMENSIONS=('read_bytes','write_bytes','work_units','process_starts','cpu_ns','wall_ns','retained_bytes')

class WorkerInitializationOperationV4:
    __slots__=('recipe','ordinal','operation','site','stage','prior','vector','effect','capture','complete')
    def __init__(self,token,recipe,ordinal,prior,maximum):
        need(token is _OPERATION,'fixed source recipe occurrence only')
        self.recipe=recipe;self.ordinal=ordinal;self.operation=OPERATIONS[ordinal]
        self.site='local_parse'if ordinal==0 else'artifact_read';self.stage='initialization'
        self.prior=prior;self.vector=tuple(maximum[k]for k in _DIMENSIONS)
        self.effect=None;self.capture=None;self.complete=False
    @property
    def maximum(self):return dict(zip(_DIMENSIONS,self.vector))

class WorkerInitializationRecipeV4:
    def __init__(self,token,backend,profile):
        need(token is _RECIPE,'fixed original initialization recipe factory')
        self.backend=backend;self.profile=profile;self.operations=[];self.next_ordinal=0;self.preparation_attempts=[]
        self.raw_first=None;self.secondaries=[];self.complete=False
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        try:self.backend.retain(error,'initialization_recipe')
        except BaseException as later:
            if later is not self.raw_first:self.secondaries.append(later)
    def require_original(self):
        if self.raw_first is not None:raise self.raw_first
        b=self.backend;b.admission.require_original()
        need(type(b)is WorkerBackendOwnerV3 and b.context.backend is b and
             getattr(b,'initialization_recipe_v4',None)is self and b.raw_first is None,
             'same actual registered original recipe/backend')
        self.profile.require_original(b.context);return self
    def next_operation(self):
        if self.raw_first is not None:raise self.raw_first
        try:
            need(len(self.preparation_attempts)==self.next_ordinal,'no repeated or failed operation recipe production')
            self.preparation_attempts.append(self.next_ordinal)
            return self._derive_next_operation()
        except BaseException as error:self.retain(error);raise self.raw_first
    def _derive_next_operation(self):
        self.require_original();b=self.backend;ordinal=self.next_ordinal
        need(0<=ordinal<6 and len(self.operations)==ordinal and b.meter.current_effect is None and
             b.publisher.pending_publication is None,'one source operation after every original predecessor acknowledgement')
        role=OPERATIONS[ordinal]
        prior=b.base_effect_operands_v3()if ordinal==0 else b.artifact_effect_operands_v3(role)
        extent=sum(len(c.raw)for c in prior)
        # This metadata inspection consumes an existing prepaid source-check
        # occurrence; it does not borrow a future artifact grant for parsing.
        b.context.channel.endpoint.reserve_source_check(extent)
        if ordinal==0:
            need(b.base is None and not b.base_entered,'unentered original base before recipe production')
            logical={**_metadata_floor(prior),'read_bytes':0,'write_bytes':0,'process_starts':0}
        else:
            need(b.base is not None and b.admission.decoded is not None and role not in b.artifact_attempts,
                 'actual original base and unattempted full artifact role')
            selection=b.admission.decoded['NativeArtifactRootSelectionV1']
            row=selection['roles'][ordinal-1];need(row['role']==role,'complete original ordered artifact selection')
            roots=[r for r in b.admission.root_rows if r['root_id']==row['root_id']]
            need(len(roots)==1,'same original selected complete root')
            root=roots[0];absolute=root['absolute_mount'];path=PurePosixPath(absolute);parts=row['relative_components']
            need(type(absolute)is str and absolute.startswith('/') and str(path)==absolute and len(absolute)<=4096 and
                 all(c not in ('','.','..')for c in path.parts[1:]) and type(parts)is list and 1<=len(parts)<=64 and
                 all(type(c)is str and 0<len(c)<=255 and c not in ('.','..')and'/'not in c and'\0'not in c for c in parts),
                 'complete source-selected absolute and relative artifact route')
            logical=artifact_requirements_v3(row['selected']['bytes'],1+len(path.parts[1:])+len(parts),extent)
        physical=self.profile.rows[ordinal]
        need(physical[:4]==(ordinal,role,'local_parse'if ordinal==0 else'artifact_read','initialization'),
             'same original exact physical operation occurrence')
        maximum={**logical,'cpu_ns':physical[4],'wall_ns':physical[5]};validate('ResourceVector',maximum)
        op=WorkerInitializationOperationV4(_OPERATION,self,ordinal,prior,maximum)
        self.operations.append(op);return op
    def retain_effect(self,operation,effect):
        b=self.backend
        need(type(operation)is WorkerInitializationOperationV4 and operation.recipe is self and
             self.operations[self.next_ordinal]is operation and operation.effect is None and
             type(effect)is WorkerEffectAttempt and effect.meter is b.meter and b.meter.current_effect is effect and
             effect.site==operation.site and effect.stage==operation.stage and effect.maximum==operation.maximum and
             effect.ordinal==(0 if operation.ordinal==0 else operation.ordinal-1) and
             len(effect.prior_captures)==len(operation.prior) and all(x is y for x,y in zip(effect.prior_captures,operation.prior)),
             'actual reserved effect occurrence and exact original source operands')
        operation.effect=effect;return effect
    def accept(self,operation,capture):
        self.require_original();b=self.backend;effect=operation.effect
        need(self.operations[self.next_ordinal]is operation and not operation.complete and effect is not None and
             effect.finished and effect.reported and effect.raw_first is None and b.meter.current_effect is None,
             'actual completed and acknowledged original composite operation')
        kind='BackendAttemptBase'if operation.ordinal==0 else'ArtifactObservation'
        require_capture(capture,b.context,kind)
        expected=b.base if operation.ordinal==0 else b.artifact_captures.get(operation.operation)
        need(capture is expected and capture.origin=='publication_ack','actual completed original backend publication')
        operation.capture=capture;operation.complete=True;self.next_ordinal+=1
        self.complete=self.next_ordinal==6;return capture

def produce_worker_initialization_recipe_v4(backend):
    need(type(backend)is WorkerBackendOwnerV3 and getattr(backend,'initialization_recipe_v4',None)is None,
         'one recipe producer on actual backend, including failed attempts')
    profile=backend.context.channel.endpoint.admission.initialization_profile
    need(type(profile)is WorkerInitializationPhysicalProfileV4,'actual independently installed physical selection')
    recipe=WorkerInitializationRecipeV4(_RECIPE,backend,profile);backend.initialization_recipe_v4=recipe
    try:recipe.require_original();return recipe
    except BaseException as error:recipe.retain(error);raise recipe.raw_first
