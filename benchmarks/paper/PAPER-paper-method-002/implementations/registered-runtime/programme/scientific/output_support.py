"""Fixed known whole scientific support before native allocation/launch.

None denotes a positive dimension supplied by the original qualified identity
contract, not an omitted axis. These checks supplement exact source emit checks;
they do not turn an operator's unissued identity into authentic evidence.
"""
from runtime.strict import require
FIXED={
'J02':{'Jaxley_voltage':(5,10,3,None),'NEURON_voltage':(5,10,3,None),'spike_times':(5,10,2,3),'spike_amplitudes':(5,10,2,3)},
'J04':{'full_state':(8001,3920000),'voltage':(8001,2000),'parameter_gradient':(3200000,),'connectivity':(1000000,6)},
'J05':{'full_state':(None,None),'parameter_gradient':(None,),'selected_12_loss':(1,),'connectivity':(25400000,6)},
'J06':{'physical_parameters':(None,),'untransformed_parameters':(None,),'derivative':(None,),'log_Jacobian':(None,),'bounds':(None,2)},
'J08':{'full_gradient':(None,),'checkpoint_gradient':(None,)},
'J09':{'boundary_state_before':(15360,3,None),'boundary_state_after':(15360,3,None),'gradient_cuts':(15360,3,None),'full_voltage':(15360,147,None)},
'J10':{'full_voltage':(10021,1,None),'parameters':(10021,19),'four_summaries':(10021,4)},
'J12':{'whole_branch_voltage':(3,339,None),'parameters_1390':(3,1390)},
'J13':{'chains_200_transitions_500':(500,200,1390),'log_density':(2500,200),'acceptance':(2500,200),'last_samples':(200,1390)},
'J16':{'full_site_predictions':(15360,147),'observation_mask':(15360,147)},
'J17':{'all_branch_calcium':(2,155,None),'site_voltage':(2,2,None),'site_calcium':(2,2,None)},
'J18':{'experimental_RF':(147,20,15),'model_RF':(147,20,15),'normalized_RF':(147,2,20,15)},
'J21':{'full_state':(13,3,None),'voltage':(13,240000,None),'Lyapunov_norms':(13,240000),'maximal_Lyapunov':(13,)},
'J22':{'test_logits':(1000,2),'trial_labels':(1000,2),'input_weights':(20,),'recurrent_weights':(20,20),'output_weights':(20,2),'voltage_readout':(1000,22,20801)},
'J23':{'positive_trial_readout':(2,None),'negative_trial_readout':(2,None)},
'J24':{'complete_voltage':(4,52,None),'raster':(4,50,None),'readout':(4,2,None)},
'J25':{'full_ion_gate_state':(None,480000),'Hann40ms_smoothed':(None,480000),'normalized_state':(None,480000),'PCA_projection':(480000,3)},
'J26':{'full_logits':(256,10),'hidden_voltage':(256,858,None)},
'J27':{'full_test_logits':(101,10000,10),'image_labels':(10000,)},
'J28':{'initial_parameters':(None,),'trained_parameters':(None,),'reset_parameters':(8,None),'reset_logits':(8,1024,10)},
'J29':{'clean_images':(128,784),'attacked_images':(2,31,128,784),'attacked_logits':(2,31,128,10),'norm_curve':(2,31,5)},
'J30':{'all64_tuning':(2,64,10),'full_response':(2,None,64,None)},
'J31':{'input_weights':(2,50816),'mechanism_parameters':(2,None)},
'J33':{'full_Jacobian':(3,None,None),'Jacobian_sign':(3,None,None)},
'J34':{'input':(2,None),'readout':(2,2,None),'raster':(2,20,None),'full_voltage_both_classes':(2,22,None)},
}
def require_full_support(group,outputs):
    by={p['artifact_id']:p for p in outputs}
    for role,dimensions in FIXED.get(group,{}).items():
        p=by[role];require(p['format']=='jaxley-flat-numeric-v1','whole fixed numeric product: '+role)
        shape=p['shape'];require(len(shape)==len(dimensions),'whole output rank: '+role)
        require(all(want is None or actual==want for actual,want in zip(shape,dimensions)),'whole scientific support: '+role)
        if group=='J13':require(p['dtype']=='float64-le','complete x64 posterior storage; no downcast allowance')
    if group=='J09':
        require(by['full_voltage']['shape'][2]>=8000,'complete200ms retinal trajectory')
        require(len({tuple(by[r]['shape'])for r in ('boundary_state_before','boundary_state_after','gradient_cuts')})==1,'same complete retinal state coordinates')
    if group=='J20':require(all(p['format']=='json'for p in outputs),'three unequal network profiles use complete keyed JSON, not a one-profile array')
    if group=='J11':require(all(p['format']=='json'for p in outputs),'all52 Allen runs and their variable complete histories use JSON')
    if group=='J06':
        size=by['physical_parameters']['shape'][0]
        require(all(by[r]['shape']==[size]for r in ('untransformed_parameters','derivative','log_Jacobian'))and by['bounds']['shape']==[size,2],'same complete transform coordinates')
    if group=='J08':require(by['full_gradient']['shape']==by['checkpoint_gradient']['shape'],'same complete checkpoint gradient coordinates')
    if group=='J25':require(len({tuple(by[r]['shape'])for r in ('full_ion_gate_state','Hann40ms_smoothed','normalized_state')})==1,'same full PCA state/trajectory extent')
    if group=='J33':
        shapes=[by[r]['shape']for r in ('full_Jacobian','Jacobian_sign')]
        require(shapes[0]==shapes[1]and shapes[0][1]==shapes[0][2],'complete square Jacobian coordinate inverse')
