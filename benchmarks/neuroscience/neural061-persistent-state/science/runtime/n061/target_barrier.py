"""Complete captured collection precedes the separately owned late target read."""
from dataclasses import dataclass
from .contracts import need
from .production import Production

@dataclass(frozen=True)
class TargetAccess:
    production:Production
    seal:tuple
    support:object
    observation:object
    host:object
    def validate(self):
        self.production.validate()
        need(self.production.collection.validate_seal() is self.seal,'same complete collection through target capture')
        need(self.support is self.production.support,'one actual support producer')
        need(self.observation.production is self.production,'original independently closed production parent')
        return self
    def capture(self,owner):
        self.validate()
        # The original observer/target issuer is still unavailable; this named
        # host operation is not implemented by a supplied target dictionary.
        return self.host.capture_targets(self.observation,owner)

def admit(production,late_host,owner):
    need(type(production) is Production,'actual selected Production, not a status/hash')
    production.validate();production.catalogue.policy.require_selected()
    # All categorical completeness checks happen before invoking the issuer.
    seal=production.collection.validate_seal();support=production.support.validate()
    observation=late_host.require_closed_production(production,owner)
    return TargetAccess(production,seal,support,observation,late_host).validate()
