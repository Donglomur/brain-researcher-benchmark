function [packet, subjLearnR] = export_subject_stage(T3, dtSubjACC, input_identity)
% Export the original downstream MATLAB stage; this file is not parity-qualified.
% Inputs are native original-stage tables, NOT outputs reconstructed by this API.
% input_identity hashes are caller declarations, not file authentication.
assert(istable(T3) && istable(dtSubjACC), 'Native tables required');
assert(isequal(T3.Properties.VariableNames, ...
    {'channel','phase','GroupCount','fun1_trial_ripple'}), 'Exact T3 columns');
assert(height(T3)>0 && height(T3)<=1000000, 'Bounded nonempty T3');
assert(all(ismember({'subject','testBeforeInfer','testBeforeMemory'}, ...
    dtSubjACC.Properties.VariableNames)), 'Original performance columns');
assert(height(dtSubjACC)>0 && height(dtSubjACC)<=1000000, 'Bounded performance');
channels = textcells(T3.channel); phaseids = textcells(T3.phase);
performance_ids = textcells(dtSubjACC.subject);
phases = {'stimulus','feedback','interval'};
% This adapter explicitly supports all three columns; it never invents one.
assert(isequal(sort(unique(phaseids)),sort(phases')), 'Three-phase adapter domain');
assert(height(unique(T3(:,{'channel','phase'})))==height(T3), 'Unique groups');
assert(isa(T3.fun1_trial_ripple,'double') && iscolumn(T3.fun1_trial_ripple));
assert(isa(T3.GroupCount,'double') && iscolumn(T3.GroupCount));
assert(isa(dtSubjACC.testBeforeInfer,'double') && iscolumn(dtSubjACC.testBeforeInfer));
assert(isa(dtSubjACC.testBeforeMemory,'double') && iscolumn(dtSubjACC.testBeforeMemory));
assert(isstruct(input_identity) && isscalar(input_identity));
assert(isequal(sort(fieldnames(input_identity)), ...
    sort({'learnr_input_sha256';'performance_input_sha256'})));
for f = fieldnames(input_identity)'
    assert(ischar(input_identity.(f{1})) && ...
        ~isempty(regexp(input_identity.(f{1}),'^[0-9a-f]{64}$','once')));
end
before = T3; flagged = false(height(T3),1);
% Author Ripple_offline_learning.m lines78-84, with mask observation only.
phases = {'stimulus' 'feedback' 'interval'};
for i = 1:3
    indpha = find(ismember(T3.phase,phases{i}));
    [~,ind]=rmoutliers(T3.fun1_trial_ripple(indpha),"mean","ThresholdFactor",3);
    ind = find(ind);
    flagged(indpha(ind)) = true; % observation; does not enter author reduction
    T3.fun1_trial_ripple(indpha(ind))=nan;
end
after = T3;
% Author lines87-93, unchanged operations; capture before channel deletion.
T3.GroupCount=[];
T3m = unstack(T3,"fun1_trial_ripple",'phase');
wide = T3m;
T3m.subject = regexprep(T3m.channel,'.*_','');  T3m.channel=[];
mapped_subjects = textcells(T3m.subject);
subjLearnR = grpstats(T3m,{'subject'},@nanmean);
subjLearnR.Properties.VariableNames = strrep(subjLearnR.Properties.VariableNames,'nanmean_','');
subjects = subjLearnR;
% Author lines96-101. Extra learned subjects can be excluded by this join.
[~,ia,ib]= intersect(dtSubjACC.subject,subjLearnR.subject,'stable');
subjLearnR = subjLearnR(ib,:);
assert(isequal(ia,(1:height(dtSubjACC))'))
subjLearnR.eleInfer_perf = dtSubjACC.testBeforeInfer;
subjLearnR.eleMemory_perf= dtSubjACC.testBeforeMemory;

packet.schema = 'ripple-subject-native-export/v1';
packet.source.revision = 'f143b0b7dca77bf9b09d5c7f39352fc5332c83c0';
packet.source.caller_sha256 = '15969cc29b6d7d28d4d4700a044454092149b688c6af9c552314a8cbff2ce6bc';
packet.source.operations = 'Ripple_offline_learning.m:77-101';
packet.input_identity = input_identity;
packet.runtime.matlab_version = version;
packet.runtime.rmoutliers_which = which('rmoutliers');
packet.runtime.grpstats_which = which('grpstats');
packet.runtime.nanmean_which = which('nanmean');
packet.channels = cell(height(before),1);
for n = 1:height(before)
    r = struct('row_id',n,'channel',channels{n},'phase',phaseids{n}, ...
        'group_count',before.GroupCount(n),'before',scalar(before.fun1_trial_ripple(n)), ...
        'after',scalar(after.fun1_trial_ripple(n)),'outlier',flagged(n));
    packet.channels{n} = r;
end
wide_channels = textcells(wide.channel);
packet.wide = cell(height(wide),1);
for n = 1:height(wide)
    packet.wide{n} = struct('row_id',n,'channel',wide_channels{n}, ...
        'subject',mapped_subjects{n},'values',values(wide,n));
end
subject_ids = textcells(subjects.subject);
packet.subjects = cell(height(subjects),1);
for n = 1:height(subjects)
    packet.subjects{n} = struct('row_id',n,'subject',subject_ids{n}, ...
        'group_count',subjects.GroupCount(n),'values',values(subjects,n));
end
packet.performance = cell(height(dtSubjACC),1);
for n = 1:height(dtSubjACC)
    packet.performance{n} = struct('row_id',n,'subject',performance_ids{n}, ...
        'inference',scalar(dtSubjACC.testBeforeInfer(n)), ...
        'memory',scalar(dtSubjACC.testBeforeMemory(n)));
end
packet.join.ia = num2cell(ia(:)); packet.join.ib = num2cell(ib(:));
packet.join.excluded_subject_row_ids = num2cell(find(~ismember((1:height(subjects))',ib)));
packet.joined = cell(height(subjLearnR),1);
joined_ids = textcells(subjLearnR.subject);
for n = 1:height(subjLearnR)
    packet.joined{n} = struct('row_id',n,'subject_row_id',ib(n), ...
        'subject',joined_ids{n},'values',values(subjLearnR,n), ...
        'inference',scalar(subjLearnR.eleInfer_perf(n)), ...
        'memory',scalar(subjLearnR.eleMemory_perf(n)));
end
packet.native_tables.before = metadata(before);
packet.native_tables.after = metadata(after);
packet.native_tables.wide = metadata(wide);
packet.native_tables.subjects = metadata(subjects);
packet.native_tables.performance = metadata(dtSubjACC);
packet.native_tables.joined = metadata(subjLearnR);
% Caller may jsonencode(packet); explicit scalar states preserve NaN/+Inf/-Inf.
% No CSV, source-input file read, R call, fit, score or paper decision occurs here.
end

function result = textcells(column)
assert((iscellstr(column) || isstring(column)) && iscolumn(column));
if isstring(column), assert(~any(ismissing(column))); result=cellstr(column); else, result=column; end
for k=1:numel(result)
    assert(isrow(result{k}) && ~isempty(result{k}) && numel(result{k})<=256);
    assert(~any(ismember(result{k},[char(0),char(10),char(13)])), 'Single-line identity');
end
end

function result = scalar(x)
assert(isa(x,'double') && isreal(x) && isscalar(x));
if isnan(x), result=struct('state','nan');
elseif x==inf, result=struct('state','positive_infinity');
elseif x==-inf, result=struct('state','negative_infinity');
else, result=struct('state','finite','value',x);
end
end

function result = values(t,n)
result=struct;
for p={'stimulus','feedback','interval'}, result.(p{1})=scalar(t.(p{1})(n)); end
end

function result = metadata(t)
result.columns = t.Properties.VariableNames(:);
result.classes = cell(numel(result.columns),1);
for k=1:numel(result.columns), result.classes{k}=class(t.(result.columns{k})); end
result.row_names = t.Properties.RowNames(:);
result.height = height(t);
end
