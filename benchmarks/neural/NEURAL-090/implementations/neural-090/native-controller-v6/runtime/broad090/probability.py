"""One admitted probability/mixture/loss convention for TUNE and final scoring.

Pure numerical source; no function in this module is executed in construction.
Training and CAL optimization remain original raw cross-entropy, not this loss.
"""
import math
from programme.contracts import need
from .protocol import EPSILON

def normalize_probability(p):
    need(type(p) in (list,tuple) and len(p)==39,'all39 probability columns')
    need(all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in p),'finite proper probability domain')
    total=math.fsum(p);need(abs(total-1)<=1e-6 and total>0,'declared simplex tolerance before one normalization')
    return tuple(x/total for x in p)

def scored_probability(admitted):
    # The sole transformation. Never clip a second time or silently change epsilon.
    return tuple((1-EPSILON)*x+EPSILON/39 for x in admitted)

def row_loss(admitted,label):
    need(type(label) is int and 0<=label<39,'fixed original class support')
    return -math.log(scored_probability(admitted)[label])

def mean_loss(losses,count):
    need(type(count) is int and count>0 and len(losses)==count,'complete nonempty row support')
    return math.fsum(losses)/count
