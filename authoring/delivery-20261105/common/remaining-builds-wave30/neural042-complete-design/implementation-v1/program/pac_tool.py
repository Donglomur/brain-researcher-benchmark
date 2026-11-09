"""Optional low-level T1 numerical primitives; no matching/report/reference API.
Invocation counters are candidate-influenced; complete worker CPU/RAM is external.
"""
import math
from core import need,integer,finite
class Tool:
    def __init__(self,budget,elements):self.budget=budget;self.cap=integer(elements,1);self.used=0
    def _np(self,shape):
        n=math.prod(shape);need(self.used+n<=self.cap,'tool element reservation');self.used+=n;self.budget.tick()
        import numpy as np
        need(np.__version__=='2.2.6','qualified tool NumPy');return np
    def kernel(self,low,high):
        low,high=finite(low),finite(high)
        allowed={(3.,5.),(5.,7.)}|{(float(h-l),float(h+l))for l in(4,6)for h in range(70,141,5)}
        need((low,high)in allowed,'only the declared two theta and30 pair-specific gamma passbands')
        df=min(max(low*.25,2.),low,200-high);order=2*math.ceil(3.3*400/df/2);np=self._np((8*(order+1),))
        t=np.arange(order+1,dtype=float)-order/2;window=np.hamming(order+1)
        def lp(f):
            h=2*f/400*np.sinc(2*f/400*t)*window;total=float(h.sum());need(math.isfinite(total)and total!=0 and np.isfinite(h).all(),'finite nonzero lowpass normalization');return h/total
        result=lp(high+df/2)-lp(low-df/2);need(np.isfinite(result).all(),'finite transition-adjusted filter');self.budget.tick();return result
    def analytic(self,values,low,high):
        shape=getattr(values,'shape',None);need(type(shape)is tuple and len(shape)==2 and shape[1]==1000,'explicit trial/time array')
        np=self._np((math.prod(shape)*12,));need(type(values)is np.ndarray and values.dtype==np.float64 and np.isfinite(values).all(),'finite exact numerical input')
        h=self.kernel(low,high);pad=(len(h)-1)//2;self._np((shape[0]*(1000+2*pad)*2,))
        from scipy import __version__ as version
        from scipy.signal import convolve,hilbert
        need(version=='1.15.3','qualified tool SciPy')
        result=np.empty(shape,dtype=np.complex128)
        for i,row in enumerate(values):
            self.budget.tick();result[i]=hilbert(convolve(np.pad(row,(pad,pad),mode='edge'),h,mode='valid',method='direct'));self.budget.tick()
        return result
    def histogram(self,phase,amplitude):
        shape=getattr(phase,'shape',None);need(type(shape)is tuple and shape==getattr(amplitude,'shape',None),'same explicit arrays')
        np=self._np((math.prod(shape)*8,));need(type(phase)is np.ndarray and type(amplitude)is np.ndarray and phase.dtype==np.float64 and amplitude.dtype==np.float64 and np.isfinite(phase).all()and np.isfinite(amplitude).all()and (amplitude>=0).all(),'finite phase/amplitude')
        need((phase>=-np.pi).all()and (phase<=np.pi).all(),'analytic phase domain')
        bins=np.floor(((phase.ravel()+np.pi)%(2*np.pi))/(2*np.pi)*18).astype(np.int64)
        need((bins>=0).all()and (bins<18).all(),'numeric boundary failure, not biological null')
        counts=np.bincount(bins,minlength=18);sums=np.bincount(bins,weights=amplitude.ravel(),minlength=18);self.budget.tick();return counts,sums
    def mi(self,phase,amplitude):
        counts,sums=self.histogram(phase,amplitude);np=self._np((128,))
        if (counts==0).any():return None
        means=sums/counts;total=float(means.sum())
        if not math.isfinite(total)or total<=0:return None
        p=means/total;v=p[p>0];answer=float(max(0.,(np.sum(v*np.log(v))+np.log(18))/np.log(18)));self.budget.tick();return answer
