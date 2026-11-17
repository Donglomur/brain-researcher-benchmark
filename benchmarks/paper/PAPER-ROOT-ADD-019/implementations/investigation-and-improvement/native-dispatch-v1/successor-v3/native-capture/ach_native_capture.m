function out = ach_native_capture(action, varargin)
% Source-only native observation sink. No scientific estimator is implemented.
% Every result remains provisional until independent native/outer admission.
persistent st
out = [];
switch action
    case 'begin'
        if ~isempty(st), error('achcapture:active', 'An owned capture is active'); end
        cfg = varargin{1}; directory = varargin{2}; limits = varargin{3};
        fields = {'max_snapshots','max_nodes','max_depth','max_files', ...
            'max_total_bytes','max_leaf_bytes','max_snapshot_bytes', ...
            'max_workspace_bytes','max_cache_bytes'};
        if ~isstruct(limits) || ~isequal(sort(fieldnames(limits)), sort(fields'))
            error('achcapture:limits', 'Exact explicit limit fields required');
        end
        for i=1:numel(fields)
            v=limits.(fields{i});
            if ~isa(v,'double') || ~isscalar(v) || ~isfinite(v) || v<1 || v~=fix(v) || v>flintmax
                error('achcapture:limits', 'Positive exact natural limit required');
            end
        end
        if ~ischar(directory) || ~isfolder(directory)
            error('achcapture:directory', 'Fresh independently owned directory required');
        end
        listing=dir(directory); listing=listing(~ismember({listing.name},{'.','..'}));
        if ~isempty(listing), error('achcapture:directory', 'Capture directory must be empty'); end
        st=ach_native_capture_state(cfg,directory,limits);
    case 'snapshot'
        active(st);
        anchor=varargin{1}; kind=varargin{2};
        info=evalin('caller','whos');
        keep=~startsWith({info.name},'achcap_'); info=info(keep);
        if sum([info.bytes])>st.limits.max_workspace_bytes
            error('achcapture:workspace', 'Workspace logical extent exceeds selected cap');
        end
        vars=struct;
        for i=1:numel(info)
            value=evalin('caller',info(i).name);
            [vars.(info(i).name),st]=encode(value,st,0);
        end
        record=struct('schema','ach_native_snapshot_v1','anchor',anchor, ...
            'kind',kind,'workspace',vars,'workspace_whos_bytes',sum([info.bytes]), ...
            'context_id',st.cfg.context_id,'root_id',st.cfg.root_id, ...
            'mode',st.cfg.mode,'capture_spec_sha256',st.cfg.capture_spec_sha256);
        record.workspace_variable_order={info.name};
        if strcmp(kind,'root_return')
            [record.graphics_numeric,st]=graphics_numeric(st);
            st.root_returned=true;
        end
        [descriptor,st]=record_write(record,st);
        st.records{end+1}=descriptor;
    case 'value'
        active(st); anchor=varargin{1}; out=varargin{2};
        [node,st]=encode(out,st,0);
        record=struct('schema','ach_native_value_tap_v1','anchor',anchor, ...
            'value',node,'context_id',st.cfg.context_id,'root_id',st.cfg.root_id, ...
            'mode',st.cfg.mode,'capture_spec_sha256',st.cfg.capture_spec_sha256);
        [descriptor,st]=record_write(record,st); st.records{end+1}=descriptor;
    case 'cache_branch'
        active(st); root=varargin{1}; path=varargin{2}; cached_true=varargin{3};
        if ~strcmp(root,st.cfg.root_id), error('achcapture:root','Cache root mismatch'); end
        if strcmp(st.cfg.mode,'forced_recompute')
            % Deliberately do not open or inspect the existing cache body.
            out=~cached_true;
        elseif strcmp(st.cfg.mode,'cached_replay')
            if exist(path,'file')~=2, error('achcapture:cache','Required admitted cache missing'); end
            out=cached_true;
        else
            error('achcapture:mode','This root requires explicit cache/recompute mode');
        end
    case 'cache_output'
        active(st);
        if ~strcmp(st.cfg.mode,'forced_recompute') || ~isempty(st.cache_path)
            error('achcapture:cache','Only one owned recomputed cache is supported');
        end
        % The original save statement executes once at this owned destination.
        % A parent process/file-size guard is still required during native save.
        st.cache_path=fullfile(st.directory,'native-recomputed-cache.mat');
        if exist(st.cache_path,'file'), error('achcapture:collision','Cache collision'); end
        st.cache_reserved=st.limits.max_cache_bytes;
        reserve(st,st.cache_reserved); st.bytes=st.bytes+st.cache_reserved;
        st.files=st.files+1; out=st.cache_path;
    case 'finish'
        active(st);
        if ~st.root_returned, error('achcapture:incomplete','No root return snapshot'); end
        cache=struct('present',false);
        if ~isempty(st.cache_path)
            d=dir(st.cache_path);
            if numel(d)~=1 || d.isdir || d.bytes>st.cache_reserved
                error('achcapture:cache_extent','Native saved product extent failed');
            end
            sync_file(st.cache_path);
            cache=struct('present',true,'path','native-recomputed-cache.mat', ...
                'bytes',d.bytes,'sha256',sha_file(st.cache_path,d.bytes), ...
                'artifact_type','original_native_save_MAT', ...
                'body_schema_admitted',false,'recomputed_not_cache_input',true);
        end
        record=struct('schema','ach_native_capture_index_v1', ...
            'status','root_returned_provisional','source',st.cfg, ...
            'snapshots',{st.records},'native_cache',cache, ...
            'files_before_footer',st.files,'bytes_reserved_before_footer',st.bytes, ...
            'nodes',st.nodes,'limits',st.limits, ...
            'native_qualified',false,'outer_natural_zero_established',false, ...
            'directory_durability_established',false);
        [out,st]=json_file(record,'CAPTURE_INDEX.json',st);
        st.finished=true;
    case 'failure'
        % Best-effort diagnostic only. Caller retains the original exception.
        active(st); failure=varargin{1};
        record=struct('schema','ach_native_capture_failure_v1', ...
            'root_id',st.cfg.root_id,'context_id',st.cfg.context_id, ...
            'identifier',failure.identifier,'message',failure.message, ...
            'snapshots',{st.records},'status','partial_unaccepted', ...
            'root_returned',st.root_returned,'finished',st.finished);
        [out,st]=json_file(record,'FAILURE.json',st);
    case 'reset'
        st=[];
    otherwise
        error('achcapture:action','Unknown sink action');
end
end

function active(st)
if isempty(st) || st.finished
    error('achcapture:inactive','Capture is not active');
end
end

function reserve(st,n)
if n<0 || ~isfinite(n) || n~=fix(n) || n>flintmax || ...
        st.bytes+n>st.limits.max_total_bytes || st.files+1>st.limits.max_files
    error('achcapture:budget','Complete capture budget unavailable');
end
end

function [node,st]=encode(v,st,depth)
st.nodes=st.nodes+1;
if st.nodes>st.limits.max_nodes || depth>st.limits.max_depth
    error('achcapture:tree_cap','Capture tree bound exceeded');
end
c=class(v); shape=size(v);
node=struct('class',c,'shape',shape);
primitive={'double','single','int8','uint8','int16','uint16', ...
    'int32','uint32','int64','uint64','logical','char'};
if any(strcmp(c,primitive))
    if issparse(v)
        [row,col,value]=find(v);
        [node.row,st]=encode(row,st,depth+1);
        [node.column,st]=encode(col,st,depth+1);
        [node.values,st]=encode(value,st,depth+1);
        node.storage='sparse_triplets_column_major';
    elseif ~isreal(v)
        [node.real,st]=raw_leaf(real(v),c,st);
        [node.imaginary,st]=raw_leaf(imag(v),c,st);
        node.storage='complex_separate_planes_column_major';
    else
        [node.leaf,st]=raw_leaf(v,c,st);
        node.storage='little_endian_column_major';
    end
elseif strcmp(c,'cell')
    node.storage='cell_column_major'; node.values=cell(1,numel(v));
    for j=1:numel(v), [node.values{j},st]=encode(v{j},st,depth+1); end
elseif strcmp(c,'struct')
    names=fieldnames(v); node.storage='struct_column_major';
    node.field_order=names; node.values=cell(1,numel(v)*numel(names));
    for j=1:numel(v)
        for k=1:numel(names)
            [node.values{(j-1)*numel(names)+k},st]=encode(v(j).(names{k}),st,depth+1);
        end
    end
elseif strcmp(c,'string')
    node.storage='string_elements_UTF8_with_missing_mask';
    missing=ismissing(v); [node.missing,st]=encode(missing,st,depth+1);
    node.values=cell(1,numel(v));
    for j=1:numel(v)
        if missing(j)
            node.values{j}=struct('status','missing_string');
        else
            [node.values{j},st]=raw_leaf(unicode2native(char(v(j)),'UTF-8'),'uint8',st);
        end
    end
elseif strcmp(c,'table') || strcmp(c,'timetable')
    node.storage='table_columns'; node.variable_order=v.Properties.VariableNames;
    node.columns=cell(1,width(v));
    for j=1:width(v), [node.columns{j},st]=encode(v.(node.variable_order{j}),st,depth+1); end
    [node.row_names,st]=encode(v.Properties.RowNames,st,depth+1);
    [node.dimension_names,st]=encode(v.Properties.DimensionNames,st,depth+1);
    [node.variable_units,st]=encode(v.Properties.VariableUnits,st,depth+1);
    [node.variable_descriptions,st]=encode(v.Properties.VariableDescriptions,st,depth+1);
    [node.description,st]=encode(v.Properties.Description,st,depth+1);
    [node.user_data,st]=encode(v.Properties.UserData,st,depth+1);
    custom=v.Properties.CustomProperties; custom_names=properties(custom);
    node.custom_property_order=custom_names;node.custom_properties=cell(size(custom_names));
    for j=1:numel(custom_names)
        [node.custom_properties{j},st]=encode(custom.(custom_names{j}),st,depth+1);
    end
    if strcmp(c,'timetable'), [node.row_times,st]=encode(v.Properties.RowTimes,st,depth+1); end
elseif strcmp(c,'categorical')
    node.storage='categorical_codes_and_categories';
    [node.codes,st]=encode(double(v),st,depth+1);
    [node.categories,st]=encode(categories(v),st,depth+1);
    node.ordinal=isordinal(v);
elseif strcmp(c,'function_handle')
    f=functions(v); node.storage='source_bound_function_handle_description';
    [node.expression,st]=encode(func2str(v),st,depth+1);
    if isfield(f,'workspace'), [node.workspace,st]=encode(f.workspace,st,depth+1); end
    node.executable_handle_not_serialized=true;
elseif all(isgraphics(v(:))) && ~isempty(v)
    node.storage='graphics_handle_explicitly_excluded';
elseif any(strcmp(c,{'LinearModel','LinearMixedModel','CompactLinearModel', ...
        'ClassificationPartitionedLinear','ClassificationLinear', ...
        'CompactClassificationLinear', ...
        'classreg.learning.partition.ClassificationPartitionedLinear', ...
        'classreg.learning.classif.CompactClassificationLinear'}))
    if ~isscalar(v)
        node.storage='native_model_array_column_major';node.values=cell(1,numel(v));
        for j=1:numel(v), [node.values{j},st]=encode(v(j),st,depth+1); end
        return
    end
    % A declared projection, not an assertion that private model internals
    % have a portable complete representation. Original scalar extractions
    % and the single-evaluation kfoldLoss tap remain separately captured.
    node.storage='declared_native_model_property_projection';
    names={'Coefficients','CoefficientCovariance','DFE','MSE','RMSE', ...
        'Rsquared','LogLikelihood','ModelCriterion','Fitted','Residuals', ...
        'NumObservations','ResponseName','PredictorNames','Beta','Bias', ...
        'Lambda','ClassNames','Prior','Cost','Trained'};
    node.property_order=names; node.properties=cell(size(names));
    for j=1:numel(names)
        if isprop(v,names{j})
            [node.properties{j},st]=encode(v.(names{j}),st,depth+1);
        else
            node.properties{j}=struct('status','property_not_defined_on_class');
        end
    end
    node.private_internal_state_not_claimed=true;
else
    error('achcapture:unsupported_class','Unsupported non-graphics class: %s',c);
end
end

function [descriptor,st]=raw_leaf(v,c,st)
classes={'double','single','int8','uint8','int16','uint16', ...
    'int32','uint32','int64','uint64','logical','char'};
sizes=[8,4,1,1,2,2,4,4,8,8,1,2];
i=find(strcmp(c,classes),1);
if isempty(i), error('achcapture:wire_class','Unsupported wire class'); end
expected=numel(v)*sizes(i);
if expected>st.limits.max_leaf_bytes || expected>flintmax
    error('achcapture:leaf_cap','Raw leaf cap exceeded before write');
end
reserve(st,expected); st.files=st.files+1; st.bytes=st.bytes+expected;
name=sprintf('leaf-%09d.bin',st.files); path=fullfile(st.directory,name);
exclusive(path); fid=fopen(path,'w','ieee-le');
if fid<0, error('achcapture:open','Cannot open owned leaf'); end
primary=[];
try
    precision=c;
    if strcmp(c,'logical'), precision='uint8'; end
    if strcmp(c,'char'), precision='uint16'; end
    for first=1:65536:numel(v)
        last=min(first+65535,numel(v));
        count=fwrite(fid,v(first:last),precision);
        if count~=last-first+1, error('achcapture:short_write','Short raw write'); end
    end
catch failure
    primary=failure;
end
primary=close_reader_writer(fid,primary);
if ~isempty(primary), rethrow(primary); end
sync_file(path); d=dir(path);
if numel(d)~=1 || d.bytes~=expected, error('achcapture:extent','Raw leaf extent mismatch'); end
descriptor=struct('path',name,'bytes',expected,'sha256',sha_file(path,expected), ...
    'class',c,'shape',size(v),'byte_order','little','layout','MATLAB_column_major', ...
    'NaN_Inf_policy','preserved_in_raw_floating_payload_not_JSON');
end

function [descriptor,st]=record_write(record,st)
st.snapshots=st.snapshots+1;
if st.snapshots>st.limits.max_snapshots
    error('achcapture:snapshot_cap','Complete snapshot count exceeds selected cap');
end
record.sequence=st.snapshots;
name=sprintf('snapshot-%09d.json',st.snapshots);
[descriptor,st]=json_file(record,name,st);
end

function [descriptor,st]=json_file(record,name,st)
bytes=unicode2native(jsonencode(record),'UTF-8');
if numel(bytes)>st.limits.max_snapshot_bytes
    error('achcapture:metadata_cap','Capture metadata cap exceeded before write');
end
reserve(st,numel(bytes)); st.files=st.files+1; st.bytes=st.bytes+numel(bytes);
path=fullfile(st.directory,name); exclusive(path); fid=fopen(path,'w');
if fid<0, error('achcapture:open','Cannot open owned metadata'); end
primary=[];
try
    if fwrite(fid,bytes,'uint8')~=numel(bytes), error('achcapture:short_write','Short metadata write'); end
catch failure
    primary=failure;
end
primary=close_reader_writer(fid,primary);
if ~isempty(primary), rethrow(primary); end
sync_file(path); d=dir(path);
if numel(d)~=1 || d.bytes~=numel(bytes), error('achcapture:extent','Metadata extent mismatch'); end
descriptor=struct('path',name,'bytes',numel(bytes),'sha256',sha_file(path,numel(bytes)));
end

function exclusive(path)
% The parent must provide a fresh private directory with no concurrent writers.
% Java creates the new name exclusively; a subsequent open is not a substitute
% for that ownership assumption or for independent post-run custody checks.
f=java.io.File(path);
if ~f.createNewFile(), error('achcapture:collision','Owned output already exists'); end
end

function sync_file(path)
f=java.io.RandomAccessFile(path,'rw'); primary=[];
try, f.getFD().sync(); catch failure, primary=failure; end
try, f.close(); catch failure
    if isempty(primary), primary=failure; else, primary=addCause(primary,failure); end
end
if ~isempty(primary), rethrow(primary); end
% Parent-directory fsync is deliberately not asserted by this MATLAB sink.
end

function value=sha_file(path,expected)
md=java.security.MessageDigest.getInstance('SHA-256');
fid=fopen(path,'r');
if fid<0, error('achcapture:hash_open','Cannot reopen closed owned output'); end
primary=[];
try
    remaining=expected;
    while remaining>0
        requested=min(65536,remaining);
        bytes=fread(fid,requested,'*uint8');
        if numel(bytes)~=requested, error('achcapture:hash_short','Owned output hash short read'); end
        md.update(typecast(bytes,'int8'));
        remaining=remaining-requested;
    end
    if ~isempty(fread(fid,1,'*uint8')), error('achcapture:hash_growth','Owned output grew during hash'); end
    [~,errnum]=ferror(fid);
    if errnum~=0, error('achcapture:hash_read','Owned output hash read failed'); end
catch failure
    primary=failure;
end
primary=close_reader_writer(fid,primary);
if ~isempty(primary), rethrow(primary); end
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
end

function primary=close_reader_writer(fid,primary)
try
    if fclose(fid)~=0, error('achcapture:close','Owned descriptor close failed'); end
catch failure
    if isempty(primary), primary=failure; else, primary=addCause(primary,failure); end
end
end

function [records,st]=graphics_numeric(st)
% Fresh-worker figures only, selected numerical properties. Not visual parity.
objects=findall(groot); records=cell(1,numel(objects));
names={'XData','YData','ZData','CData','SizeData','XNegativeDelta', ...
    'XPositiveDelta','YNegativeDelta','YPositiveDelta','Value','String', ...
    'XLim','YLim','ZLim'};
for j=1:numel(objects)
    r=struct('graphics_class',class(objects(j)),'property_order',{{}},'properties',{{}});
    for k=1:numel(names)
        if isprop(objects(j),names{k})
            value=get(objects(j),names{k});
            [node,st]=encode(value,st,0);
            r.property_order{end+1}=names{k};r.properties{end+1}=node;
        end
    end
    records{j}=r;
end
end
