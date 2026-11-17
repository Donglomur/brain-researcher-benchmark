function h_prepare(request_path)
% Full selected originals -> private inert typed arrays. No fitting/filtering.
% Admission, immutable image, source authentication and original clock are
% enforced by the independent provider before this fixed entrypoint runs.
r=jsondecode(fileread(request_path));
assert(strcmp(r.schema,'h_native_request_v2') && strcmp(r.operation,'prepare'),'H:Request','Wrong request');
assert(strcmp(r.output_root,'/output'),'H:Path','Fixed private output mount');
root=r.output_root; assert(isfolder(root) && numel(dir(root))==2,'H:Fresh','Empty owned output mount required');
manifest=struct('schema','h_preparation_v2','status','incomplete','originals',{r.originals},...
    'identity_status','unresolved_external_authentication','behavior_sessions',{{}},'imaging_sessions',{{}},...
    'variant_metadata',{{}},'failures',{{}},'expected_behavior_sessions',92,'expected_imaging_variant_sessions',88,...
    'source_roster_is_identity_proof',false,'scientific_qualification',false);
h_io('json',fullfile(root,'preparation-start.json'),struct('schema','h_preparation_start_v2','expected_behavior_sessions',92,'expected_imaging_variant_sessions',88,'status','started'));
behavior=cell(1,92); imaging=cell(1,88); metadata=cell(1,2);
for k=1:92,behavior{k}=unstarted('behavior',k);end
for k=1:88,imaging{k}=unstarted('imaging',k);end
try
    original=load(r.originals(1).path,'allbeh');
    assert(isfield(original,'allbeh') && iscell(original.allbeh) && isequal(size(original.allbeh),[23 2]),'H:Schema','All 23 behavior animals required');
    for a=1:23
        for d=1:4
            k=(a-1)*4+d; dtype=ceil(d/2);within=mod(d-1,2)+1;
            row=ordinal('behavior',1,a,dtype,within,k);
            try
                days=original.allbeh{a,dtype}; assert(iscell(days) && numel(days)>=2,'H:Schema','At least two source days required');
                if dtype==1,source_day=numel(days)-2+within;else,source_day=within;end
                row.source_day_ordinal=source_day;
                row.arrays=session(root,sprintf('behavior/a%02d/d%d',a,d),days{source_day},false);
                row.status='exported';
            catch e,row.status='failed';row.error=h_io('error',e);end
            behavior{k}=row; h_io('json',fullfile(root,sprintf('behavior-%03d.json',k)),row);
        end
    end
catch e,manifest.failures{end+1}=struct('original',1,'error',h_io('error',e));end
clear original;
variants={'source_preprocessing','no_smoothing_no_flooring'};
for v=1:2
    try
        original=load(r.originals(v+1).path,'allrawtrials');
        assert(isfield(original,'allrawtrials'),'H:Schema','Missing allrawtrials');x=original.allrawtrials;
        assert(isstruct(x) && isscalar(x) && all(isfield(x,{'rawtrials','frametimes','p','rundatetime'})),'H:Schema','Full top-level imaging schema required');
        assert(iscell(x.rawtrials) && isequal(size(x.rawtrials),[11 2]),'H:Schema','All 11 imaging animals required');
        t=x.frametimes;assert(isnumeric(t) && isreal(t) && numel(t)==402 && isvector(t) && all(isfinite(t(:))) && all(diff(t(:))>0),'H:Clock','Finite increasing 402-frame original clock required');
        metadata{v}=struct('variant',variants{v},'status','exported','frametimes',h_io('numeric',root,[variants{v} '/frametimes'],t),...
            'p',h_io('pack',root,[variants{v} '/p'],x.p),'rundatetime',h_io('pack',root,[variants{v} '/rundatetime'],x.rundatetime),...
            'clock_kind','source_nominal_seconds_relative_first_odor','physical_acquisition_clock_authenticated',false);
        for a=1:11
            for d=1:4
                k=(v-1)*44+(a-1)*4+d;dtype=ceil(d/2);within=mod(d-1,2)+1;
                row=ordinal('imaging',v+1,a,dtype,within,k);row.variant=variants{v};row.source_day_ordinal=within;
                try
                    days=x.rawtrials{a,dtype};assert(iscell(days) && numel(days)==2,'H:Schema','Exactly two selected original days required');
                    row.arrays=session(root,sprintf('%s/a%02d/d%d',variants{v},a,d),days{within},true);
                    row.status='exported';
                catch e,row.status='failed';row.error=h_io('error',e);end
                imaging{k}=row;h_io('json',fullfile(root,sprintf('imaging-%03d.json',k)),row);
            end
        end
    catch e
        metadata{v}=struct('variant',variants{v},'status','failed','error',h_io('error',e));
        manifest.failures{end+1}=struct('original',v+1,'error',h_io('error',e));
    end
    clear original x;
end
manifest.behavior_sessions=behavior;manifest.imaging_sessions=imaging;manifest.variant_metadata=metadata;
manifest.structural_complete=all(cellfun(@(s)strcmp(s.status,'exported'),behavior)) && all(cellfun(@(s)strcmp(s.status,'exported'),imaging));
% An exported shape and source roster never authenticate real identity/joins.
manifest.status='incomplete_pending_independent_identity_and_alignment_admission';
if ~manifest.structural_complete,manifest.status='incomplete_schema_or_export_failure';end
h_io('json',fullfile(root,'preparation.json'),manifest);
end

