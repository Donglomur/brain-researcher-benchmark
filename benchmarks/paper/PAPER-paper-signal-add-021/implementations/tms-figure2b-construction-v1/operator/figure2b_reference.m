function figure2b_reference(config_file)
% Future trusted numerical reference. No plotting, clusters or inference.
C=jsondecode(fileread(config_file)); I=C.identity;
assert(isequal(double(I.shape(:))',[62 53 200 15]));
assert(strcmp(I.schema,'tms_figure2b_source_position_identity_v1'));
A=I.participant_axis_identity;
assert(strcmp(A.kind,'released_array_positions') && isequal(double(A.positions(:))',0:14));
assert(isequal(A.physical_id_map_verified,false) && isequal(A.source_order_preserved,true));
assert(strcmp(I.provenance.endpoint,'released_artifact_group_topography'));
assert(strcmp(I.provenance.units_interpretation,'dB_as_used_by_published_operator'));
assert(strcmp(I.provenance.storage,'MATLAB-double'));
assert(isequal(I.provenance.upstream_preprocessing_verified,false));
assert(isequal(I.provenance.paired_person_inference_admitted,false));
addpath(C.fieldtrip_root); ft_defaults;
% Resolve the exact path-selected implementation, not an unrelated shadow.
assert(strcmp(which('ft_math'),fullfile(C.fieldtrip_root,'ft_math.m')));
assert(strcmp(which('nearest'),fullfile(C.fieldtrip_root,'utilities','nearest.m')));
% Explicit selected FieldTrip statistics helpers, rather than toolbox defaults.
addpath(fullfile(C.fieldtrip_root,'external','stats'),'-begin');
assert(strcmp(which('nanmean'),fullfile(C.fieldtrip_root,'external','stats','nanmean.m')));
assert(strcmp(which('nansum'),fullfile(C.fieldtrip_root,'external','stats','nansum.m')));
support=load(C.layout,'lay');assert(all(ismember(I.labels(:),support.lay.label(:))));
% Layout mapping is by label, never by neighbor or layout row position.
assert(~isfolder(C.output)); mkdir(C.output);
loaded=load(C.derivative,'mTFR'); original=loaded.mTFR;
conds={'NT','T'}; locations={'pin','pout'};
fields=struct(); descriptions=struct();
for ci=1:2
 for li=1:2
  cond=conds{ci}; loc=locations{li}; D=original.(cond).(loc).all;
  assert(isa(D.powspctrm,'double') && isreal(D.powspctrm));
  assert(isequal(size(D.powspctrm),[62 53 200 15]));
  assert(isequal(double(D.freq(:)),double(I.frequency(:))) && isequal(double(D.time(:)),double(I.time(:))));
  assert(isequal(D.label(:),I.labels(:)));
  values=D.powspctrm;
  support=uint16(zeros(62,53,200));
  for position=1:15
   support=bitor(support,uint16(~isnan(values(:,:,:,position))).*uint16(2^(position-1)));
  end
  contributors=uint8(sum(~isnan(values),4));
  D.powspctrm=mean(values,4,'omitnan');
  D.dimord='chan_freq_time';
  averaged.(cond).(loc)=D;
  stem=['mean.' cond '.' loc '.all.'];
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'value'],D.powspctrm,'f8',[62 53 200]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'undefined'],uint8(isnan(D.powspctrm)),'u1',[62 53 200]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'positions'],support,'u2',[62 53 200]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'contributors'],contributors,'u1',[62 53 200]);
 end
end
cfg=[];cfg.parameter='powspctrm';
cfg.operation='(10^(x2/10) - 10^(x1/10)) / (10^(x1/10) + 10^(x2/10))';
windows={[.5 1.5],[3 4]};wnames={'delay1','delay2'};
for ci=1:2
 cond=conds{ci}; contrast=ft_math(cfg,averaged.(cond).pin,averaged.(cond).pout);
 assert(isequal(contrast.label(:),I.labels(:)) && isequal(contrast.freq(:),I.frequency(:)) && isequal(contrast.time(:),I.time(:)));
 [fields,descriptions]=emit(fields,descriptions,C.output,['normalized.' cond '.value'],contrast.powspctrm,'f8',[62 53 200]);
 [fields,descriptions]=emit(fields,descriptions,C.output,['normalized.' cond '.undefined'],uint8(isnan(contrast.powspctrm)),'u1',[62 53 200]);
 f=nearest(contrast.freq,8):nearest(contrast.freq,12);
 for wi=1:2
  w=windows{wi};t=nearest(contrast.time,w(1)):nearest(contrast.time,w(2));
  selected=contrast.powspctrm(:,f,t);
  time_support=uint16(sum(~isnan(selected),3));
  intermediate=nanmean(selected,3);
  frequency_support=uint8(sum(~isnan(intermediate),2));
  topo=nanmean(intermediate,2);
  stem=['window.' cond '.' wnames{wi} '.'];
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'value'],topo,'f8',[62]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'undefined'],uint8(isnan(topo)),'u1',[62]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'time_contributors'],time_support,'u2',[62 numel(f)]);
  [fields,descriptions]=emit(fields,descriptions,C.output,[stem 'frequency_contributors'],frequency_support,'u1',[62]);
 end
end
% JSON object keys include dots, so assemble a deterministic raw field object.
keys=fieldnames(descriptions);pairs=cell(numel(keys),1);
for k=1:numel(keys),r=descriptions.(keys{k});pairs{k}=[jsonencode(r.name) ':' jsonencode(r.spec)];end
manifest=['{"schema":"tms_figure2b_source_position_full_output_v1","identity":' jsonencode(I) ',"producer":"pinned-FieldTrip-20220104-reference","fields":{' strjoin(pairs,',') '}}'];
assert(~isfile(fullfile(C.output,'OUTPUT.json')));fid=fopen(fullfile(C.output,'OUTPUT.json'),'w');assert(fid>=0);closer=onCleanup(@()fclose(fid));fwrite(fid,unicode2native(manifest,'UTF-8'),'uint8');clear closer;
end
function [fields,descriptions]=emit(fields,descriptions,root,name,value,kind,shape)
assert(numel(value)==prod(shape));
if strcmp(kind,'f8'),precision='double';elseif strcmp(kind,'u2'),precision='uint16';else,precision='uint8';end
path=fullfile(root,[name '.bin']);assert(~isfile(path));fid=fopen(path,'w','ieee-le');assert(fid>=0);closer=onCleanup(@()fclose(fid));
% MATLAB column-major traversal of reversed dimensions equals declared C order.
fwrite(fid,permute(value,ndims(value):-1:1),precision);clear closer;
fid=fopen(path,'r');closer=onCleanup(@()fclose(fid));body=fread(fid,inf,'*uint8');clear closer;
md=java.security.MessageDigest.getInstance('SHA-256');md.update(body);hex=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2)',1,[]));
key=sprintf('field%d',numel(fieldnames(descriptions))+1);
% Force shape to JSON array even for channel-only vectors.
spec=struct('shape',{num2cell(shape)},'dtype',kind,'bytes',numel(body),'sha256',hex);
descriptions.(key)=struct('name',name,'spec',spec);fields.(key)=name;
end
