"""Source-specific output/telemetry checking after protected capture selection.

Schema validation and same-implementation consistency are not an independent
numerical bank. No observation is invented for a missing physical counter.
"""
import math
import zlib
from .protocol import require, integer, digest, validate_pin
from .identity import identity, job_digest, manifest_digest, profile_digest, bind_profile, plan_digest
from .scientific import request_contract, SOURCE_OPERATIONS
from .summaries import dispatch_summary


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def output_extent(request, pins):
    """Reserve the combined output domain before retaining any output body."""
    require(pins,'empty-output-capture','constructor')
    paths=[];total=0
    for p in pins:
        validate_pin(p);paths.append(p['path']);total+=p['bytes']
    require(len(paths)==len(set(paths)), 'duplicate-output-member','constructor capture')
    require(total<=request['limits']['output_bytes'],'constructor-total-output-cap','complete output set')
    return total


def png_descriptor(body, max_pixels, max_bytes):
    """Validate the complete noninterlaced native PNG, including CRC/zlib extent.

    No rendering or pixel editing occurs. Unsupported interlaced encodings are
    explicit failures rather than claimed full validation from a header alone.
    """
    require(len(body)<=max_bytes and body[:8]==b'\x89PNG\r\n\x1a\n','PNG-signature-or-cap','GUI image')
    offset=8;header=None;compressed=[];ended=False;idat_closed=False;seen_idat=False;metadata={}
    while offset<len(body):
        require(offset+12<=len(body),'PNG-truncated-chunk','GUI image')
        n=int.from_bytes(body[offset:offset+4],'big');kind=body[offset+4:offset+8]
        require(n<=2147483647 and all(65<=c<=90 or 97<=c<=122 for c in kind)
                and 65<=kind[2]<=90,'PNG-chunk-name-or-length','PNG alphabetic names and reserved bit')
        end=offset+12+n;require(end<=len(body),'PNG-truncated-data','GUI image')
        data=body[offset+8:offset+8+n]
        crc=int.from_bytes(body[offset+8+n:end],'big')
        require((zlib.crc32(kind+data)&0xffffffff)==crc,'PNG-CRC','GUI image')
        if header is None:
            require(kind==b'IHDR' and n==13,'PNG-IHDR','GUI image')
            width,height=int.from_bytes(data[:4],'big'),int.from_bytes(data[4:8],'big')
            depth,colour,compression,filtering,interlace=data[8:]
            # The selected GUI export is RGB/RGBA, not indexed/grayscale.
            # Reject unsupported colour models rather than partially validate
            # their palette/transparency and call the image complete.
            allowed={2:{8,16},6:{8,16}}
            require(width>0 and height>0 and width*height<=max_pixels and colour in allowed
                    and depth in allowed[colour] and compression==filtering==interlace==0,
                    'PNG-unsupported-format-or-pixel-cap','native noninterlaced format')
            header={'width':width,'height':height,'bit_depth':depth,'colour_type':colour}
        elif kind==b'IHDR':require(False,'PNG-duplicate-header','GUI image')
        elif kind==b'IDAT':
            require(not idat_closed,'PNG-discontinuous-IDAT','GUI image')
            seen_idat=True;compressed.append(data)
        elif kind==b'IEND':
            require(n==0 and seen_idat and end==len(body),'PNG-invalid-end','GUI image');ended=True
        else:
            # Explicit narrow RGB/RGBA subset. Palettes are unused and rejected,
            # including well-formed optional palettes, rather than half-validated.
            require(kind!=b'PLTE','PNG-palette-not-supported','RGB/RGBA capture contract')
            require(kind in {b'sRGB',b'gAMA',b'pHYs'},'PNG-unsupported-chunk','explicit native subset')
            require(not seen_idat and kind not in metadata,'PNG-metadata-order-or-duplicate','before IDAT, once')
            if kind==b'sRGB':require(n==1 and data[0]<=3,'PNG-sRGB','rendering intent')
            if kind==b'gAMA':require(n==4 and int.from_bytes(data,'big')>0,'PNG-gAMA','positive gamma')
            if kind==b'pHYs':require(n==9 and data[8] in (0,1),'PNG-pHYs','unit specifier')
            metadata[kind]=data
        offset=end
    require(ended and header is not None,'PNG-missing-IEND','GUI image')
    require(not(b'sRGB' in metadata and b'gAMA' in metadata)
            or int.from_bytes(metadata[b'gAMA'],'big')==45455,'PNG-sRGB-gAMA-conflict','colour metadata')
    channels={0:1,2:3,3:1,4:2,6:4}[header['colour_type']]
    stride=(header['width']*channels*header['bit_depth']+7)//8+1
    expected=stride*header['height']
    require(expected<=max_pixels*8+header['height'],'PNG-expanded-cap','GUI image')
    decompressor=zlib.decompressobj();raw=decompressor.decompress(b''.join(compressed),expected+1)
    require(len(raw)==expected and decompressor.eof and not decompressor.unused_data
            and not decompressor.unconsumed_tail,'PNG-zlib-extent','complete image')
    require(all(raw[i] in range(5) for i in range(0,expected,stride)),'PNG-filter-byte','GUI image')
    return header


