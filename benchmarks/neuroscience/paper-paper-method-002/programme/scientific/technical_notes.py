"""Final actual captured-product joins; unavailable independent tests stay explicit."""
from .technical_support.contracts import require,complete,emit

def contour_support(rows):
    by=complete(rows,tuple(range(147)),'site');summary=[]
    for site in range(147):
        row=by[site];require(row['coordinate_unit']=='micrometre','retinal contour units')
        require(row['level']in(.4,.5,.6),'explicit retinal contour profile');counts={}
        for kind in('experimental','model'):
            paths=row[kind];require(type(paths)is list,'complete JSON contour paths')
            for path in paths:
                require(type(path)is list and path,'nonempty observed contour path')
                for point in path:
                    require(type(point)is list and len(point)==2 and all(type(x)in(int,float)for x in point),'complete coordinate pairs')
            counts[kind]={'paths':len(paths),'points':sum(len(path)for path in paths)}
        summary.append({'site':site,'field':row['field'],'level':row['level'],**counts})
    return summary

def qr_support(record,shape,dt):
    require(shape==(13,240000)and dt==.025,'complete gain-by-time QR support')
    require(record['profile']in('source_two_2s_transients_per_ms','paper_single4s_per_step'),'explicit Lyapunov profile')
    rows=record['runs'];require(type(rows)is list and len(rows)==13,'complete13 gain records')
    units='per_ms'if record['profile']=='source_two_2s_transients_per_ms'else'per_solver_step'
    for i,row in enumerate(rows):
        require(row['gain']==i*.00025 and row['units']==units,'gain order and original source units')
        require(row['accumulation_steps']==row['renormalization_steps']==240000 and row['transient_steps']==160000,'complete original QR accumulation')
    return rows,units

def hmc_support(density_shape,acceptance_shape):
    require(density_shape==acceptance_shape==(2500,200),'complete transition-by-chain prior+posterior support')
    return {'chains':200,'prior_transitions':2000,'posterior_transitions':500,'acceptance_kind':'probability'}

