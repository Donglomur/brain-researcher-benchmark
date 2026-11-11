"""Original-owner conservative reservations; physical observations stay separate.

No unused reservation is returned. Logical admission debits the original
partition before any grant. CPU/wall are held prospectively, never inserted as
measured child CPU. The exact EarlyResources hook below is an integration
prerequisite; this file does not silently patch an active owner.
"""
from .common import need
from .early_resources import EarlyResources
from .precommit_records import DIMENSIONS
from .backend_native_wire import validate_native_type

_LOGICAL=('read_bytes','write_bytes','work_units','process_starts','retained_bytes')
_PHYSICAL=('cpu_ns','wall_ns')
_METER=object()

class NativeReservationSlot:
    def __init__(self,ledger,partition,maximum,kind):
        self.ledger=ledger;self.partition=partition;self.maximum=dict(maximum);self.kind=kind
        self.ordinal=len(ledger.slots);self.charged={};self.physical_entered=False;self.complete=False
        self.observation=None;self.raw_first=None;self.secondaries=[];self.used=dict.fromkeys(DIMENSIONS,0)
        self.physical_parent=None;self.effect_owner=None;self.children=[]
        self.child_physical_claimed=dict.fromkeys(_PHYSICAL,0);self.nested_physical=dict.fromkeys(_PHYSICAL,0)
        self.logical_attempts=[]
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)

class NativeReservationLedger:
    def __init__(self,channel):
        from .backend_linux_channel import HNativeChannelOwner
        need(type(channel)is HNativeChannelOwner and type(channel.owner)is EarlyResources,
             'actual original H channel and original owner')
        channel.attempt.require_live_original()
        need(not channel.setup_entered and getattr(channel,'reservation_ledger',None)is None,
             'original control reserve before acquisition and child launch')
        self.channel=channel;self.owner=channel.owner;self.slots=[];self.raw_first=None;self.secondaries=[]
        self.physical={p:dict.fromkeys(_PHYSICAL,0)for p in self.owner.partitions}
        self.control_host=None;self.control_arm=None
        channel.reservation_ledger=self
        if not hasattr(self.owner,'native_receiver_ledgers'):self.owner.native_receiver_ledgers=[]
        self.owner.native_receiver_ledgers.append(self)
    def require_original(self):
        need(self.channel.reservation_ledger is self and
             any(x is self for x in self.owner.native_receiver_ledgers),'original registered reservation storage')
        self.channel.attempt.require_live_original()
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.channel.retain(error,'reservation')
    def reserve(self,partition,maximum,kind):
        self.require_original();validate_native_type('ResourceVector',maximum)
        need(not self.owner.terminal,'no new productive grant after original protected terminal entry')
        need(partition in ('host',self.channel.attempt.condition),'same H or this original arm')
        need(kind in ('control_host','control_arm'),'worker effects require actual receive owner and nested reservation path')
        slot=NativeReservationSlot(self,partition,maximum,kind);self.slots.append(slot)
        try:
            need(self.raw_first is None,'no new reservation after prior failure')
            self.owner.check()
            for dim in DIMENSIONS:
                limit=self.owner.partitions[partition][dim]
                if partition=='host':limit-=self.owner.terminal_reserve[dim]
                held=sum(x.physical[partition][dim]for x in self.owner.native_receiver_ledgers)if dim in _PHYSICAL else 0
                need(self.owner.used[partition][dim]+held+maximum[dim]<=limit,
                     'prior actual usage plus all retained original holds within same partition')
            # All logical maxima are prospective debits, not measured usage.
            # A later refusal preserves the successful earlier debit prefix.
            for dim in _LOGICAL:
                self.owner.charge(partition,dim,maximum[dim]);slot.charged[dim]=maximum[dim]
            for dim in _PHYSICAL:self.physical[partition][dim]+=maximum[dim]
            slot.physical_entered=True;slot.complete=True;return slot
        except BaseException as error:slot.retain(error);self.retain(error);raise
    def reserve_worker_effect(self,effect):
        """Retained child claim inside the actual control arm physical hold.

        Every worker effect uses this same path. Logical maxima remain new
        prospective original-arm debits; CPU/wall are never added twice.
        """
        from .backend_host_receiver import HEffectReceive,HReceiverPending,HChannelReceiver
        from .native_control_plan_v4 import NativeControlPlanV4
        self.require_original()
        need(type(effect)is HEffectReceive,'actual original host effect receive owner')
        receiver=effect.receiver;pending=effect.intent_pending
        need(type(receiver)is HChannelReceiver and type(pending)is HReceiverPending and
             receiver.ledger is self and receiver.channel is self.channel and receiver.owner is self.owner and
             receiver.activation.receiver is receiver and receiver.activation.channel is self.channel and
             self.channel.protocol is receiver and receiver.effect is effect and
             any(x is effect for x in receiver.effects) and receiver.pending is pending and
             pending.receiver is receiver and any(x is pending for x in receiver.history) and
             pending.kind=='EffectIntentV1' and pending.packet['payload']is effect.intent and
             pending.sequence==effect.sequence==receiver.sequence and
             effect.slot is None and pending.effect_slot is None,
             'same actual outstanding original packet/effect/channel/ledger occurrence')
        maximum=effect.intent['maximum'];validate_native_type('ResourceVector',maximum)
        partition=self.channel.attempt.condition
        slot=NativeReservationSlot(self,partition,maximum,'effect');self.slots.append(slot)
        slot.effect_owner=effect;slot.physical_parent=self.control_arm
        # Before any plan revalidation or debit can fail, the actual caller
        # retains this exact slot. A later exception cannot orphan its prefix.
        effect.slot=slot;pending.effect_slot=slot
        try:
            need(not self.owner.terminal and self.raw_first is None and
                 receiver.raw_first is None and not receiver.poisoned,'no productive reservation after failure/terminal')
            plan=getattr(self,'source_control_plan',None);parent=self.control_arm
            need(type(plan)is NativeControlPlanV4 and plan.ledger is self and
                 plan.attempt is self.channel.attempt and self.channel.attempt.native_control_plan is plan,
                 'actual original completed source control plan, not an equal vector')
            plan.require_original()
            need(type(parent)is NativeReservationSlot and parent.ledger is self and
                 any(x is parent for x in self.slots) and parent.partition==partition and parent.kind=='control_arm' and
                 parent.complete and parent.physical_entered and parent.raw_first is None and
                 parent.maximum==plan.arm_vector,'same unchanged complete original control arm parent hold')
            self.owner.check()
            for dim in DIMENSIONS:
                limit=self.owner.partitions[partition][dim]
                if dim in _PHYSICAL:
                    held=sum(x.physical[partition][dim]for x in self.owner.native_receiver_ledgers)
                    need(self.physical[partition][dim]==parent.maximum[dim] and
                         self.owner.used[partition][dim]+held<=limit and
                         parent.child_physical_claimed[dim]+maximum[dim]<=parent.maximum[dim],
                         'actual complete whole hold plus nonrefundable nested child sum within original cap')
                else:
                    need(self.owner.used[partition][dim]+maximum[dim]<=limit,
                         'new logical effect debit inside original residual partition')
            parent.children.append(slot)
            for dim in _PHYSICAL:
                parent.child_physical_claimed[dim]+=maximum[dim]
                slot.nested_physical[dim]=maximum[dim]
            slot.physical_entered=True
            # Claims remain retained even if a later logical debit fails or
            # the original grant is never delivered/entered/observed.
            for dim in _LOGICAL:
                slot.logical_attempts.append((dim,maximum[dim]))
                self.owner.charge(partition,dim,maximum[dim]);slot.charged[dim]=maximum[dim]
            slot.complete=True;return slot
        except BaseException as error:
            slot.retain(error);pending.retain(error)
            try:self.retain(error)
            except BaseException as later:
                if later is not error:slot.secondaries.append(later)
            raise
    def reserve_control(self,host_maximum,arm_maximum):
        need(self.control_host is None and self.control_arm is None,'one complete prior control-plane reservation')
        self.control_host=self.reserve('host',host_maximum,'control_host')
        self.control_arm=self.reserve(self.channel.attempt.condition,arm_maximum,'control_arm')
        return self
    def host_meter(self):return NativeReservedMeter(_METER,self.control_host)
    def arm_meter(self):return NativeReservedMeter(_METER,self.control_arm)