def _native_undefined(value):
    if isinstance(value,dict):
        if set(value)=={'native_nonfinite'}:
            require(value['native_nonfinite'] in {'nan','positive-infinity','negative-infinity'},
                    'invalid-native-nonfinite-tag','native output')
            return True
        return any(_native_undefined(v) for v in value.values())
    if isinstance(value,list):return any(_native_undefined(v) for v in value)
    return False


def validate_product(request, output, operands, *, allow_invented=False):
    request_contract(request,allow_invented=allow_invented)
    require(output['schema']=='kilosort4_scientific_output_v3'
            and output['request_digest']==digest(request)
            and output['execution_context']==request['execution_context']
            and output['operation']==request['operation']
            and output['support_digest']==request['support_digest']
            and output['numerical_scope']==request['numerical_scope']
            and output['definition_digest']==digest(request['definition'])
            and output['input_pins']=={k:v['pin'] for k,v in request['inputs'].items()},
            'scientific-output-identity','operation/request/source operands')
    require(output['historical_parity'] is False and output['scientific_pass'] is None,
            'output-cannot-claim-qualification','source product')
    op=request['operation'];r=output['result']
    if _native_undefined(r):
        return {'status':'required-unscorable','reason':'Original native nonfinite values retained',
                'independent_bank_validation':False}
    if op not in SOURCE_OPERATIONS:
        expected=dispatch_summary(request,operands,allow_invented=allow_invented)
        require(r==expected,'summary-output-mismatch','complete same-source recomputation')
        if op=='waveform_statistics' and any(x['T2P_seconds'] is None for x in r['result']['units']):
            return {'status':'required-unscorable','reason':'Complete unit retained without defined T2P',
                    'independent_bank_validation':False}
        if op=='runtime_mean_sem' and r['result']['comparison_status']!='comparable-under-selected-boundary':
            return {'status':'required-unscorable','reason':'Noncomparable or unauthenticated runtime measurements',
                    'raw_timings_retained':True,'independent_bank_validation':False}
    elif op=='native_gui_diagnostic_v4_0_2':
        require(r['scene']==request['parameters']['scene']
                and type(r['width']) is int and type(r['height']) is int
                and r['width']>0 and r['height']>0
                and r['width']*r['height']<=request['limits']['max_points']
                and r['source_functions']=='kilosort.gui.sanity_plots'
                and r['original_paper_GUI_event_script_reproduced'] is False,
                'native-GUI-output','source plot only')
        validate_pin(r['image'])
        require(r['image']['path']=='GUI_DIAGNOSTIC.png'
                and r['image']['bytes']<=request['limits']['output_bytes'], 'native-GUI-image','exact output member')
    elif op=='native_ccg_v4_0_2':
        a,b=operands['spike_train_1'],operands['spike_train_2'];h=r['histogram']
        require(len(h)==1001 and all(_finite(x) and x>=0 and x==int(x) for x in h),
                'native-CCG-output-shape','all1001bins')
        require(sum(h)<=len(a)*len(b) and r['spike_counts']==[len(a),len(b)]
                and r['central_bin_restored'] is True,'native-CCG-support','all event pairs')
        require(_finite(r['duration_seconds']) and r['duration_seconds']>=0,
                'native-CCG-duration','finite source span')
        for k in ('Q12_contamination','R12_probability','R00_baseline'):
            require(_finite(r[k]) and r[k]>=0,'native-CCG-number',k)
        require(r['R12_probability']<=1,'native-probability','R12')
        require(type(r['autocorrelation_refractory']) is bool
                and r['autocorrelation_refractory']==(r['Q12_contamination']<.2 and r['R12_probability']<.2)
                and type(r['cross_correlation_refractory']) is bool
                and r['cross_correlation_refractory']==(r['Q12_contamination']<.25 and r['R12_probability']<.05),
                'native-threshold-output','literal source thresholds')
    elif op=='native_bimodality_v4_0_2':
        require(r['input_count']==len(operands['projection']) and r['histogram_edges']==400
                and r['histogram_bins']==399 and _finite(r['score']),
                'native-bimodality-output','literal399bins')
    elif op=='native_split_projection_v4_0_2':
        labels=operands['cluster_labels'];tree=operands['tree'];members=operands['cluster_membership']
        k=request['parameters']['tree_row'];parent=set(members[tree[k][2]])
        n=sum(x in parent for x in labels)
        require(r['projection_count']==len(r['projection'])==n and all(_finite(x) for x in r['projection'])
                and r['tree_row']==k and r['features']==len(operands['features'][0])
                and r['literal_last_feature_replaced'] is True and r['ridge']==.01 and _finite(r['score']),
                'native-regression-output','selected parent support')
    return {'status':'source-output-schema-validated','complete_support':True,
            'independent_bank_validation':False,'historical_parity':False,'scientific_pass':None}


