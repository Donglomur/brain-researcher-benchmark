function products = native_dispatch(request)
% Authored/static only. Execute only inside a qualified independent reference
% environment, with source-compatible input roles and exact native bindings.
% Original author files are copied verbatim; no mutation of the native methods.
addpath(genpath(request.author_source));
out = request.output_root;
if ~exist(out,'dir'), mkdir(out); end
products = struct();
switch request.operation
 case 'behavior_full_349_expert_first15_models'
  processBehaviorData(request.behavior_root,request.author_source,[out filesep]);
  products.expert = load(fullfile(out,'expert.mat'));
  products.naive = load(fullfile(out,'naive.mat'));
  products.inference = load(fullfile(out,'infModel.mat'));
  products.divisive = load(fullfile(out,'divModel.mat'));
 case 'muscimol_full_nine_pairs'
  processMuscimolData(request.muscimol_root,request.author_source,[out filesep]);
  products.control = load(fullfile(out,'control.mat'));
  products.muscimol = load(fullfile(out,'muscimol.mat'));
 case 'acute_native_distance_mutation'
  products.acute = muscimolPhysiology(request.acute_root);
  products.policy = 'native_original_single_subscript_distance_writes';
 case 'all_event_responses_by_area'
  products.areas = cell(size(request.area_roots));
  for a=1:length(request.area_roots)
   folder=fullfile(out,sprintf('area_%d',a));mkdir(folder);
   processEphysData(request.area_roots{a},request.author_source,[folder filesep]);
   products.areas{a}=load(fullfile(folder,'incongruentResponses.mat'));
  end
 case 'tca_full_expert_naive'
  assert(length(request.group_roots)==2,'Both expert and naive are required');
  products.groups=cell(1,2);
  for g=1:2
   folder=fullfile(out,sprintf('tca_%d',g));mkdir(folder);
   makeTensor_TCA(request.group_roots{g},[folder filesep]);
   tensorFile=load(fullfile(folder,'timeblockTensor.mat'));
   info=load(fullfile(folder,'block_tensorInfo.mat'));
   errors=TCA_chooseRank(tensorFile.data,[folder filesep]);
   [model,IDmap]=runTCA(tensorFile.data,8,{'neurons','time','blocks'},0);
   products.groups{g}=struct('rank_errors',errors,'tensor',tensorFile.data,...
    'original_neuron_map',info,'model',model,'IDmap',IDmap);
  end
 case 'signed_native_all_event_prepost'
  assert(length(request.contexts)==6,'F3 F4 F7low F7high S6 S7 contexts');
  products.contexts=cell(1,6);
  for c=1:6
   x=request.contexts{c};result=struct();
   for e=1:length(x.events)
    event=x.events{e};pre=cell(1,length(event.xvec));post=pre;
    for j=1:length(event.xvec)
     b=event.xvec(j);
     [pre{j}.p,pre{j}.null]=permute_test(event.pre_nonpref(:,b),event.pre_pref(:,b),1000,1);
     [post{j}.p,post{j}.null]=permute_test(event.post_nonpref(:,b),event.post_pref(:,b),1000,1);
    end
    result.events{e}=struct('pre',{pre},'post',{post},'physical_group_map',event.physical_group_map);
   end
   products.contexts{c}=result;
  end
 case 'all_dprime_groups'
  products.groups=cell(size(request.group_roots));
  for g=1:length(request.group_roots)
   folder=fullfile(out,sprintf('dprime_%d',g));mkdir(folder);
   processDPrime(request.group_roots{g},request.author_source,[folder filesep]);
   products.groups{g}=load(fullfile(folder,'d.mat'));
  end
 case 'full_figure_source_workspace'
  % The finite figure list is pinned author source. This runs actual scientific
  % producers/consumers; bindings must provide source-compatible paths first.
  allowed={'plotFigure1_expertBeh','plotFigure2_muscimol','plotFigure3_expertEphys',...
   'plotFigure4_TCA','plotFigure6_naiveBeh','plotFigure7_naiveEphys',...
   'plotFigureS1_rawWTexperts','plotFigureS2_divNorm10trial','plotFigureS3_muscimolPhys',...
   'plotFigureS4_muscimolBehSupp','plotFigureS5_muscimolModelsSupp',...
   'plotFigureS6_otherAreas','plotFigureS7_TCAsupp','plotFigureS9_naiveBehSupp','plotFigureS10_dPrime'};
  assert(any(strcmp(request.script_name,allowed)),'Unbound figure source');
  % Exact script arguments differ; the qualified binding supplies an argument
  % cell, never an eval string or candidate-controlled arbitrary source path.
  f=str2func(request.script_name);feval(f,request.arguments{:});
  products.figure_id=request.script_name;
  products.numeric_extraction_required=true;
 otherwise
  error('OFC:MissingNativeProducer',...
   'Native hLDS/LDS/filter/decoder/MI/ATI simulation or block producer must be independently bound; no plotted output is a substitute.');
end
save(fullfile(out,'native_products.mat'),'products','-v7.3');
end
