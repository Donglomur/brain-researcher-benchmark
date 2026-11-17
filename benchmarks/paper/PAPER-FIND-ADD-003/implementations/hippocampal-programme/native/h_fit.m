function h_fit(request_path)
% Prospective trusted comparator, independently isolated per outer producer.
% SOURCE ONLY: no historical-equivalence or native/runtime competence claim.
% All 20 configs x six inner attempts plus one final slot are retained.
r=jsondecode(fileread(request_path));
assert(strcmp(r.schema,'h_native_request_v2') && strcmp(r.operation,'fit') && strcmp(r.output_root,'/output') && strcmp(r.training_path,'/input/TRAINING.json'),'H:Request','Fixed prospective request');
root='/output';assert(isfolder(root) && numel(dir(root))==2,'H:Fresh','Empty private output mount');
configs=configurations();attempts=cell(1,121);
for c=1:20
    for f=1:6,k=(c-1)*6+f;attempts{k}=struct('ordinal',k,'stage','inner','config',c,'fold',f,'status','unstarted');end
end
attempts{121}=struct('ordinal',121,'stage','final','config',[],'fold',[],'status','unstarted');
h_io('json',fullfile(root,'fit-ledger.initial.json'),struct('schema','h_svm_attempts_v1','attempts',{attempts},'expected_attempts',121));
selection=struct('status','unstarted');result=struct('schema','h_svm_fit_result_v1','status','incomplete','scientific_qualification',false);
try
    t=jsondecode(fileread(r.training_path));assert(strcmp(t.schema,'h_training_view_v2'),'H:Training','Training schema');
    assert(islogical(t.clock) && isscalar(t.clock) && t.channels>=1 && t.channels==fix(t.channels),'H:Training','Typed channel/clock declaration');
    assert(isfield(t,'query_labels_exposed') && isequal(t.query_labels_exposed,false),'H:Exposure','Training-only exposure declaration required');
    expected={'values','missing','labels','trial_group'};if t.clock,expected{end+1}='clock';end
    assert(isequal(sort(fieldnames(t.arrays)),sort(expected(:))),'H:Exposure','Only declared training tensors may be supplied');
    assert(strcmp(t.arrays.values.dtype,'<f8') && strcmp(t.arrays.missing.dtype,'|u1') && strcmp(t.arrays.trial_group.dtype,'<i8') && any(strcmp(t.arrays.labels.dtype,{'<i8','|u1'})),'H:Dtype','Exact training tensor dtypes');
    values=double(h_read_npy('/input',t.arrays.values));missing=logical(h_read_npy('/input',t.arrays.missing));
    y=double(h_read_npy('/input',t.arrays.labels));groups=double(h_read_npy('/input',t.arrays.trial_group));
    assert(ndims(values)==3 && size(values,2)==t.channels && size(values,3)==15 && isequal(size(values),size(missing)),'H:Training','Full local window tensor');
    n=size(values,1);assert(isequal(size(y),[n 1]) && isequal(size(groups),[n 1]),'H:Training','One label and group per training window');
    assert(all(isfinite(values(:))) && all(values(missing)==0),'H:Training','Finite values with explicit missing zeros');
    assert(all(y==0 | y==1) && all(isfinite(groups)) && all(groups==fix(groups)),'H:Training','Binary labels and integer trial groups');
    uniquegroups=unique(groups);nt=numel(uniquegroups);
    assert(ismember(nt,[118 119]) && n==5*nt && isequal(uniquegroups,(0:nt-1)'),'H:Training','Every complete purged outer training trial and five windows');
    for g=0:nt-1,ix=groups==g;assert(sum(ix)==5 && numel(unique(y(ix)))==1,'H:Training','Trial-atomic common labels across five windows');end
    clock=zeros(n,0);
    if t.clock
        assert(strcmp(t.arrays.clock.dtype,'<f8'),'H:Dtype','Float64 allowed clock');
        clock=double(h_read_npy('/input',t.arrays.clock));assert(isequal(size(clock),[n 5]) && all(clock(:)==0 | clock(:)==1) && all(sum(clock,2)==1),'H:Clock','Five allowed current-window clock indicators');
        for g=0:nt-1,assert(all(sum(clock(groups==g,:),1)==1),'H:Clock','All five current-window clocks per trial');end
    else,assert(~isfield(t.arrays,'clock'),'H:Clock','No explicit clock in neural-only fit');end
    folds=t.inner_folds;assert(numel(folds)==6,'H:Training','Exactly six inner folds');seen=zeros(nt,1);
    for f=1:6
        tr=double(folds(f).train_groups(:));va=double(folds(f).validation_groups(:));
        assert(~isempty(tr) && ~isempty(va) && all(ismember(tr,uniquegroups)) && all(ismember(va,uniquegroups)) && numel(unique(tr))==numel(tr) && numel(unique(va))==numel(va) && isempty(intersect(tr,va)),'H:Training','Disjoint complete declared inner groups');
        seen(va+1)=seen(va+1)+1;
    end
    assert(all(seen==1),'H:Training','Validation groups must partition every outer training trial');
    rng(0,'twister'); % Prospective producer seed, not a historical author seed.
    evaluated=cell(1,20);
    for c=1:20
        cfg=configs(c);[raw,mask]=features(values,missing,cfg.family);oof=nan(n,1);coverage=zeros(n,1);complete=true;
        for f=1:6
            k=(c-1)*6+f;a=attempts{k};a.status='started';a.config_definition=cfg;
            h_io('json',fullfile(root,sprintf('fit-%03d.started.json',k)),a);
            try
                train=ismember(groups,double(folds(f).train_groups(:)));valid=ismember(groups,double(folds(f).validation_groups(:)));
                transform=learn_transform(raw(train,:),mask(train,:));
                X=transform_features(raw(train,:),mask(train,:),clock(train,:),transform);
                V=transform_features(raw(valid,:),mask(valid,:),clock(valid,:),transform);
                [model,meta]=fit_native(X,y(train),cfg);
                margin=native_margin(model,V);assert(all(isfinite(margin)),'H:Scores','Finite OOF margins');
                oof(valid)=margin;coverage(valid)=coverage(valid)+1;
                a.status='completed';a.train_rows=sum(train);a.validation_rows=sum(valid);a.native=meta;
            catch e,a.status='failed';a.error=h_io('error',e);complete=false;end
            attempts{k}=a;h_io('json',fullfile(root,sprintf('fit-%03d.json',k)),a);
        end
        record=struct('config',c,'definition',cfg,'status','invalid');
        if complete && all(coverage==1) && all(isfinite(oof))
            try
                [threshold,balanced]=choose_threshold(oof,y);
                record.status='complete';record.threshold=threshold;record.balanced_accuracy=balanced;
                record.oof_margin=h_io('array',root,sprintf('config-%02d-oof.npy',c),oof,'<f8',[n]);
            catch e,record.error=h_io('error',e);end
        else,record.reason='one_or_more_inner_attempts_failed_or_incomplete';end
        evaluated{c}=record;
        h_io('json',fullfile(root,sprintf('config-%02d.json',c)),record);
    end
    % Iteration order is exactly complexity, C, declared gamma order; retain
    % the earlier config on exact balanced-accuracy ties.
    best=0;bestBA=-inf;
    for c=1:20
        if strcmp(evaluated{c}.status,'complete') && evaluated{c}.balanced_accuracy>bestBA,best=c;bestBA=evaluated{c}.balanced_accuracy;end
    end
    assert(best>0,'H:Selection','No complete valid configuration; no partial-config selection');
    selection=struct('status','selected','config',best,'definition',configs(best),'threshold',evaluated{best}.threshold,'inner_balanced_accuracy',bestBA,'evaluated',{evaluated});
    h_io('json',fullfile(root,'selection.json'),selection);
    a=attempts{121};a.status='started';a.config=best;a.config_definition=configs(best);
    h_io('json',fullfile(root,'fit-121.started.json'),a);
    try
        [raw,mask]=features(values,missing,configs(best).family);transform=learn_transform(raw,mask);
        X=transform_features(raw,mask,clock,transform);[model,meta]=fit_native(X,y,configs(best));
        native=native_margin(model,X);params=export_model(root,model,meta,transform,configs(best),evaluated{best}.threshold,t.channels,t.clock,X,native);
        params.training_input_manifest_sha256=h_io('sha',r.training_path);
        params.training_input_arrays=t.arrays;params.training_only=true;params.query_labels_exposed=false;
        a.status='completed';a.native=meta;attempts{121}=a;
        envelope=struct('schema','h_svm_export_v1','status','complete','parameters',rmfield(params,{'arrays','native_training_margins'}),...
            'arrays',params.arrays,'native_training_margins',params.native_training_margins,'attempts',{attempts},'scientific_qualification',false);
        h_io('json',fullfile(root,'MODEL_PARAMETERS.json'),envelope);
        result.status='parameters_exported_pending_independent_graph_roundtrip';
        result.model_parameters_sha256=h_io('sha',fullfile(root,'MODEL_PARAMETERS.json'));
    catch e,a.status='failed';a.error=h_io('error',e);end
    attempts{121}=a;h_io('json',fullfile(root,'fit-121.json'),a);
catch e,result.error=h_io('error',e);end
result.selection=selection;result.attempts=attempts;result.expected_attempts=121;
result.completed_attempts=sum(cellfun(@(a)strcmp(a.status,'completed'),attempts));
result.failed_attempts=sum(cellfun(@(a)strcmp(a.status,'failed'),attempts));
result.unstarted_attempts=sum(cellfun(@(a)strcmp(a.status,'unstarted'),attempts));
h_io('json',fullfile(root,'fit-ledger.json'),result);
if ~isfile(fullfile(root,'MODEL_PARAMETERS.json'))
    h_io('json',fullfile(root,'MODEL_PARAMETERS.json'),struct('schema','h_svm_export_v1','status','incomplete','parameters',struct,...
        'arrays',struct,'native_training_margins',[],'attempts',{attempts},'failure_evidence','fit-ledger.json','scientific_qualification',false));
end
% Parent graph compiler owns RESULT.json after independent training roundtrip.
end

function c=configurations()
Cs=[0.015625 0.25 4 64];families={'linear_mean','linear_fullwindow','gaussian_fullwindow'};
c=repmat(struct('family','','C',0,'gamma_multiplier',0),1,20);k=0;
for f=1:3
    for j=1:4
        gammas=0;if f==3,gammas=[0.25 1 4];end
        for g=gammas,k=k+1;c(k)=struct('family',families{f},'C',Cs(j),'gamma_multiplier',g);end
    end
end
end

function [raw,mask]=features(values,missing,family)
n=size(values,1);channels=size(values,2);
if strcmp(family,'linear_mean')
    raw=mean(values,3);mask=any(missing,3);
else
    raw=reshape(permute(values,[1 3 2]),n,15*channels);
    mask=reshape(permute(missing,[1 3 2]),n,15*channels);
end
end

function t=learn_transform(raw,missing)
F=size(raw,2);means=zeros(1,F);scales=ones(1,F);allmissing=false(1,F);
for j=1:F
    x=raw(~missing(:,j),j);
    if isempty(x),allmissing(j)=true;continue;end
    means(j)=mean(x);scales(j)=std(x,1);if scales(j)==0,scales(j)=1;end
end
assert(all(isfinite(means)) && all(isfinite(scales)) && all(scales>0),'H:Transform','Finite population training transform required');
t=struct('mean',means,'scale',scales,'all_missing',allmissing);
end

function X=transform_features(raw,missing,clock,t)
X=(raw-t.mean)./t.scale;X(missing)=0;X(:,t.all_missing)=0;
X=[X double(missing) clock];assert(all(isfinite(X(:))),'H:Transform','Finite transformed complete feature vector');
end

function [m,meta]=fit_native(X,y,cfg)
assert(all(ismember([0 1],unique(y))),'H:Classes','Both training classes required');
n=numel(y);weights=zeros(n,1);weights(y==0)=n/(2*sum(y==0));weights(y==1)=n/(2*sum(y==1));D=size(X,2);
gamma=0;kernel='linear';
if strcmp(cfg.family,'gaussian_fullwindow'),gamma=cfg.gamma_multiplier/D;kernel=@(u,v)gaussian(u,v,gamma);end
lastwarn('');
m=fitcsvm(X,y,'ClassNames',[0;1],'BoxConstraint',cfg.C,'Weights',weights,...
    'Prior','uniform','Cost',[0 1;1 0],'Standardize',false,'ScoreTransform','none',...
    'Solver','SMO','IterationLimit',1000000,'KKTTolerance',0.001,...
    'KernelFunction',kernel,'KernelScale',1,'CacheSize',128);
[warning_message,warning_id]=lastwarn;
assert(isempty(warning_message),'H:NativeWarning','Native warning %s: %s',warning_id,warning_message);
assert(isequal(double(m.ClassNames(:)),[0;1]),'H:Orientation','Explicit class order required');
ci=m.ConvergenceInfo;
assert(isstruct(ci) && isfield(ci,'Converged') && isscalar(ci.Converged) && ci.Converged==true,'H:Convergence','Unknown or failed native convergence');
meta=struct('class_order',[0 1],'gamma',gamma,'D',D,'solver','SMO','iteration_limit',1000000,...
    'kkt_tolerance',0.001,'kernel_scale',1,'cache_size_native_megabytes',128,'standardize',false,'score_transform','none',...
    'class_weights','N/(2*N_class)','prior','uniform','converged',true,'compatibility_and_native_competence_qualified',false);
end

function k=gaussian(u,v,gamma)
d=max(0,sum(u.^2,2)+sum(v.^2,2)'-2*(u*v'));
k=exp(-gamma*d);
end

function margin=native_margin(m,X)
[~,scores]=predict(m,X);
assert(isnumeric(scores) && isequal(size(scores),[size(X,1) 2]) && all(isfinite(scores(:))),'H:Scores','Finite binary score matrix');
margin=scores(:,2);assert(all(abs(scores(:,1)+margin)<=1e-10*(1+abs(margin))),'H:Orientation','Untransformed signed binary margins required');
end

function [threshold,best]=choose_threshold(scores,y)
assert(all(ismember([0 1],unique(y))),'H:Classes','Both classes in complete pooled OOF required');
z=unique(scores);lo=z(1)-4*eps(max(1,abs(z(1))));hi=z(end)+4*eps(max(1,abs(z(end))));
assert(isfinite(lo) && isfinite(hi) && lo<z(1) && hi>z(end),'H:Threshold','Finite exterior decision thresholds required');
mid=z(1:end-1)/2+z(2:end)/2;choices=unique([lo;mid;hi]);
best=-inf;threshold=nan;
for k=1:numel(choices)
    t=choices(k);pred=scores>=t;
    ba=0.5*(sum(pred(y==1)==1)/sum(y==1)+sum(pred(y==0)==0)/sum(y==0));
    if ba>best || (ba==best && (abs(t)<abs(threshold) || (abs(t)==abs(threshold) && t<threshold)))
        best=ba;threshold=t;
    end
end
assert(isfinite(best) && isfinite(threshold),'H:Threshold','Complete finite calibration result');
end

function p=export_model(root,m,meta,t,cfg,threshold,channels,hasclock,X,native)
F=numel(t.mean);D=size(X,2);arrays=struct;
arrays.mean=h_io('array',root,'parameters/mean.npy',t.mean,'<f8',[F]);
arrays.scale=h_io('array',root,'parameters/scale.npy',t.scale,'<f8',[F]);
arrays.all_missing=h_io('array',root,'parameters/all_missing.npy',t.all_missing,'|u1',[F]);
bias=double(m.Bias);assert(isreal(bias) && isscalar(bias) && isfinite(bias),'H:Export','Finite native bias');
arrays.bias=h_io('array',root,'parameters/bias.npy',bias,'<f8',[]);
arrays.threshold=h_io('array',root,'parameters/threshold.npy',threshold,'<f8',[]);
if startsWith(cfg.family,'linear')
    beta=double(m.Beta(:));assert(numel(beta)==D && all(isfinite(beta)),'H:Export','Complete linear beta');
    exported=X*beta+bias;
    arrays.beta=h_io('array',root,'parameters/beta.npy',beta,'<f8',[D]);
else
    sv=double(m.SupportVectors);alpha=double(m.Alpha(:));svlabels=double(m.SupportVectorLabels(:));
    assert(size(sv,2)==D && size(sv,1)==numel(alpha) && numel(alpha)==numel(svlabels) && all(svlabels==1 | svlabels==-1) && all(isfinite(sv(:))) && all(isfinite(alpha)),'H:Export','Typed complete support vectors and native signed labels');
    signed=alpha.*svlabels;exported=gaussian(X,sv,meta.gamma)*signed+bias;K=size(sv,1);
    arrays.support_vectors=h_io('array',root,'parameters/support_vectors.npy',sv,'<f8',[K D]);
    arrays.signed_alpha=h_io('array',root,'parameters/signed_alpha.npy',signed,'<f8',[K]);
    arrays.gamma=h_io('array',root,'parameters/gamma.npy',meta.gamma,'<f8',[]);
end
assert(all(isfinite(exported)) && all(abs(exported-native)<=1e-8*(1+abs(native))),'H:Roundtrip','Native score orientation/kernel/export mismatch on training support');
assert(isequal(exported>=threshold,native>=threshold),'H:Roundtrip','Training class roundtrip mismatch');
n=size(X,1);
roundtrip=struct('transformed_X',h_io('array',root,'training-roundtrip/transformed_X.npy',X,'<f8',[n D]),...
    'native_margin',h_io('array',root,'training-roundtrip/native_margin.npy',native,'<f8',[n]),...
    'exported_margin',h_io('array',root,'training-roundtrip/exported_margin.npy',exported,'<f8',[n]),...
    'rtol',1e-8,'atol',1e-8,'native_formula_training_check_passed',true,'independent_graph_roundtrip','required');
p=struct('schema','h_svm_parameters_v1','family',cfg.family,'channels',channels,'clock',hasclock,'arrays',arrays,...
    'config',cfg,'native_options',meta,'class_order',[0 1],'decision','raw_margin_minus_threshold_greater_equal_zero_is_B',...
    'training_roundtrip',roundtrip,'scientific_qualification',false);
p.native_training_margins=h_io('array',root,'training-roundtrip/native_centered_margin.npy',native-threshold,'<f8',[n]);
end
