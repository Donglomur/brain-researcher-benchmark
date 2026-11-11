function export_source(dataDir, outDir)
% Deterministic source projection only. Do not run MainData.m or its fitting code.
% No execution occurred during construction; both original MAT parts are absent.
assert(~isfolder(outDir) && ~isfile(outDir), 'Fresh output directory required');
names = {'mainData1.mat','mainData2.mat'};
md5s = {'f2d3b27ebbbd99a58c6ff62e8b473a58','1f163dee80ad4baf1574e581954f0213'};
for k=1:2
    assert(strcmp(digest(fullfile(dataDir,names{k}),'MD5'),md5s{k}), 'Original MAT identity');
end
a=load(fullfile(dataDir,names{1})); b=load(fullfile(dataDir,names{2}));
assert(isfield(a,'micedats1') && isfield(b,'micedats2'), 'Both complete MAT partitions');
micedats=cat(1,a.micedats1,b.micedats2);
if isfield(a,'dirTable'), tab=a.dirTable; else, assert(isfield(b,'dirTable')); tab=b.dirTable; end
if isfield(a,'dirTable') && isfield(b,'dirTable'), assert(isequaln(a.dirTable,b.dirTable),'Conflicting dirTable'); end
assert(height(tab)==numel(micedats),'Complete session table');
dirs=string(tab.DA_Dir); alt=string(tab.Alt_Delay_Dir);
selected=find(tab.Delay==2 & string(tab.GrCs)=="Y");
selected=selected(arrayfun(@(i)isfield(micedats{i},'chronicGreen'),selected));
assert(~isempty(selected),'No declared registered-delay cohort');
census=struct([]);
for k=1:numel(micedats)
    isgrc=string(tab.GrCs(k))=="Y"; hasch=isfield(micedats{k},'chronicGreen');
    delay=double(tab.Delay(k)); assert(isscalar(delay) && isfinite(delay),'Finite planned delay');
    if ~isgrc, disposition='outside_GrC_scope';
    elseif delay~=2, disposition='not_two_second_target';
    elseif ~hasch, disposition='no_chronicGreen_registration';
    else, disposition='required_registered_target'; end
    census(k)=struct('session_index1',k,'is_grc',logical(isgrc),'delay_s',delay,...
        'has_chronic_green',logical(hasch),'disposition',disposition);
end
records=struct([]); total=0;
for j=1:numel(selected)
    ti=selected(j); si=find(dirs==alt(ti));
    assert(isscalar(si) && tab.Delay(si)==1 && string(tab.GrCs(si))=="Y",'Unique 1-second source session');
    sm=mouse(dirs(si)); tm=mouse(dirs(ti));
    assert(sm==tm && string(tab.DAType(si))==string(tab.DAType(ti)), 'Within-mouse and reward-type pair');
    assert(ismember(string(tab.DAType(ti)),["DAT","MFB"]),'Required pair outside selected DAT/MFB type');
    s=micedats{si}; t=micedats{ti};
    matches=double(t.chronicGreen.finalMatchesMat);
    assert(size(matches,2)==2 && all(isfinite(matches),'all') && all(matches>=0,'all') && all(matches==fix(matches),'all'),'Registration matrix');
    maxima=max(matches,[],1);
    tc=find(maxima==t.nc_right_green); sc=find(maxima==s.nc_right_green);
    assert(isscalar(tc) && isscalar(sc) && tc~=sc,'Ambiguous registration orientation');
    for c=1:2, v=matches(matches(:,c)>0,c); assert(numel(unique(v))==numel(v),'Repeated positive registration cell'); end
    allmatches=matches(:,[sc tc]);
    valid=all(matches>0,2); matches=matches(valid,:);
    assert(~isempty(matches) && all(matches(:,sc)<=s.nc_right_green) && all(matches(:,tc)<=t.nc_right_green),'Complete positive matched-cell inventory');
    [sx,st]=extract(s,matches(:,sc)); [tx,tt]=extract(t,matches(:,tc));
    assert(size(sx,1)>=5 && size(tx,1)>=1,'Full source/target trial support');
    total=total+8*(numel(sx)+numel(tx));
    assert(total<=150000000,'Complete source projection exceeds prospective byte cap; do not shrink cohort');
    records(j).pair_index1=j; records(j).source_session_index1=si; records(j).target_session_index1=ti;
    records(j).mouse_id=char(sm); records(j).reward_type=char(string(tab.DAType(ti)));
    records(j).registration_rows_source_target=arrayfun(@(k)allmatches(k,:),1:size(allmatches,1),'UniformOutput',false);
    records(j).source_cells_index1=matches(:,sc)'; records(j).target_cells_index1=matches(:,tc)';
    records(j).source_shape=[size(sx,1),size(sx,2),size(sx,3)]; records(j).target_shape=[size(tx,1),size(tx,2),size(tx,3)];
    records(j).source_time_seconds=st; records(j).target_time_seconds=tt;
