function export_WB_fields(inputFile, outputFile, maxExpandedBytes)
% Future deterministic operator conversion, no fits or scientific scores.
% Requires independently authenticated exact WT source before this call.
% Real MAT format/rows/clock have not been inspected for this task.
assert(~isfile(outputFile), 'Fresh output only');
assert(maxExpandedBytes > 0 && maxExpandedBytes <= 2^31, 'Explicit selected decoded bound');
info = whos('-file', inputFile, 'wbData');
assert(numel(info)==1 && strcmp(info.class,'struct') && info.bytes<=maxExpandedBytes, 'Bounded WB struct census before load');
assert(prod(info.size)>=3 && prod(info.size)<=256, 'Bounded full WT recording roster');
v = load(inputFile,'wbData');
w = v.wbData; rows = cell(1,numel(w));
for i=1:numel(w)
    r=w(i);
    assert(all(isfield(r,{'Name','velocity','reversal_vec','dv','gcamp_wIDs'})), 'Exact author WB fields');
    n=numel(r.velocity); assert(n>=3 && n<=1000000, 'Bounded full recording');
    assert(isnumeric(r.velocity) && isreal(r.velocity) && isnumeric(r.dv) && isreal(r.dv) && isnumeric(r.reversal_vec) && isreal(r.reversal_vec));
    assert(numel(r.dv)==n && numel(r.reversal_vec)==n && all(ismember(r.reversal_vec(:),[0,1])));
    % MATLAB adds empty numeric fields to other struct rows when an identity
    % field is assigned only in rows with a neuron-id text file. Preserve the
    % missing-identity case as an explicit no-SAAV exclusion, not a guessed ID.
    assert(isempty(r.gcamp_wIDs) || (iscell(r.gcamp_wIDs) && size(r.gcamp_wIDs,2)==2 && size(r.gcamp_wIDs,1)<=1000));
    matches={};
    for j=1:size(r.gcamp_wIDs,1)
        name=r.gcamp_wIDs{j,1};
        if (ischar(name)||isstring(name)) && strcmp(string(name),"SAAV")
            trace=r.gcamp_wIDs{j,2};
            assert(isnumeric(trace) && isreal(trace) && numel(trace)==n, 'Exact full SAAV trace');
            matches{end+1}=struct('name','SAAV','row_index1',j,'trace',reshape(double(trace),1,[])); %#ok<AGROW>
        end
    end
    assert(numel(matches)<=1,'Ambiguous SAAV identity; never select by prediction');
    rows{i}=struct('Name',char(string(r.Name)),'velocity',reshape(double(r.velocity),1,[]),...
        'reversal_vec',reshape(double(r.reversal_vec),1,[]),'dv',reshape(double(r.dv),1,[]),...
        'saav_matches',{matches});
end
pin=struct('bytes',236931813,'sha256','4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45');
out=struct('schema','neural047-wb-fields-v1','source_pin',pin,'rows',{rows});
body=jsonencode(out,'ConvertInfAndNaN',true); % missing samples become explicit null, never zero
assert(strlength(string(body))<=64000000,'Bounded complete normalized field export');
assert(~isfile(outputFile),'Fresh operator-owned output');
fid=fopen(outputFile,'w','n','UTF-8'); assert(fid>=0); cleaner=onCleanup(@()fclose(fid));
fwrite(fid,body,'char');
end
