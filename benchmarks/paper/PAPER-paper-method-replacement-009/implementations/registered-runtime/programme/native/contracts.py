"""Trial-specific fixed deployment, with independent evidence remaining external."""
from contextvars import ContextVar
from contextlib import contextmanager
from .io import read,need
from ..selection import OperatorSelection
_CURRENT=ContextVar('trial_original_deployment',default=None)
GATES=('rights','source_versions','complete_cohorts','clock_and_units','historical_splits','fitted_prior_target','native_image','isolation','counters','capacity','target_custody')
class Deployment:
 def __init__(self):raise TypeError('original fixed capture only')
 @classmethod
 def capture(cls,selection,host):
  need(type(selection)is OperatorSelection,'original operator capture');selection.revalidate();body=selection.body
  need(set(body['evidence'])==set(GATES),'all independent external deployment evidence')
  evidence={}
  for name in GATES:
   row=body['evidence'][name];evidence[name]=host.read(row['path'],row['bytes'],row);need(evidence[name],'nonempty selected evidence body')
  # Independent issuer and empirical truth are trusted operator/platform inputs.
  # These reads do not qualify a source packet or manufacture a native receipt.
  obj=object.__new__(cls);obj.selection=selection;obj.evidence=evidence;obj.profile=dict(body['runtime_profile'],qualification=selection.identity,selected_qualification=selection.identity);obj.identity=selection.identity;return obj
 @contextmanager
 def activate(self):
  need(_CURRENT.get()is None,'one original deployment');self.selection.revalidate();token=_CURRENT.set(self)
  try:yield self
  finally:_CURRENT.reset(token)
def require_qualification(selected,expected_selection,operation='participant'):
 owner=_CURRENT.get();need(type(owner)is Deployment and operation in('reference_preparation','participant'),'original Trial deployment scope')
 owner.selection.revalidate();need(selected==expected_selection==owner.identity,'same actual selected deployment');return owner