class NativeReservedMeter:
    """Source-owned cursor in an already debited original reservation."""
    def __init__(self,token,slot):
        need(token is _METER and type(slot)is NativeReservationSlot and slot.complete,
             'actual complete earlier original reserve')
        self.slot=slot;self.owner=slot.ledger.owner;self.name=slot.partition
    def check(self):
        self.slot.ledger.require_original();self.owner.check()
    def charge(self,dimension,amount):
        need(type(amount)is int and amount>=0 and dimension in _LOGICAL,
             'only source-known logical work consumes prepaid logical custody')
        self.check();s=self.slot
        need(s.used[dimension]+amount<=s.maximum[dimension],'no new budget or capacity after reservation')
        s.used[dimension]+=amount
    def record(self):return self.owner.cost_prefix()

def check_native_physical_holds(owner,partition,dimension,amount,limit):
    """Fixed hook before EarlyResources._charge mutates actual physical usage."""
    if dimension not in _PHYSICAL:return
    ledgers=getattr(owner,'native_receiver_ledgers',())
    total=0
    for ledger in ledgers:
        need(type(ledger)is NativeReservationLedger and ledger.owner is owner,'closed actual ledger registry')
        ledger.require_original();total+=ledger.physical[partition][dimension]
    need(owner.used[partition][dimension]+amount+total<=limit,'actual observation and retained prospective holds share original cap')
