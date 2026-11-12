function native_baseline(packageRoot, outputRoot)
% Future operator-only scientific run. NOT executed during package building.
% Uses only sanitized public metadata and original extracted waveforms.
% Requires an empty output location and licensed MATLAB/toolboxes.
assert(~exist(outputRoot,'dir') && ~exist(outputRoot,'file'), 'Fresh output required');
mkdir(outputRoot);
addpath(genpath(fullfile(packageRoot,'private','author_source','MATLAB')));
C=jsondecode(fileread(fullfile(packageRoot,'public','cohort.json')));
folds=struct([]);
for mi=1:5
    mouse=C.mice(mi);
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
    % Verify every required pre-extracted waveform before entering author code.
    units=mouse.units;
    for ui=1:numel(units)
        assert(isfile(fullfile(UMparam.KSDir{units(ui).session},'RawWaveforms',sprintf('Unit%d_RawSpikes.npy',units(ui).cluster_id))), 'Missing waveform');
    end
    [~,T,~,~]=UnitMatch(clusinfo,UMparam);
    % The benchmark applies its own documented two-day decoder equally to
    % baseline and candidate; no multi-session UID grouping is substituted.
    n=numel(units); P=nan(n,n);
    for ri=1:height(T)
        ii=find([units.session]==T.RecSes1(ri) & [units.cluster_id]==T.ID1(ri));
        jj=find([units.session]==T.RecSes2(ri) & [units.cluster_id]==T.ID2(ri));
        assert(numel(ii)==1 && numel(jj)==1, 'Unit identity mismatch');
        P(ii,jj)=T.MatchProb(ri);
    end
    assert(all(isfinite(P),'all') && all(P>=0 & P<=1,'all'), 'Invalid baseline probabilities');
    folds(mi).held_out_mouse=mouse.mouse_id;
    allNames={'Mouse1','Mouse2','Mouse3','Mouse4','Mouse5'};
    folds(mi).development_mice=allNames(~strcmp(allNames,mouse.mouse_id));
    folds(mi).probabilities=P;
end
result=struct('schema','unitmatch_submission_v1','access_view','B', ...
    'method_name','UnitMatch v2.0 native MATLAB, seed 0, source-conditioned five-mouse demo','folds',folds);
fid=fopen(fullfile(outputRoot,'baseline.json'),'w'); assert(fid>=0); cleanup=onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(result));
end