function row=unstarted(kind,k)
row=struct('cohort',kind,'ordinal',k,'status','unstarted','reason','source_not_reached');
end

function row=ordinal(kind,original,a,dtype,within,k)
days={'standard_minus2','standard_minus1','reversal1','reversal2'};
row=struct('cohort',kind,'ordinal',k,'original_ordinal',original,'animal_source_ordinal',a,...
    'daytype_source_ordinal',dtype,'within_selected_day_ordinal',within,'identity_status','unresolved',...
    'source_ordinal_is_authenticated_identity',false,'animal_ordinal',a-1,'day',days{(dtype-1)*2+within});
end

function out=session(root,prefix,s,isimaging)
assert(isstruct(s) && isscalar(s) && all(isfield(s,{'beh','licking'})),'H:Schema','Complete daily behavior schema required');
assert(isnumeric(s.beh) && isreal(s.beh) && isequal(size(s.beh),[140 5]),'H:Schema','Exactly 140 trials and all five behavior fields required');
assert(iscell(s.licking) && numel(s.licking)==140,'H:Schema','All 140 trial lick vectors required');
assert(all(ismember(s.beh(:,1),[11 12 21 22 511 512 521 522])),'H:Labels','Unknown or missing first-odor code');
out=struct('beh',h_io('numeric',root,[prefix '/beh'],s.beh));
labels=ismember(s.beh(:,1),[21 22 521 522]);
out.first_odor_B=h_io('array',root,[prefix '/first_odor_B.npy'],labels,'|u1');
out.trial_source_ordinal=h_io('array',root,[prefix '/trial_source_ordinal.npy'],(1:140)','<i8');
out.acquisition_chunk_from_source_position=h_io('array',root,[prefix '/source_chunk_ordinal.npy'],ceil((1:140)'/20),'<i8');
out.acquisition_chunk_identity_authenticated=false;
offsets=zeros(141,1,'int64');chronological=false(140,1);finite=true(140,1);events=cell(140,1);
for tr=1:140
    lick=s.licking{tr};assert(isnumeric(lick) && isreal(lick) && (isvector(lick) || isempty(lick)),'H:Licks','Original lick vectors required');
    assert(~any(isinf(lick(:))),'H:Infinity','Infinite lick event');
    events{tr}=double(lick(:));offsets(tr+1)=offsets(tr)+numel(lick);
    finite(tr)=all(isfinite(lick(:)));chronological(tr)=finite(tr) && all(diff(lick(:))>=0);
end
% Preserve event list order and NaNs: never sort, interpolate or impute.
out.lick_events_seconds=h_io('numeric',root,[prefix '/lick_events_seconds'],vertcat(events{:}));
out.lick_offsets=h_io('array',root,[prefix '/lick_offsets.npy'],offsets,'<i8');
out.lick_chronological=h_io('array',root,[prefix '/lick_chronological.npy'],chronological,'|u1');
out.lick_finite=h_io('array',root,[prefix '/lick_finite.npy'],finite,'|u1');
out.lick_clock='seconds_relative_first_odor_source_subtraction_1';
out.lick_clock_identity_authenticated=false;
if ~isimaging,return;end
assert(all(isfield(s,{'F','Fneu','spks','locomotion','xyoff','roistats'})),'H:Schema','Every neural/nuisance/ROI field required');
assert(isnumeric(s.spks) && ndims(s.spks)==3 && size(s.spks,2)==140 && size(s.spks,3)==402 && size(s.spks,1)>0,'H:Schema','Full ROI by 140 by 402 required');
nr=size(s.spks,1);assert(iscell(s.roistats) && numel(s.roistats)==nr,'H:ROI','Every original ROI metadata entry required');
names={'F','Fneu','spks'};
for j=1:3
    name=names{j};assert(isnumeric(s.(name)) && isequal(size(s.(name)),[nr 140 402]),'H:ROI','Full same original ROI axis required');
    out.(name)=h_io('numeric',root,[prefix '/' name],s.(name));
end
names={'locomotion','xyoff'};
for j=1:2
    name=names{j};assert(isnumeric(s.(name)) && isequal(size(s.(name)),[140 402]),'H:Nuisance','All trial/frame nuisance support required');
    out.(name)=h_io('numeric',root,[prefix '/' name],s.(name));
end
quality=nan(nr,1);
for roi=1:nr
    z=s.roistats{roi};assert(isstruct(z) && isscalar(z) && isfield(z,'iscell') && isnumeric(z.iscell) && isscalar(z.iscell),'H:ROI','Original scalar iscell probability required');
    quality(roi)=z.iscell;
end
assert(all(isfinite(quality)) && all(quality>=0 & quality<=1),'H:ROI','Finite iscell probability required');
out.roi_source_ordinal=h_io('array',root,[prefix '/roi_source_ordinal.npy'],(1:nr)','<i8');
out.iscell=h_io('numeric',root,[prefix '/iscell'],quality);
out.eligible_mask=h_io('array',root,[prefix '/eligible_mask.npy'],quality>0.3,'|u1');
out.roistats=h_io('pack',root,[prefix '/roistats'],s.roistats);
out.roi_alignment_status='source_order_preserved_cross_variant_identity_unresolved';
end
