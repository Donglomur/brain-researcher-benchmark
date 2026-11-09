"""Durable bounded metadata index; complete states remain in original producer files."""
from pathlib import Path
from core import need, encoded, pin, publish, capture, parse, integer


class Records:
    def __init__(self, root, budget, cap, index_cap, index=None):
        self.root, self.budget, self.cap, self.index_cap = Path(root), budget, integer(cap,1), integer(index_cap,1)
        self.index = {} if index is None else dict(index)
        need(len(encoded(self.index)) <= self.index_cap, 'bounded complete index')
    def __contains__(self, key): return key in self.index
    def __len__(self): return len(self.index)
    def __iter__(self): return iter(self.index)
    def __setitem__(self, key, value):
        need(type(key) is str and len(key) == 64 and all(c in '0123456789abcdef' for c in key)
             and key not in self.index, 'unique exact operation record')
        # This fixed conservative index entry bound precedes insertion. Complete
        # record/JSON working memory has a separately selected host RSS ceiling.
        need((len(self.index)+1)*1024 <= self.index_cap, 'prospective full metadata index allowance')
        raw = encoded(value); need(len(raw) <= self.cap, 'complete record bound, no truncation')
        path = self.root/(key+'.json'); desc = publish(path,raw,self.budget,readonly=True)
        self.index[key] = {'path':str(path),'pin':desc}
    def __getitem__(self, key):
        d = self.index[key]; raw,_ = capture(d['path'],d['pin'],self.cap,self.budget,readonly=True)
        return parse(raw)
    def keys(self): return self.index.keys()
    def values(self):
        for key in self.index: yield self[key]
    def items(self):
        for key in self.index: yield key,self[key]
