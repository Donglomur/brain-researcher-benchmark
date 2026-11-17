function native_worker(request_path, output_path)
% ADDITIVE SOURCE PROPOSAL ONLY. No authority is created by this MATLAB file.
% The isolated Python worker verifies the pinned-image public-key signature,
% complete43 release, exact source/executable/instrumentation identities and
% inherited deadline BEFORE MATLAB is invoked. External custody remains required.
request = jsondecode(fileread(request_path));
assert(isstruct(request) && isequal(request.future_execution_authorized,true), ...
    'paper020:authority','Trusted signed worker admission required');
assert(numel(request.selection)==3 && all(request.selection==fix(request.selection)) ...
    && request.selection(1)>=1 && request.selection(1)<=14 ...
    && all(request.selection(2:3)>=1) && all(request.selection(2:3)<=2), ...
    'paper020:selection','One original configuration/method/mode required');
[~,~,native_endian]=computer;
assert(isunix && strcmp(native_endian,'L'),'paper020:endian','Reviewed little-endian native image required');
% JSON structs preserve fourteen case boundaries even when every vector has
% equal length; no jsondecode matrix-flattening ambiguity is allowed.
expected_times = cell(14,1); expected_cell_ids = cell(14,1);
assert(numel(request.expected_times)==14 && numel(request.expected_cell_ids)==14, ...
    'paper020:fullRoster','Complete14 admitted metadata required');
for c=1:14
    expected_times{c}=request.expected_times(c).values(:);
    ids=request.expected_cell_ids(c).values;
    if ischar(ids); ids={ids}; elseif isstring(ids); ids=cellstr(ids); end
    assert(iscell(ids) && ~isempty(ids),'paper020:cellIDs','Explicit opaque cell IDs required');
    expected_cell_ids{c}=ids(:);
end
request.expected_times=expected_times;
request.expected_cell_ids=expected_cell_ids;
global paper020_trace paper020_trace_rows
paper020_trace={}; paper020_trace_rows=[];
% This reviewed derivative retains the frozen source's source-pin checks,
% original helpers/driver arithmetic and errors, but selects one of56 phases.
capture=native_capture(request);
[output_dir,~,~]=fileparts(output_path);
% Preserve failed native capture and all original native workspace/transcript
% before converting; this protected companion is never a prediction input.
save(fullfile(output_dir,'capture_private.mat'),'capture','paper020_trace','-v7');
selection=request.selection;
job=capture.jobs{selection(1),selection(2),selection(3)};
assert(isstruct(job) && strcmp(job.status,'captured_not_qualified'), ...
    'paper020:nativeFailure','Original native phase failed; no success-fill or portable replacement');
assert(nnz(~cellfun(@isempty,capture.jobs))==1,'paper020:workload','Exactly one original literal phase must execute');
w=job.workspace;
ncell=numel(request.expected_cell_ids{selection(1)});
nrow=size(w.params,1); ndim=size(w.params,2);
assert(ndim==20 && size(w.paper020_raw_params,1)==nrow && size(w.paper020_raw_params,2)==20, ...
    'paper020:features','Complete raw20 feature basis required');
t=w.t(:); nt=numel(t);
if strcmp(job.mode,'static')
    bins={find(t>50 & t<300)};
    averaged=reshape(w.resp_raw,[nrow,ncell,1]);
    raw_psth=w.psth; % original static driver already performed cat(3,psth{:})
else
    centers=find(t>0 & t<500);
    width=round(50/(t(2)-t(1))); half=(width-1)/2;
    assert(width>=1 && mod(width,2)==1,'paper020:window','Original odd width required');
    bins=cell(1,numel(centers));
    for k=1:numel(centers); bins{k}=(centers(k)-half):(centers(k)+half); end
    averaged=w.sw; raw_psth=cat(3,w.psth{:});
end
nw=numel(bins);
assert(nw>0 && all(cellfun(@(x) ~isempty(x) && all(x>=1 & x<=nt),bins)), ...
    'paper020:window','Every original complete window required');
