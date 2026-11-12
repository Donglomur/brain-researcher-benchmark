function unitmatch_native_capture(packageRoot, outputRoot)
% Source-owned future baseline; MATLAB execution is not qualified by this file.
% Scientific parameter setup/call are preserved from native_baseline.m
% SHA256 4f4bbec46506d3fbb5adbe90ef7c35c669275bcd3210b25852eab9f38eb1d6db.
% Derived from the existing UnitMatch adapter; retain author CC BY-NC-SA 4.0
% attribution/license notices. No new license is granted by this successor.
assert(~exist(outputRoot,'dir') && ~exist(outputRoot,'file'), 'Fresh output required');
mkdir(outputRoot);
addpath(genpath(fullfile(packageRoot,'private','author_source','MATLAB')));
C=jsondecode(fileread(fullfile(packageRoot,'public','cohort.json')));
assert(numel(C.mice)==5, 'Exactly five mice required');
allNames={'Mouse1','Mouse2','Mouse3','Mouse4','Mouse5'};
expectedCounts=[534,109,96,59,466];
observed=struct('schema','unitmatch_native_completion_v1','official_commit', ...
    '6ef0023cb4a7be0a94dabbab24bb79c084b6fb1e','matlab_version',version, ...
    'unitmatch_function',which('UnitMatch'),'parameters_function',which('DefaultParametersUnitMatch'), ...
    'npy_function',which('readNPY'),'mouse_ids',{allNames},'unit_counts',expectedCounts,'seed',0);
observed.toolboxes=ver;
sourcePrefix=[fullfile(packageRoot,'private','author_source','MATLAB') filesep];
dispatchNames={'unitmatch_function','parameters_function','npy_function'};
for fi=1:numel(dispatchNames)
    resolved=observed.(dispatchNames{fi});
    assert(startsWith(resolved,sourcePrefix) && isfile(resolved), 'MATLAB dispatch outside locked author source');
end
for mi=1:5
    mouse=C.mice(mi);
    assert(strcmp(mouse.mouse_id,allNames{mi}), 'Mouse order mismatch');
    assert(numel(mouse.sessions)==2, 'Two sessions required');
    rng(0,'twister');
    clusinfo=struct('cluster_id',[],'Good_ID',[],'RecSesID',[],'ProbeID',[],'Shank',[],'depth',[]);
    UMparam=struct();
    for si=1:2
        session=mouse.sessions(si); meta=session.cluster_metadata;
        names={'cluster_id','Good_ID','ProbeID','Shank','depth'};
        for fi=1:numel(names)
            name=names{fi}; clusinfo.(name)=[clusinfo.(name); meta.(name)(:)];
        end
        clusinfo.RecSesID=[clusinfo.RecSesID; si*ones(numel(meta.cluster_id),1)];
        UMparam.KSDir{si}=fullfile(packageRoot,'public',session.data_dir);
        UMparam.AllChannelPos{si}=readNPY(fullfile(UMparam.KSDir{si},'channel_positions.npy'));
    end
    UMparam.SaveDir=fullfile(outputRoot,mouse.mouse_id);
    UMparam.RawDataPaths={'',''}; UMparam.AllDecompPaths={'',''};
    UMparam=DefaultParametersUnitMatch(UMparam);
    UMparam.RedoExtraction=0; UMparam.GoodUnitsOnly=1; UMparam.MakePlotsOfPairs=0; UMparam.GUI=0;
    units=mouse.units;
    for ui=1:numel(units)
        assert(isfile(fullfile(UMparam.KSDir{units(ui).session},'RawWaveforms',sprintf('Unit%d_RawSpikes.npy',units(ui).cluster_id))), 'Missing waveform');
    end
    [~,T,~,~]=UnitMatch(clusinfo,UMparam);
    % Capture-only successor: no score, decoder, grouping, or threshold change.
    n=numel(units);
    assert(n==expectedCounts(mi) && height(T)==n*n, 'Incomplete pair table');
    assert(size(unique([[units.session]',[units.cluster_id]'],'rows'),1)==n, 'Duplicate unit identity');
    seen=false(n,n);
    for ri=1:height(T)
        ii=find([units.session]==T.RecSes1(ri) & [units.cluster_id]==T.ID1(ri));
        jj=find([units.session]==T.RecSes2(ri) & [units.cluster_id]==T.ID2(ri));
        assert(numel(ii)==1 && numel(jj)==1, 'Unit identity mismatch');
        assert(~seen(ii,jj), 'Duplicate directed pair');
        seen(ii,jj)=true;
    end
    assert(all(seen,'all'), 'Missing directed pair');
    assert(isnumeric(T.MatchProb) && all(isfinite(T.MatchProb),'all') && all(T.MatchProb>=0 & T.MatchProb<=1,'all'), 'Invalid baseline probabilities');
    tableCapture=struct('schema','unitmatch_native_pairs_v1','mouse_id',mouse.mouse_id, ...
        'unit_count',n,'row_count',height(T),'seed',0,'units',units, ...
        'session1',T.RecSes1(:)','cluster1',T.ID1(:)', ...
        'session2',T.RecSes2(:)','cluster2',T.ID2(:)','probability',T.MatchProb(:)');
    writeJSON(fullfile(outputRoot,[mouse.mouse_id '.pairs.json']),tableCapture);
end
% Marker is written only after all five complete table captures.
writeJSON(fullfile(outputRoot,'completion.json'),observed);
end

function writeJSON(path,value)
assert(~exist(path,'file') && ~exist(path,'dir'),'Fresh product required');
fid=fopen(path,'w'); assert(fid>=0,'Cannot create native product');
cleanup=onCleanup(@()fclose(fid));
count=fprintf(fid,'%s\n',jsonencode(value));
[~,errorNumber]=ferror(fid);
assert(count>0 && errorNumber==0,'Cannot write complete native product');
end
