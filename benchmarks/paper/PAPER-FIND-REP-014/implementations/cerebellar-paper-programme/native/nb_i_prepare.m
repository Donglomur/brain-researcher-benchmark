function nb_i_prepare(data_root, output_root, limits_file)
% Future operator-only preparation; never candidate-visible and never a fit.
% Exact source support: MainData.m 14-17,218-232,513-556,603-620.
% The caller authenticates all ten complete immutable originals before launch.
if ~isfolder(data_root)||~isfolder(output_root),error('Existing immutable input and fresh output directories required');end
existing=dir(output_root);if any(~ismember({existing.name},{'.','..'})),error('Fresh empty output directory required');end
limits=jsondecode(fileread(limits_file));
keys={'max_files','max_file_bytes','max_output_bytes','max_metadata_bytes','max_collection_items','max_native_elements'};
if ~isequal(sort(fieldnames(limits)),sort(keys')),error('Exact preparation limit keys');end
for k=1:numel(keys),v=limits.(keys{k});if ~isscalar(v)||~isfinite(v)||v<1||fix(v)~=v||v>flintmax,error('Positive exact limits');end,end
if limits.max_metadata_bytes>limits.max_file_bytes||limits.max_file_bytes>limits.max_output_bytes,error('Nested preparation limits');end
budget=struct('files',0,'bytes',0,'nodes',0,'hash_read_bytes',0,'limits',limits,'outputs',{{}});
files={'mainData1.mat','mainData2.mat','mainLearn.mat','CF_novice.mat','IOChRmine.mat','IOChRmine_learn.mat','IOChRmine_imaging.mat','passiveMFB.mat','gtacr1.mat','gtacr1_learn.mat'};
report=struct('schema','filio_i_prepared_v1','matlab_version',version,'files_census',{{}},'acquisitions',{{}},'output_files',{{}},...
    'biological_identity_verified',false,'physical_trial_aliases_verified',false,'direct_sample_overlap_verified',false,...
    'original_normalization_lineage_verified',false,'original_attempt_bijection_verified',false);
% Census every variable, including embedded bsln/control aggregates, not only
% primary named collections. Native load expansion is container-bounded only.
for fi=1:numel(files)
    fn=fullfile(data_root,files{fi});if ~isfile(fn),error('Missing full original %s',files{fi});end
    vars=whos('-file',fn);r=struct('file',files{fi},'variables',{{}});
    for vi=1:numel(vars)
        name=vars(vi).name;loaded=load(fn,name);
        [node,budget]=nb_i_census(loaded.(name),budget,0);
        r.variables{end+1}=struct('name',name,'declared_class',vars(vi).class,'declared_shape',vars(vi).size,'declared_bytes',vars(vi).bytes,'census',node);
        clear loaded node
    end
    report.files_census{end+1}=r;
end
% Original MainData14-16 uses two unrestricted sequential loads. Resolve
% each required variable from the LAST source file whose census contains it.
% Never infer variable ownership from its suffix or publisher filename.
main_files={'mainData1.mat','mainData2.mat'};wanted={'micedats1','micedats2','dirTable'};resolved=struct();owners=struct();
for file_index=1:2
    census=report.files_census{file_index};if ~strcmp(census.file,main_files{file_index}),error('Exact MainData census load sequence');end
    available=cellfun(@(v)v.name,census.variables,'UniformOutput',false);
    if numel(unique(available))~=numel(available),error('Unique source variable census');end
    for name_index=1:numel(wanted)
        name=wanted{name_index};if ismember(name,available)
            loaded=load(fullfile(data_root,main_files{file_index}),name);
            if ~isfield(loaded,name),error('Census/load variable mismatch');end
            resolved.(name)=loaded.(name);owners.(name)=struct('file',main_files{file_index},'variable',name,'load_index',file_index);
            clear loaded
        end
    end
end
if ~all(isfield(resolved,wanted)),error('Required MainData variable absent after full sequential loads');end
if ~iscell(resolved.micedats1)||~iscell(resolved.micedats2)||~istable(resolved.dirTable),error('Exact source MainData collections after precedence');end
n1=numel(resolved.micedats1);micedats=cat(1,resolved.micedats1,resolved.micedats2);dirTable=resolved.dirTable;clear resolved
report.main_load_sequence=main_files;report.main_variable_owners=owners;
if numel(micedats)~=height(dirTable)||isempty(micedats),error('Complete source row/table join');end
required={'Delay','FirstRew','DAType','GrCs','CFType','DA_Dir','WaterDir','Alt_Delay_Dir'};
if ~all(ismember(required,dirTable.Properties.VariableNames)),error('Complete context/identity source fields');end
first=micedats{1};nb_i_clock(first.tmpx_right,'first neural template');
[~,grc_template]=winfn(first.tmpx_right,[-1 4]);[~,cf_template]=winfn(first.tmpx_right,[-2 2]);
for d=1:numel(micedats)
    for which=1:2
        if which==1,curd=micedats{d};collection='main';
        elseif isfield(micedats{d},'waterdat'),curd=micedats{d}.waterdat;collection='water';
        else
            missingviews={};if dirTable.Delay(d)==1,missingviews={'Water'};end
            report.acquisitions{end+1}=struct('key',sprintf('row%06d-water',d),'source_row',d,'collection','water','status','structural_absence','views',{missingviews},'reason','No source waterdat field');
            continue
        end
        if ~isstruct(curd)||~isscalar(curd),error('Exact source recording struct');end
        ctx=struct();for k=1:numel(required),name=required{k};ctx.(name)=nb_i_scalar(dirTable.(name)(d,:));end
        if ~isnumeric(ctx.Delay)||~isscalar(ctx.Delay)||~isfinite(ctx.Delay),error('Numeric finite source planned delay');end
        views={};
        if which==2 && ctx.Delay==1,views={'Water'};
        elseif which==1 && ctx.Delay==1,views={'1-s DA'};if strcmp(ctx.FirstRew,'DA'),views{end+1}='DA-first';end
        elseif which==1 && ctx.Delay==2,views={'2-s DA'};end
        if ~isscalar(curd.dtb)||~isfinite(curd.dtb)||curd.dtb<=0,error('Positive source behavior sampling period');end
        nb_i_clock(curd.tmpxx,'behavior');nb_i_clock(curd.tmpx_right,'neural');
        N=numel(curd.rewarded);if N>limits.max_collection_items,error('Full source trial cap; never crop');end
        if size(curd.rewarded,1)~=N||size(curd.goodMvmt,1)~=N||~isequal(size(curd.rewtimes),size(curd.trueend),size(curd.truestart)),error('Source trial-vector orientation must not be silently repaired');end
        rewarded=nb_i_flag(curd.rewarded,N);good0=nb_i_flag(curd.goodMvmt,N);
        truestart=nb_i_vector(curd.truestart,N);trueend=nb_i_vector(curd.trueend,N);rewtimes=nb_i_vector(curd.rewtimes,N);
        pos=curd.rewAlgn.pos;
        if ~isnumeric(pos)||~isreal(pos)||size(pos,1)~=N||size(pos,2)~=numel(curd.tmpxx)||size(pos,3)~=2||ndims(pos)>3,error('Complete two-component reward-aligned handle rows');end
        if numel(pos)>limits.max_native_elements,error('Full native handle element cap; never crop');end
        z=find(curd.tmpxx==0);if numel(z)~=1,error('Exact source zero behavior coordinate');end
        rewdel=(rewtimes-trueend)*curd.dtb;
        mvlen=reshape(sqrt(sum(pos(:,z,:).^2,3)),[],1);
        mvdurs=(trueend-truestart)*curd.dtb*1000;
        good=good0;good(rewdel>ctx.Delay*1.5)=false;good(rewdel<ctx.Delay*0.5)=false;
        eligible=good & mvlen>6;trash=false(N,1);
        % Preserve native exclusion only at source-selected event rows. Raw
        % event/frame arrays below remain unchanged, including gap statuses.
        if isfield(curd,'trashframes')
            chosen=find(eligible);ix=rewtimes(chosen);
            if any(~isfinite(ix)|ix~=fix(ix)|ix<1|ix>numel(curd.frame_right)),error('Native trash/event index mapping unavailable');end
            trash(chosen)=ismember(curd.frame_right(ix),curd.trashframes);
        end
        eligible=eligible & ~trash;
        a=struct('key',sprintf('row%06d-%s',d,collection),'source_row',d,'collection',collection,'status','present',...
            'source_part',1+(d>n1),'source_ordinal',d-(d>n1)*n1,'source_context',ctx,'views',{views},...
            'original_trial_count',N,'trial_axis_interpretation','Released source-array rows; original physical-attempt bijection remains unverified',...
            'dtb',curd.dtb,'dtb_seconds',curd.dtb,'arrays',struct(),'registrations',struct(),'modalities',{{}});
        if d<=n1,source_variable='micedats1';source_ordinal=d;else,source_variable='micedats2';source_ordinal=d-n1;end
        owner=owners.(source_variable);parent_source_prefix=sprintf('%s::%s{%d}',owner.file,source_variable,source_ordinal);source_prefix=parent_source_prefix;
        if which==2,source_prefix=[source_prefix '.waterdat'];end
        a.trashframes_present=isfield(curd,'trashframes');
        a.source_variable=source_variable;a.source_owner_file=owner.file;
        a.source_path=source_prefix;a.source_context_path=sprintf('%s::dirTable(%d,:)',owners.dirTable.file,d);
        a.registration_source_paths=struct('chronicGreen',[parent_source_prefix '.chronicGreen'],'chronicRed',[parent_source_prefix '.chronicRed']);
        a.source_field_paths=struct('rew_pos',[source_prefix '.rewAlgn.pos'],'behavior_clock',[source_prefix '.tmpxx'],'neural_clock',[source_prefix '.tmpx_right'],'dtb_seconds',[source_prefix '.dtb'],'frame_right',[source_prefix '.frame_right'],'truestart',[source_prefix '.truestart'],'trueend',[source_prefix '.trueend'],'rewtimes',[source_prefix '.rewtimes']);
        names={'trial_ordinal','rewarded','goodMvmt_original','goodMvmt_source','trash_excluded','eligible','eligible_rewarded','eligible_omitted',...
            'mvlen','movement_duration_ms','rewdel_seconds','truestart','trueend','rewtimes','frame_right','behavior_clock','neural_clock','rew_pos'};
        vals={int64((1:N)'),rewarded,good0,good,trash,eligible,eligible&rewarded,eligible&~rewarded,mvlen,mvdurs,rewdel,truestart,trueend,rewtimes,curd.frame_right,curd.tmpxx,curd.tmpx_right,pos};
        for k=1:numel(names)
            v=vals{k};if k==18,shape=[N numel(curd.tmpxx) 2];else,shape=numel(v);end
            [desc,budget]=nb_i_array(output_root,[a.key '_' names{k} '.npy'],v,shape,budget);a.arrays.(names{k})=desc;
        end
        if isfield(curd,'trashframes'),v=curd.trashframes;else,v=zeros(0,1);end
        [a.arrays.trashframes,budget]=nb_i_array(output_root,[a.key '_trashframes.npy'],v,numel(v),budget);
        for reg={'chronicGreen','chronicRed'}
            key=reg{1};if isfield(micedats{d},key)
                [a.registrations.(key),budget]=nb_i_typed(micedats{d}.(key),output_root,[a.key '_' key],budget,0);
            else,a.registrations.(key)=struct('kind','absent');end
        end
        for c=1:2
            if c==1,modality='GrC';signal='sigFilt_right_green';algn='endAlgn';cn='nc_right_green';lim=[-1 4];template=grc_template;present=strcmpi(ctx.GrCs,'Y');
            else,modality='CF';signal='sprate_right_red';algn='rewAlgn';cn='nc_right_red';lim=[-2 2];template=cf_template;present=~strcmpi(ctx.CFType,'none');end
            observed_count=NaN;if isfield(curd,cn)&&isnumeric(curd.(cn))&&isscalar(curd.(cn))&&isfinite(curd.(cn))&&curd.(cn)>=0&&fix(curd.(cn))==curd.(cn),observed_count=double(curd.(cn));end
            m=struct('name',modality,'status','structural_absence','reason','Source modality flag absent','cell_count',observed_count,'required_cells',0);
            if isempty(views),m.status='outside_selected_views';m.reason='Source four-view selectors do not include this recording';
            elseif present
                x=curd.(algn).(signal);C=curd.(cn);
                if ~isscalar(C)||C<0||C~=fix(C)||~isnumeric(x)||~isreal(x)||size(x,1)~=N||size(x,2)~=C||size(x,3)~=numel(curd.tmpx_right)||ndims(x)>3,error('Full native trial/cell/time axes');end
                [ix,source_time]=winfn(curd.tmpx_right,lim);
                if N*C*numel(template)>limits.max_native_elements||N*C*numel(ix)>limits.max_native_elements,error('Full target element cap; never crop');end
                % Literal MainData550-551 transformation, before any response
                % classification, reliability selection or trial averaging.
                curgrc=x(:,:,ix);
                if N*C==0,targets=zeros(N,C,numel(template));
                else,targets=permute(interp1(source_time,permute(curgrc,[3 1 2]),template,'linear','extrap'),[2 3 1]);end
                m=struct('name',modality,'status','present','cell_count',C,'required_cells',C,'source_signal',[algn '.' signal],'source_path',[source_prefix '.' algn '.' signal],...
                    'target_axes',{{'released_trial','source_cell','native_template_time'}},'interpolation','linear/extrap, literal MainData551');
                [m.targets,budget]=nb_i_array(output_root,[a.key '_' modality '_targets.npy'],targets,[N C numel(template)],budget);
                [m.target_time,budget]=nb_i_array(output_root,[a.key '_' modality '_target_time.npy'],template,numel(template),budget);
                [m.source_time,budget]=nb_i_array(output_root,[a.key '_' modality '_source_time.npy'],source_time,numel(source_time),budget);
                [m.source_time_indices,budget]=nb_i_array(output_root,[a.key '_' modality '_source_indices.npy'],int64(ix),numel(ix),budget);
            end
            a.modalities{end+1}=m;
        end
        report.acquisitions{end+1}=a;
    end
end
report.output_files=budget.outputs;
report.producer_io=struct('completed_array_files',budget.files,'completed_array_bytes',budget.bytes,'array_checksum_read_bytes',budget.hash_read_bytes,'native_input_read_bytes',[],'native_load_peak_bytes',[]);
report.producer_io.interpretation='Array writes/hash reads observed; native input read traffic and load expansion unknown. PREPARED metadata is additional, externally captured by the engine.';
report.full_source_rows=numel(micedats);report.required_original_files=files;
report.unknowns={'Animal/session identity and physical aliases are unverified','Source raw sample origins cannot be inferred from rounded dt','Original normalization/filter/registration dependencies remain unverified','Omission clock and source-to-array trial mapping require independent admission','All shapes/counts are source observations, not independent biological units'};
raw=unicode2native(jsonencode(report),'UTF-8');
if numel(raw)>limits.max_metadata_bytes,error('Complete metadata cap; never truncate');end
[~,budget]=nb_i_bytes(output_root,'PREPARED.json',raw,budget);
end

function x=nb_i_vector(x,N)
if ~isnumeric(x)||~isreal(x)||~isvector(x)&&~isempty(x)||numel(x)~=N,error('Exact source trial vector');end
x=reshape(x,[],1);
end
function x=nb_i_flag(x,N)
x=nb_i_vector(double(x),N);if any(~isfinite(x)|~ismember(x,[0 1])),error('Exact source binary flag');end;x=logical(x);
end
function nb_i_clock(x,name)
if ~isnumeric(x)||~isreal(x)||~isvector(x)||numel(x)<2||any(~isfinite(x))||any(diff(x)<=0),error('Strict native %s clock',name);end
end
function out=nb_i_scalar(x)
if isnumeric(x)||islogical(x)
    if ~isscalar(x)||~isfinite(x),error('Scalar finite source context');end;out=double(x);
elseif ischar(x),out=x;
elseif (isstring(x)||iscategorical(x))&&isscalar(x),if ismissing(x),out='';else,out=char(string(x));end
elseif iscell(x)&&isscalar(x),out=nb_i_scalar(x{1});
else,error('Scalar source context representation');end
end