def validate_resource_observation(native, observer, observer_profile, caps):
    """Require selected physical observations; runtime's null counters fail.

    Implementing this validator does not implement or qualify an external host
    observer. Its exact executable and capture/cgroup coverage remain gates.
    """
    require(observer['schema']=='kilosort4_resource_observation_v3'
            and observer['native_attempt_digest']==digest(native)
            and observer['attempt_id']==native['attempt_id']
            and observer['container_name']==native['container_name']
            and observer['observer_profile_digest']==identity('validator-profile',observer_profile),
            'resource-observer-binding','same native attempt')
    require(observer_profile['role']=='telemetry-validator'
            and observer_profile['qualified_native_observer'] is True
            and observer_profile['executable_pin'] and observer_profile['qualification_pin'],
            'observer-not-qualified','no operator promise')
    validate_pin(observer_profile['executable_pin']);validate_pin(observer_profile['qualification_pin'])
    require(observer['coverage']=={'worker':True,'container':True,'descendants':True,
                                   'lifetime_complete':True,'failed_work_included':True},
            'resource-observer-coverage','whole native process graph')
    require(native['failure'] is None and native['exit_code']==0
            and native['termination']['custody_complete'] and not native['termination']['residual_processes'],
            'native-cleanup-not-complete','physical lifecycle')
    mapping={'wall_seconds':'wall_seconds','cpu_seconds':'cpu_seconds','peak_RSS_bytes':'memory_bytes',
             'read_bytes':'read_bytes','write_bytes':'write_bytes','peak_disk_bytes':'disk_bytes',
             'output_bytes':'output_bytes','log_bytes':'log_bytes','peak_processes':'max_processes',
             'peak_gpu_memory_bytes':'gpu_memory_bytes'}
    for measured,cap in mapping.items():
        value=observer['measurements'][measured]
        require(_finite(value) and value>=0 and value<=caps[cap], 'resource-unmeasured-or-over-cap',measured)
        if not measured.endswith('seconds'):integer(value,measured)
    return {'status':'complete-within-caps','physical_observation_digest':digest(observer)}