def notes(ctx):
    import numpy as np,jax.numpy as jnp
    rows=complete(ctx.read_json('supplementary_note_inputs'),tuple(range(1,9)),'note');result=[]
    selected=ctx.config['selected_upstream_jobs'];require(type(selected)is list and selected,'actual original parent jobs')
    for note in range(1,9):
        row=rows[note];require(row['source_anchors'],'complete note source map')
        require(row['upstream_jobs']and set(row['upstream_jobs'])<=set(selected),'actual same-condition parent provenance')
        checks={};unavailable=[]
        if note==1:
            source=ctx.read_json('note1_source_map');require(source['definitions'],'actual architecture definitions')
            checks['source_definitions']=len(source['definitions']);unavailable=['independent historical toolbox equivalence']
        elif note==2:
            a=np.asarray(ctx.read_array('note2_jaxley_voltage'));b=np.asarray(ctx.read_array('note2_neuron_voltage'));clocks=ctx.read_json('note2_clock')
            require(a.shape[:3]==b.shape[:3]==(5,10,3),'complete five-morphology ten-amplitude three-site support')
            same=a.shape==b.shape and len(clocks)==5 and all(x['jaxley_ms']==x['neuron_ms']for r in clocks for x in r['amplitudes'])
            checks={'jaxley_shape':list(a.shape),'neuron_shape':list(b.shape),'same_clock':same}
            if same:checks['solver']={'max_absolute':float(np.max(np.abs(a-b))),'mean_absolute':float(np.mean(np.abs(a-b))),'values_compared':int(a.size)}
            else:unavailable.append('clock-aligned solver comparison; incompatible literal terminal clocks retained without cropping')
            unavailable.extend(['independent two/four-compartment comparator producer','independent unsplit/split300 comparator producer','independent leapfrog/0.001mV derivative comparator producer'])
        elif note==3:
            from scipy.special import expit
            p=np.asarray(ctx.read_array('note3_physical'));z=np.asarray(ctx.read_array('note3_untransformed'));bounds=np.asarray(ctx.read_array('note3_bounds'))
            require(p.shape==z.shape and bounds.shape==p.shape+(2,),'complete physical/unconstrained coordinate join')
            reconstructed=bounds[:,0]+(bounds[:,1]-bounds[:,0])*expit(z)
            checks['transform_roundtrip']=float(np.max(np.abs(p-reconstructed)))
            for label,a,b in(('checkpoint','note3_full_gradient','note3_checkpoint_gradient'),('boundary_continuity','note3_boundary_before','note3_boundary_after')):
                x=np.asarray(ctx.read_array(a));y=np.asarray(ctx.read_array(b));require(x.shape==y.shape,'complete actual method coordinates');checks[label]=float(np.max(np.abs(x-y)))
            cuts=np.asarray(ctx.read_array('note3_gradient_cuts'));require(cuts.ndim==3 and cuts.shape[:2]==(15360,3),'all retinal gradient cuts')
            checks['gradient_cut_nonzero_count']=int(np.count_nonzero(cuts));checks['actual_optimizer_updates']=ctx.read_json('note3_optimizer_updates')
        elif note==4:
            from .technical_support.allen_loss import soft_dtw_distance,window_reduce
            family=ctx.read_json('note4_allen_voltage');require(len(family)==52,'all52 actual Allen captures');values=[]
            require(ctx.config['time_penalty']in('source_normalized_index','paper_unscaled_index'),'explicit time penalty')
            for run in family:
                target=jnp.asarray(run['fit_target']);candidates=run['fit_voltage']
                require(candidates and len(run['fit_clock_ms'])==target.size,'complete Allen target/clock')
                b=window_reduce(target,jnp.max,stride=30,window_size=50);lo=jnp.min(b);hi=jnp.max(b)
                require(bool(hi>lo),'nonflat observed scale');b=(b-lo)/(hi-lo)
                cost=lambda x,y:jnp.abs(x-y)
                penalty=lambda x,y:jnp.abs(x-y)/(b.shape[0]if ctx.config['time_penalty']=='source_normalized_index'else 1.)
                bb=soft_dtw_distance(b,b,gamma=.1,cost_fn=cost,penalty_fn=penalty);all_candidates=[]
                for trace in candidates:
                    ctx.checkpoint();a=jnp.asarray(trace);require(a.shape==target.shape,'complete original candidate fit trace')
                    a=(window_reduce(a,jnp.max,stride=30,window_size=50)-lo)/(hi-lo)
                    aa=soft_dtw_distance(a,a,gamma=.1,cost_fn=cost,penalty_fn=penalty);ab=soft_dtw_distance(a,b,gamma=.1,cost_fn=cost,penalty_fn=penalty)
                    all_candidates.append({'soft_DTW_a_b':float(ab),'self_a':float(aa),'self_b':float(bb),'divergence_scaled':float((ab-.5*aa-.5*bb)/.05)})
                values.append({**{k:run[k]for k in('specimen','budget','algorithm','seed')},'candidates':all_candidates})
            checks={'all_runs':values,'window':50,'stride':30,'gamma':.1,'scale':.05}
        elif note==5:
            density=np.asarray(ctx.read_array('note5_log_density'));acceptance=np.asarray(ctx.read_array('note5_acceptance'))
            checks=hmc_support(density.shape,acceptance.shape)
            require(np.all((acceptance>=0)&(acceptance<=1)),'actual HMC acceptance probabilities, not indicators')
            checks.update(prior_mean_acceptance_per_chain=np.mean(acceptance[:2000],axis=0).tolist(),posterior_mean_acceptance_per_chain=np.mean(acceptance[2000:],axis=0).tolist(),
                density_range=[float(np.min(density)),float(np.max(density))],mixing_calibration=ctx.read_json('note5_mixing'))
            unavailable=['independent posterior calibration beyond recorded diagnostics']
        elif note==6:
            checks={'complete_contours':contour_support(ctx.read_json('note6_contours')),'ASD_evidence_trajectory':ctx.read_json('note6_evidence')}
            unavailable=['independent original retinal raw preprocessing parity']
        elif note==7:
            norms=np.asarray(ctx.read_array('note7_norms'));declared=np.asarray(ctx.read_array('note7_maximal'))
            qr,units=qr_support(ctx.read_json('note7_counts'),norms.shape,.025)
            require(np.all(norms>0)and declared.shape==(13,),'positive complete QR norms and all13 gains')
            logs=np.sum(np.log(norms),axis=1);duration=np.asarray([r['accumulation_steps']*.025 for r in qr]);rate_ms=logs/duration
            expected=rate_ms if units=='per_ms'else logs/np.asarray([r['accumulation_steps']for r in qr])
            checks={'recomputed_per_ms':rate_ms.tolist(),'recomputed_per_second':(rate_ms*1000).tolist(),'declared_units':units,'complete_duration_ms_per_gain':duration.tolist(),'max_absolute_declared_difference':float(np.max(np.abs(expected-declared)))}
        else:
            conflicts=ctx.read_json(row['source_conflicts']);require(conflicts,'full named conflict ledger');checks={'source_conflicts':conflicts,'resolved_by_this_producer':False}
        result.append({'note':note,'computed_checks':checks,'unavailable_independent_tests':unavailable,'native_parity_qualified':False})
    emit(ctx,'eight_notes_source_map',[{'note':n,'source_anchors':rows[n]['source_anchors'],'upstream_jobs':rows[n]['upstream_jobs']}for n in range(1,9)])
    emit(ctx,'native_method_tests',result)
