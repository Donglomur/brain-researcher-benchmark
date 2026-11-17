"""Prospective invented scalar qualification, independent rational expectations.

Not a full authentic workload or a performance qualification. No protected
kernel, source data, descriptor, certificate or prior result is opened.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import struct

def complete_invented(comparator):
    # The fixture recipe specifies exact integer dB means independently of the
    # tested reduction. Distinct channel/pair/window/frequency/time signatures,
    # varying position support and varying time counts detect axis/reduction
    # mistakes. All 1,458,240 invented words are consumed by calculate().
    raw=bytearray(struct.pack('<d',float('nan'))*1458240)
    expected=[]
    def put(condition,ch,w,f,t,values):
        start=(((((condition*62+ch)*2+w)*7+f)*28+t)*15)
        for i,value in enumerate(values):
            position=(i*5+ch+f+t+condition)%15
            struct.pack_into('<d',raw,(start+position)*8,float(value))
    for pair in range(2):
        for w in range(2):
            for ch in range(62):
                frequencies=[]
                for f in range(7):
                    times=[]
                    for t in range(28):
                        if ((ch+2*w+pair)%19==0 or f==(ch+w)%7 or
                            t>=1+(f*3+ch)%11):
                            continue
                        a=(ch+w+f)%3-1
                        delta=(1+(ch*3+w*2+pair+f+t)%4)*(1 if (ch+w+pair)%2 else -1)
                        b=a+delta
                        put(pair*2,ch,w,f,t,[10*a-10,10*a+10])
                        put(pair*2+1,ch,w,f,t,[10*b] if t%2 else [10*b-20,10*b,10*b+20])
                        power=Fraction(10**delta) if delta>=0 else Fraction(1,10**(-delta))
                        times.append((power-1)/(power+1))
                    if times:
                        frequencies.append(sum(times,Fraction())/len(times))
                expected.append(float(sum(frequencies,Fraction())/len(frequencies)) if frequencies else float('nan'))
    body=comparator.calculate(bytes(raw))
    wanted=struct.pack('<248d',*expected)+bytes(int(math.isnan(x)) for x in expected)
    assert len(body)==2232 and body==wanted
    return True

def check(comparator):
    count=0
    with localcontext() as ctx:
        ctx.prec=100
        ln10=Decimal(10).ln()
        for k in (-10,-3,-1,0,1,3,10):
            actual=comparator.contrast(Fraction(0),Fraction(10*k),ln10)
            power=Fraction(10**k) if k>=0 else Fraction(1,10**(-k))
            expected=(power-1)/(power+1)
            # Prospective engineering error bound only, chosen without authentic
            # results. Rational oracle is independent of Decimal exp/series.
            assert abs(Fraction(actual)-expected)<=Fraction(1,10**90)
            count+=1
        for exponent in (1074,1000,500):
            d=Fraction(1,1<<exponent)
            actual=comparator.contrast(Fraction(0),d,ln10)
            # For x=ln10*d/20, x/(1+x^2) < tanh(x) < x. Bound ln10 by
            # exact coarse rationals2<ln10<3 to test nonzero tiny scale.
            assert d/Fraction(11)<Fraction(actual)<3*d/20
            assert comparator.contrast(d,Fraction(0),ln10)==-actual
            count+=2
        nan=float('nan')
        assert comparator.group([0.,20.]+[nan]*13)==10
        assert comparator.group([0.]+[nan]*14)==0
        assert comparator.group([nan]*15) is None
        assert comparator.contrast(None,Fraction(0),ln10) is None
        count+=4
        for values in ([math.inf]+[0.]*14,[1001.]+[0.]*14,[0.]*14):
            try:comparator.group(values)
            except ValueError:pass
            else:raise AssertionError('domain refusal required')
            count+=1
    assert complete_invented(comparator)
    count+=1
    assert count==21
    return count
