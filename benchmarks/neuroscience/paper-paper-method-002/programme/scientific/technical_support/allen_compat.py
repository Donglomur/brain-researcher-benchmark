"""Root-selected prospective Jaxley0.8.2 dimensional/API adapter.

The13 original classes remain byte-exact in allen_channels.py. Their currents
are microampere/cm2. Jaxley>=0.5 consumes milliampere/cm2. Physical conductance
parameters remain S/cm2, voltage mV, time ms, calcium concentration mM. No fitted
value, initial state, kinetic equation or stimulus amplitude is rescaled here.
"""
from . import allen_channels as original

class _CurrentUnits:
    current_is_in_mA_per_cm2=True
    def compute_current(self,states,voltages,params):
        return super().compute_current(states,voltages,params)/1000.0

class NaTaT(_CurrentUnits,original.NaTaT):pass
class NaTs2T(_CurrentUnits,original.NaTs2T):pass
class NapEt2(_CurrentUnits,original.NapEt2):pass
class KPst(_CurrentUnits,original.KPst):pass
class KTst(_CurrentUnits,original.KTst):pass
class SKE2(_CurrentUnits,original.SKE2):pass
class SKv3_1(_CurrentUnits,original.SKv3_1):pass
class M(_CurrentUnits,original.M):pass
class CaHVA(_CurrentUnits,original.CaHVA):pass
class CaLVA(_CurrentUnits,original.CaLVA):pass
class H(_CurrentUnits,original.H):pass
class CaNernstReversal(_CurrentUnits,original.CaNernstReversal):pass

class CaPump(_CurrentUnits,original.CaPump):
    def update_states(self,states,dt,voltages,params):
        # Native0.8.2 i_Ca is mA/cm2. The unchanged original divides its incoming
        # microampere value by1000 before the Faraday concentration equation.
        legacy_states=dict(states)
        legacy_states['i_Ca']=states['i_Ca']*1000.0
        return super().update_states(legacy_states,dt,voltages,params)
