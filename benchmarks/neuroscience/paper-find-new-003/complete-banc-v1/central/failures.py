"""Primary and independent secondary observations survive failed publication."""
class FailureEnvelope(Exception):
    def __init__(self,primary,where='operation'):
        if isinstance(primary,FailureEnvelope):
            self.primary=dict(primary.primary);self.secondary=list(primary.secondary);self.evidence=dict(primary.evidence)
        else:
            self.primary=observation(primary,where);self.secondary=[];self.evidence={}
        super().__init__(self.primary['type']+': '+self.primary['message'])
    def add(self,error,where):
        if isinstance(error,FailureEnvelope):
            self.secondary.append({**error.primary,'where':where})
            self.secondary.extend(error.secondary)
        else:self.secondary.append(observation(error,where))
        return self
    def attach(self,name,value):self.evidence[name]=value;return self
    def document(self):return {'primary':self.primary,'secondary':self.secondary,'evidence':self.evidence,'successful_closure':False}

def observation(error,where):
    return {'where':where,'type':type(error).__name__,'message':str(error)[:2000]}

def combine(primary,error,where):
    if primary is None:return FailureEnvelope(error,where)
    return primary.add(error,where)