end
mkdir(outDir);
for j=1:numel(records)
    r=records(j); [sx,~]=extract(micedats{r.source_session_index1},r.source_cells_index1);
    [tx,~]=extract(micedats{r.target_session_index1},r.target_cells_index1);
    sn=sprintf('pair%04d_source.f64',j); tn=sprintf('pair%04d_target.f64',j);
    writebin(fullfile(outDir,sn),sx); writebin(fullfile(outDir,tn),tx);
    records(j).source_file=struct('path',sn,'bytes',8*numel(sx),'sha256',digest(fullfile(outDir,sn),'SHA-256'));
    records(j).target_file=struct('path',tn,'bytes',8*numel(tx),'sha256',digest(fullfile(outDir,tn),'SHA-256'));
end
index=struct('schema','neural029-raw-projection-v2','source_record','21645651',...
    'complete_selected_cohort',true,'source_part_count',2,'source_session_count',numel(micedats),...
    'selected_target_session_indices1',selected(:)','pairs',records,'scientific_fits',0,'scientific_scores',0);
index.cohort_dispositions=num2cell(census);
index.pairs=num2cell(records); % Preserve JSON list identity even for one pair.
index.selected_target_session_indices1=num2cell(selected(:)');
fid=fopen(fullfile(outDir,'INDEX.json'),'w'); assert(fid>0); clean=onCleanup(@()fclose(fid));
fwrite(fid,jsonencode(index),'char');
end

function m=mouse(path)
parts=split(path,"\"); assert(numel(parts)>=2); m=parts(end-1); assert(strlength(m)>0);
end

function [x,clock]=extract(s,cells)
assert(isfield(s,'endAlgn') && isfield(s.endAlgn,'sigFilt_right_green') && isfield(s,'tmpx_right'));
clock=double(s.tmpx_right(:)');
assert(all(isfinite(clock)) && all(diff(clock)>0) && clock(1)<=0 && clock(end)>=3,'Native clock support');
lo=find(clock<=0,1,'last'); hi=find(clock>=3,1,'first');
full=s.endAlgn.sigFilt_right_green;
assert(size(full,2)==s.nc_right_green && size(full,3)==numel(clock),'Trial-cell-time source geometry');
x=double(full(:,cells,lo:hi)); clock=clock(lo:hi);
assert(all(isfinite(x),'all'),'Nonfinite required calcium: report source gap, do not filter cells or trials');
end

function writebin(path,x)
fid=fopen(path,'w','ieee-le'); assert(fid>0); clean=onCleanup(@()fclose(fid));
assert(fwrite(fid,permute(x,[3 2 1]),'double')==numel(x),'Complete C-order binary');
end

function value=digest(path,algorithm)
md=java.security.MessageDigest.getInstance(algorithm);
fid=fopen(path,'r'); assert(fid>0); clean=onCleanup(@()fclose(fid));
while true
    x=fread(fid,1048576,'*uint8'); if isempty(x), break; end
    md.update(typecast(x,'int8'));
end
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2)',1,[]));
end