assert(~(strcmp(job.mode,'time_course') && ncell==1 && nw>1), ...
    'paper020:singleton','Literal default-dimension summaries do not fit V2; no fabricated replacement');
assert(numel(averaged)==nrow*ncell*nw,'paper020:response','Complete native averaged responses required');
counts=zeros(nrow,ncell,nw,'int64');
for k=1:nw
    counts(:,:,k)=reshape(int64(sum(isnan(raw_psth(:,bins{k},:)),2)),[nrow,ncell]);
end
is_set2=strcmp(w.stim_name,'thousand_monkey');
if is_set2; nrepeat=100; else; nrepeat=1; end
fam_cw=reshape(w.cs_fam,[ncell,nw]);
if strcmp(job.mode,'static') && is_set2
    ctrl_cwr=reshape(w.cs_unfam.',[ncell,nw,nrepeat]);
else
    ctrl_cwr=reshape(w.cs_unfam,[ncell,nw,nrepeat]);
end
payload=zeros(0,1,'uint8'); descriptors={};
emit('raw_features',double(w.paper020_raw_params),[nrow,20],'<f8');
emit('times',double(t),nt,'<f8');
emit('feature_values',double(w.params),[nrow,20],'<f8');
% These statistics are additive native diagnostic capture of the full matrix;
% the normalized source params above come from the UNCHANGED load_data line.
emit('feature_means',mean(w.paper020_raw_params),20,'<f8');
emit('feature_rms',sqrt(mean(w.paper020_raw_params.^2)),20,'<f8');
emit('feature_sd_population',std(w.paper020_raw_params,1),20,'<f8');
emit('feature_sd_sample',std(w.paper020_raw_params,0),20,'<f8');
emit('averaged_responses',double(averaged),[nrow,ncell,nw],'<f8');
emit('response_bin_nan_counts',counts,[nrow,ncell,nw],'<i8');
emit('familiar_cosines',permute(reshape(fam_cw,[ncell,nw,1]),[2,3,1]),[nw,1,ncell],'<f8');
emit('control_cosines',permute(ctrl_cwr,[2,3,1]),[nw,nrepeat,ncell],'<f8');
ngroup=numel(paper020_trace)/ncell;
expected_groups=(2+2*nrepeat)*nw;
if ~is_set2; expected_groups=3*nw; end
assert(ngroup==fix(ngroup) && ngroup==expected_groups,'paper020:trace','Complete original helper/cell trace required');
for g=1:ngroup
    traces=paper020_trace((g-1)*ncell+(1:ncell));
    rows=traces{1}.rows(:); nr=numel(rows);
    keep=false(nr,ncell); coefficients=zeros(20,ncell);
    nb=20+(selection(2)==2); full_b=zeros(nb,ncell);
    ranks=zeros(ncell,1,'int64'); finite_inputs=false(2,ncell);
    for c=1:ncell
        tr=traces{c};
        assert(isequal(tr.rows(:),rows) && numel(tr.keep)==nr && numel(tr.coefficients)==20 ...
            && numel(tr.full_b)==nb,'paper020:trace','Exact source rows/original b trace required');
        keep(:,c)=tr.keep(:); coefficients(:,c)=tr.coefficients(:); full_b(:,c)=tr.full_b(:);
        ranks(c)=int64(tr.diagnostic_rank);
        finite_inputs(:,c)=[tr.finite_response;tr.finite_features];
    end
    prefix=sprintf('trace/%d/',g-1);
    emit([prefix 'rows'],int64(rows),nr,'<i8');
    emit([prefix 'keep'],keep,[nr,ncell],'|b1');
    emit([prefix 'coefficients'],coefficients,[20,ncell],'<f8');
    emit([prefix 'full_b'],full_b,[nb,ncell],'<f8');
    emit([prefix 'diagnostic_rank'],ranks,ncell,'<i8');
    emit([prefix 'finite_inputs'],finite_inputs,[2,ncell],'|b1');
end
% The original time summaries are captured by the unchanged frozen collector.
% Static summaries are explicit additional diagnostics using those same native
% nanmean/std formulas; they are not claimed to have been emitted by the driver.
ctrl_per_cell=nanmean(ctrl_cwr,3);
fam_subset_count=int64(reshape(~isnan(fam_cw),[ncell,nw]));
ctrl_subset_count=int64(sum(~isnan(ctrl_cwr),3));
if strcmp(job.mode,'time_course')
    fam_mean=w.capture_familiar_mean; ctrl_mean=w.capture_control_mean;
    fam_sem=w.capture_familiar_sem; ctrl_sem=w.capture_control_sem;
    fam_count=w.capture_familiar_count; ctrl_count=w.capture_control_count;
    assert(isequaln(ctrl_per_cell,w.capture_control_per_cell),'paper020:summary','Native control summary changed');
else
    fam_mean=nanmean(fam_cw); ctrl_mean=nanmean(ctrl_per_cell);
    fam_count=sum(~isnan(fam_cw)); ctrl_count=sum(~isnan(ctrl_per_cell));
    fam_sem=std(fam_cw,'omitnan')./sqrt(fam_count);
    ctrl_sem=std(ctrl_per_cell,'omitnan')./sqrt(ctrl_count);
end
assert(all([numel(fam_mean),numel(ctrl_mean),numel(fam_sem),numel(ctrl_sem),numel(fam_count),numel(ctrl_count)]==nw), ...
    'paper020:summaryShape','Native default-dimension summary differs; no replacement values');
summary('familiar',fam_cw,fam_subset_count,fam_mean,fam_sem,fam_count);
summary('control',ctrl_per_cell,ctrl_subset_count,ctrl_mean,ctrl_sem,ctrl_count);
method='STA'; if selection(2)==2; method='OLS_INTERCEPT'; end
metadata=struct('schema','paper020_native_phase_payload_v1','configuration',job.configuration, ...
    'method',method,'mode',job.mode,'instrumentation',request.instrumentation, ...
    'trace_groups',ngroup,'source_default_dimension_compatible',true);
envelope=struct('metadata',metadata,'arrays',{descriptors});
meta_json=jsonencode(envelope);
assert(numel(unicode2native(meta_json,'UTF-8'))<=request.metadata_byte_limit, ...
    'paper020:metadataBudget','Native metadata budget exceeded');
% Flat numeric/character v5 envelope; arbitrary MATLAB object deserialization is
% unnecessary. v7.3 is intentionally not used as an automatic size fallback.
save(output_path,'meta_json','payload','-v6');

    function emit(name,value,shape,dtype)
        assert(numel(value)==prod(shape),'paper020:shape','Collector numerical extent differs');
        if strcmp(dtype,'<f8'); value=double(value); raw=typecast(value(:),'uint8');
        elseif strcmp(dtype,'<i8'); value=int64(value); raw=typecast(value(:),'uint8');
        elseif strcmp(dtype,'|b1'); raw=uint8(logical(value(:)));
        else; error('paper020:dtype','Unsupported native wire dtype'); end
        assert(numel(payload)+numel(raw)<=request.output_byte_limit,'paper020:outputBudget','Native array budget exceeded');
        descriptor=struct('name',name,'dtype',dtype,'shape',{num2cell(shape(:).')}, ...
            'offset',numel(payload),'bytes',numel(raw));
        descriptors{end+1}=descriptor;
        payload=[payload;raw(:)]; %#ok<AGROW> Future full-workload profile must include append scratch.
    end

    function summary(name,per_cell,subset_count,means,sem,count)
        prefix=['summary/' name '/'];
        emit([prefix 'per_cell'],per_cell.',[nw,ncell],'<f8');
        emit([prefix 'subset_non_nan_counts'],subset_count.',[nw,ncell],'<i8');
        emit([prefix 'means'],means(:),nw,'<f8');
        emit([prefix 'sem'],sem(:),nw,'<f8');
        emit([prefix 'cell_non_nan_counts'],int64(count(:)),nw,'<i8');
    end
end