def selected_product_validation(store, authority, manifest, job):
    """No raw output/issuer/case arguments may choose grading operands.

    Root supplies an immutable post-execution capture binding. The capture is
    qualified separately; it is not inferred from a successful exit status.
    """
    authority.permit(manifest,job)
    b=authority.admission['scientific_product_bindings'][job['id']]
    native=store.json(validate_pin(b['native_receipt_pin']),4*1024*1024)
    request=store.json(validate_pin(b['request_pin']),4*1024*1024)
    output_pins=[b['output_pin']]
    if request['operation']=='native_gui_diagnostic_v4_0_2':output_pins.append(b['GUI_image_pin'])
    output_extent(request,output_pins)
    output=store.json(validate_pin(b['output_pin']),b['output_pin']['bytes'])
    profile=store.json(validate_pin(b['producer_profile_pin']),4*1024*1024)
    descriptor=manifest['producer_profiles'][job['producer_id']]
    bind_profile(manifest,job,profile)
    require(b['producer_profile_pin']==descriptor['profile_pin']
            and native['producer_profile_pin']==descriptor['profile_pin']
            and native['profile_digest']==profile_digest(profile)
            and native['job_digest']==job_digest(job)
            and native['manifest_digest']==manifest_digest(manifest),
            'product-native-binding',job['id'])
    request_mapping=join_request_namespaces(request,b['request_pin'],native,profile)
    require(native['permit']['job_id']==native['job_id']==job['id']
            and native['permit']['job_digest']==native['job_digest']
            and native['permit']['manifest_digest']==native['manifest_digest']
            and native['permit']['plan_digest']==native['plan_digest']==plan_digest(manifest)
            and native['producer_descriptor_digest']==digest(descriptor),
            'product-native-permit-binding',job['id'])
    require(native['permit']['selection_pin']==b['execution_selection_pin'],
            'product-execution-selection',job['id'])
    execution=store.json(validate_pin(b['execution_selection_pin']),1024*1024)
    require(execution['purpose']=='scientific-execution'
            and execution['canonical_id']==manifest['canonical_id']
            and execution['manifest_digest']==manifest_digest(manifest)
            and job['id'] in execution['scoped_job_ids']
            and execution['admission_receipt_pin']==native['permit']['admission_receipt_pin'],
            'product-selection-ancestry',job['id'])
    require(native['status']=='native-exited' and native['failure'] is None
            and native['exit_code']==0 and native['termination']['custody_complete']
            and not native['termination']['residual_processes'],
            'product-native-not-complete',job['id'])
    capture=store.json(validate_pin(b['capture_pin']),1024*1024)
    capture_profile=store.json(validate_pin(b['capture_profile_pin']),1024*1024)
    expected_members={'SCIENTIFIC_OUTPUT.json':b['output_pin']}
    if request['operation']=='native_gui_diagnostic_v4_0_2':
        image_pin=validate_pin(b['GUI_image_pin']);image_meta=output['result']['image']
        require(image_pin['bytes']==image_meta['bytes'] and image_pin['sha256']==image_meta['sha256'],
                'GUI-image-content-binding',job['id'])
        require(image_pin['bytes']<=request['limits']['output_bytes'],'GUI-image-cap',job['id'])
        image_bytes=store.read(image_pin,retain=True)
        header=png_descriptor(image_bytes,request['limits']['max_points'],request['limits']['output_bytes'])
        require(header['width']==output['result']['width']
                and header['height']==output['result']['height'],
                'GUI-PNG-size',job['id'])
        expected_members['GUI_DIAGNOSTIC.png']=image_pin
    require(capture_profile['role']=='protected-complete-output-capture'
            and capture_profile['qualified'] is True
            and capture['issuer_profile_pin']==b['capture_profile_pin']
            and capture['issuer_profile_digest']==identity('validator-profile',capture_profile)
            and capture['native_receipt_pin']==b['native_receipt_pin']
            and capture['request_pin']==b['request_pin']
            and capture['member_pins']==expected_members
            and capture['closed_after_termination'] is True,
            'output-capture-not-qualified',job['id'])
    store.read(validate_pin(capture_profile['executable_pin']))
    store.read(validate_pin(capture_profile['qualification_pin']))
    from .scientific import bind_definition
    bind_definition(store,authority,manifest,job,profile,request)
    operands={}
    require(set(b['operand_pins'])==set(request['inputs']), 'product-operands',job['id'])
    for role,pin in b['operand_pins'].items():
        effective=request['inputs'][role]['pin']
        require(pin['bytes']==effective['bytes'] and pin['sha256']==effective['sha256'],
                'product-operand-content',role)
        operands[role]=store.json(validate_pin(pin),request['limits']['input_bytes'])
    validation=validate_product(request,output,operands)
    return {'job_id':job['id'],'binding_digest':digest(b),'validation':validation,
            'request_namespace_mapping':request_mapping,
            'scientific_pass':None,'not_independent_numerical_parity':True}


def join_request_namespaces(request, archived_pin, native, profile):
    """Bind archive content to the verified /run mount and fixed worker argv."""
    validate_pin(archived_pin)
    mounted=native['effective_mounts'];mount_pin=validate_pin(mounted['request_pin'])
    require(mounted['schema']=='kilosort4_verified_mounts_v2' and mount_pin['path']=='request.json',
            'mounted-request-namespace','fixed /run/request.json')
    run_mounts=[row for row in mounted['mounts'] if row['target']=='/run']
    require(len(run_mounts)==1 and run_mounts[0]['read_only'] is True,'request-run-mount','qualified readonly /run')
    require(archived_pin['bytes']==mount_pin['bytes'] and archived_pin['sha256']==mount_pin['sha256'],
            'archived-request-content-mismatch','namespace mapping cannot change content')
    require(request==mounted['request'] and digest(request)==digest(mounted['request']),
            'archived-request-body-mismatch','loaded archive must equal executed request')
    entry=['python','-I','/opt/k4bench/scientific_worker.py','/run/request.json']
    require(profile['worker_kind']=='scientific' and profile['entrypoint']==entry
            and native['argv'][-5:]==[profile['image'],*entry],
            'request-runtime-entrypoint','fixed scientific worker and selected image')
    return {'archived_pin':archived_pin,'mounted_pin':mount_pin,'container_path':'/run/request.json',
            'request_digest':digest(request),'content_identity_preserved':True}


