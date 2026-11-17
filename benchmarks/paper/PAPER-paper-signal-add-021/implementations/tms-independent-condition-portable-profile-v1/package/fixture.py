"""Invented full geometry and an independent symbolic Fraction oracle.

No authentic source, reference, interval or category file is read. Numeric
fixture bytes are generated only by a separately selected engineering entry.
"""
from fractions import Fraction
import math
import os
from pathlib import Path
import struct
from common import need,write,encode,pin
from source_projection import SHAPE,BYTES,CONDITIONS,FREQUENCIES,TIMES

PROFILE='tms_invented_original_operand_fixture_v1'
CODE=b'# Invented B-only assistance; not original paper code.\n# Contrast is (pout_power-pin_power)/(pin_power+pout_power).\n'

def group_defined(condition,channel,window,frequency,time):
    pair=condition//2
    if channel==0 or (channel==2 and window==1) or (channel==3 and pair==1):
        return False
    if channel%11==1 and frequency==0:
        return False
    valid_times=1+(channel+3*window+2*frequency)%28
    if condition%2==0 and time>=valid_times:
        return False
    if condition%2==1 and (pair+channel+window+frequency+time)%17==0:
        return False
    return True

def base_db(condition,channel,window,frequency,time):
    pin_db=10*((channel+window+frequency)%3-1)
    change=10*((condition//2+channel+window+frequency+time)%5-2)
    return pin_db+(change if condition%2 else 0)

def raw_group(condition,channel,window,frequency,time):
    if not group_defined(condition,channel,window,frequency,time):
        return [float('nan')]*15
    pair_count=1+(condition+channel+window+frequency+time)%7
    include_middle=(condition+frequency+time)%2==0
    base=base_db(condition,channel,window,frequency,time)
    return [float(base+10*(1+condition%2)*(position-7))
            if position<pair_count or position>=15-pair_count or (position==7 and include_middle)
            else float('nan') for position in range(15)]

def symbolic_targets():
    """Derive group means analytically from symmetric finite raw positions.

    This does not decode generated arrays, run the candidate or invoke the
    interval kernel. Position offsets cancel exactly; unequal supports retain
    the declared base mean. Powers have integer exponents and are rational.
    """
    out=[]
    counts=[]
    for pair in range(2):
        for window in range(2):
            for channel in range(62):
                frequency_means=[]
                time_counts=[]
                for frequency in range(7):
                    contrasts=[]
                    for time in range(28):
                        a,b=2*pair,2*pair+1
                        if not(group_defined(a,channel,window,frequency,time) and
                               group_defined(b,channel,window,frequency,time)):
                            continue
                        k=(pair+channel+window+frequency+time)%5-2
                        ratio=Fraction(10**k,1) if k>=0 else Fraction(1,10**(-k))
                        contrasts.append((ratio-1)/(ratio+1))
                    time_counts.append(len(contrasts))
                    if contrasts:
                        frequency_means.append(sum(contrasts,Fraction())/len(contrasts))
                value=(sum(frequency_means,Fraction())/len(frequency_means)
                       if frequency_means else None)
                out.append(value);counts.append((tuple(time_counts),len(frequency_means)))
    need(len(out)==248,'full_symbolic_fixture_targets')
    return tuple(out),tuple(counts)

def discriminate_fixture(targets):
    # Unequal frequency support must make flattening detectably wrong on this
    # complete recipe, not merely on a separate hand-picked scalar example.
    flatten_differences=0
    for pair in range(2):
        for window in range(2):
            for channel in range(62):
                points=[]
                for frequency in range(7):
                    for time in range(28):
                        if not(group_defined(2*pair,channel,window,frequency,time) and
                               group_defined(2*pair+1,channel,window,frequency,time)):continue
                        k=(pair+channel+window+frequency+time)%5-2
                        z=Fraction(10**k,1) if k>=0 else Fraction(1,10**(-k))
                        points.append((z-1)/(z+1))
                flat=sum(points,Fraction())/len(points) if points else None
                target=targets[(pair*2+window)*62+channel]
                flatten_differences+=int(flat!=target)
    need(flatten_differences>0,'fixture_distinguishes_nested_from_flattened')
    maps=[targets[i*62:(i+1)*62] for i in range(4)]
    need(len(set(maps))==4 and any(row!=tuple(reversed(row)) for row in maps),'fixture_distinguishes_map_and_channel_order')
    # Predeclared NT/channel4/window0/frequency1/time0 has group means10,-10.
    # Its common finite positions are0..5 and9..14, with unequal pin/pout
    # symmetric offsets. Taking the contrast before position means is wrong.
    wrong=[]
    for position in (*range(6),*range(9,15)):
        k=-2+(position-7)
        z=Fraction(10**k,1) if k>=0 else Fraction(1,10**(-k))
        wrong.append((z-1)/(z+1))
    need(sum(wrong,Fraction())/len(wrong)!=Fraction(-99,101),
         'fixture_distinguishes_mean_before_nonlinearity')
    return {'nested_weighting_distinguished':True,'map_and_channel_order_distinguished':True,
            'mean_before_nonlinearity_distinguished':True}

def build_fixture(output, *, budget, modules, source_lock_sha256, runtime_sha256):
    root=Path(output);root.mkdir(mode=0o700)
    payload=bytearray(BYTES);at=0
    for condition in range(4):
        for channel in range(62):
            for window in range(2):
                for frequency in range(7):
                    for time in range(28):
                        budget.check()
                        group=raw_group(condition,channel,window,frequency,time)
                        struct.pack_into('<15d',payload,at,*group);at+=120
    need(at==BYTES,'full_fixture_input_extent')
    raw=bytes(payload)
    input_entry=write(root/'values.f64',raw,budget)
    manifest={'schema':'tms_original_input_projection_v1','profile':PROFILE,
              'dtype':'little-endian-binary64','shape':list(SHAPE),
              'axis_order':['condition','channel','window','frequency','time','stored_position'],
              'conditions':list(CONDITIONS),'labels':list(modules['certificate'].LABELS),
              'source_frequency_indices':list(FREQUENCIES),
              'source_time_indices':[list(x) for x in TIMES],
              'frequency_coordinates':list(range(7)),'time_coordinates':[list(range(28)),list(range(28))],
              'stored_positions':list(range(15)),'physical_person_mapping_claimed':False,
              'original_source':None,'values':pin(raw),
              'contains_reference_or_derived_target_fields':False}
    manifest_entry=write(root/'INPUT.json',encode(manifest),budget)
    targets,counts=symbolic_targets()
    discrimination=discriminate_fixture(targets)
    kernel=modules['kernel'];cert=modules['certificate']
    windows=[]
    for target,(tc,fc) in zip(targets,counts):
        if target is None:
            interval=None
        else:
            scaled=target*kernel.D
            lo=scaled.numerator//scaled.denominator
            hi=-((-scaled.numerator)//scaled.denominator)
            interval=kernel.Interval(lo,hi)
        windows.append(kernel.Window(interval,tc,fc))
    context=cert.FixtureContext(pin(raw)['sha256'],source_lock_sha256,runtime_sha256,'p16-invented-engineering-01')
    reference=cert.pack_fixture_reference(windows,context)
    os.chmod(root,0o500)
    # Keep target certificate outside the candidate input directory.
    return {'input_manifest':manifest_entry,'input_values':input_entry,'reference':reference,
            'reference_pin':cert.pin(reference),'context':context,'targets':targets,
            'standin_code':CODE,'authentic_source':False,'discrimination':discrimination}