def qualify_runtime_evidence(store, authority, manifest, job, request):
    """Authenticate each timing against selected native/telemetry receipts.

    This admits raw observations, including differently scoped observations.
    The summary retains incompatible rows and refuses their combined comparison.
    Nothing here installs or substitutes for a qualified physical observer.
    """
    from .pipeline import validate_execution_binding
    from .scientific import timing_boundary_contract
    selected=authority.admission['runtime_timing_bindings'][job['id']]
    ep=validate_pin(selected['evidence_operand_pin']);effective=request['inputs']['runtime_evidence']['pin']
    require(ep['bytes']==effective['bytes'] and ep['sha256']==effective['sha256'],
            'runtime-evidence-operand-binding','same content in mounted and archive namespaces')
    provided=store.json(ep,request['limits']['input_bytes'])
    expected={(m,c) for m in request['support']['method_ids'] for c in request['support']['case_ids']}
    rows=selected['rows'];keys=[(x['method_id'],x['case_id']) for x in rows]
    require(len(keys)==len(set(keys)) and set(keys)==expected,'runtime-evidence-complete-support','every method/case')
    require(len({x['measurement_id'] for x in rows})==len(rows),'runtime-measurement-reuse','distinct observations')
    evidence=[]
    for row in sorted(rows,key=lambda x:(x['method_id'],x['case_id'])):
        nm=store.json(validate_pin(row['native_manifest_pin']),4*1024*1024)
        require(nm['canonical_id']==manifest['canonical_id'],'runtime-native-canonical','selected original graph')
        candidates=[x for x in nm['jobs'] if x['id']==row['job_id']]
        require(len(candidates)==1,'runtime-native-job','exact selected original sort')
        nj=candidates[0]
        require(nj.get('reference',nj.get('method_id'))==row['method_id'] and nj['query_id']==row['case_id'],
                'runtime-native-method-case','no cross-case or cross-method substitution')
        binding=row['execution_binding'];validate_execution_binding(store,nm,nj,binding)
        native=store.json(validate_pin(binding['native_receipt_pin']),4*1024*1024)
        observer_profile=store.json(validate_pin(row['observer_profile_pin']),1024*1024)
        require(row['observer_profile_pin']==binding['telemetry-validator_profile_pin'],
                'runtime-observer-issuer','selected validated native telemetry issuer')
        for key in ('executable_pin','qualification_pin'):store.read(validate_pin(observer_profile[key]))
        observation=store.json(validate_pin(row['observation_pin']),4*1024*1024)
        telemetry=store.json(validate_pin(binding['telemetry_receipt_pin']),4*1024*1024)
        require(telemetry['physical_observation_pin']==row['observation_pin'],
                'runtime-observation-selection','same underlying native observation')
        validate_resource_observation(native,observation,observer_profile,nj['resources'])
        timing=observation['timing_measurement'];boundary=timing_boundary_contract(timing['boundary'])
        require(digest(boundary) in observer_profile['qualified_timing_boundary_digests'],
                'runtime-observer-boundary-unqualified','explicit observer support')
        require(timing['measurement_id']==row['measurement_id']
                and timing['start']['event']==boundary['start_event'] and timing['end']['event']==boundary['end_event'],
                'runtime-boundary-event-join','selected event definitions')
        begin,end=timing['start']['monotonic_seconds'],timing['end']['monotonic_seconds']
        elapsed=timing['elapsed_seconds']
        require(_finite(begin) and _finite(end) and _finite(elapsed) and end>=begin
                and elapsed==end-begin and elapsed<=observation['measurements']['wall_seconds'],
                'runtime-elapsed-observation','exact observed interval, no guessed normalization')
        evidence.append({'method_id':row['method_id'],'case_id':row['case_id'],
                         'measurement_id':row['measurement_id'],'status':'complete','wall_seconds':elapsed,
                         'runtime_boundary':boundary,'telemetry_receipt_digest':row['observation_pin']['sha256'],
                         'native_receipt_pin':binding['native_receipt_pin'],
                         'observation_pin':row['observation_pin'],'observer_profile_pin':row['observer_profile_pin'],
                         'selection_binding_digest':digest(row)})
    require(provided==evidence,'runtime-evidence-body-mismatch','fully authenticated timing operands')
    return evidence
