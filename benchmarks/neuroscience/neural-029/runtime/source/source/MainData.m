%% mouse types
exportSrcData=false;
scriptDir=fileparts(mfilename("fullpath"));
if ~isfolder(fullfile(scriptDir,"dependencies"))
    activeScriptFile=matlab.desktop.editor.getActiveFilename;
    if ~isempty(activeScriptFile), scriptDir=fileparts(activeScriptFile); end
end
if ~isfolder(fullfile(scriptDir,"dependencies")), error("Could not locate the script's dependencies directory."); end
xlout=fullfile(scriptDir,"excel","MainData.xlsx");
addpath(fullfile(scriptDir,"dependencies"));
dataDir=fullfile(scriptDir,"data");
if ~isfolder(dataDir), dataDir=uigetdir(scriptDir,"Select the directory containing the data files"); end
if isequal(dataDir,0), error("No data directory selected."); end
load(fullfile(dataDir,"mainData1.mat"));
load(fullfile(dataDir,"mainData2.mat"));
micedats = cat(1,micedats1,micedats2);
clear micedats1 micedats2
%% read stim parameters
ndirs=length(micedats);
mname = split(dirTable.DA_Dir,"\"); mname=squeeze(mname(:,end-1));
for j = 1:ndirs
    curd = micedats{j};
    winrew = winfn(curd.tmpxx,[-1 1]);
    curlas=curd.rewAlgn.sol(:,winrew);
    junk = find(sum(curlas,2)==0);
    curtr = setdiff(find(curd.rewarded),junk);
    curtrn = length(curtr);
    curlas=curd.rewAlgn.sol(curtr,winrew);
    curlason = arrayfun(@(x)find(curlas(x,:)>0,1),1:curtrn);
    curlason = median(curlason);
    curlasoff = arrayfun(@(x)find(curlas(x,:)>0,1,'last'),1:curtrn);
    curlasoff = mode(curlasoff);
    curlasdur = (curlasoff-curlason)*curd.dtb;
    pulseon = find(diff(curd.sol)>0);
    pulseoff = find(diff(curd.sol)<0);
    if length(pulseoff)>length(pulseon)
        pulseoff=pulseoff(2:end);
    elseif length(pulseoff)<length(pulseon)
        pulseon=pulseon(1:(end-1));
    end
    assert(length(pulseon)==length(pulseoff));
    curpulsedur = mode(pulseoff-pulseon)*curd.dtb;
    curpulsefreq = 1./mode(diff(pulseon)*curd.dtb);
    dirTable.stimParams(j,:) = [curlasdur curpulsedur curpulsefreq];
end

nvs = struct();
mgrps = struct();
mgrps.VTA = find(dirTable.DAType=="DAT");
nvs.VTA = length(unique(mname(mgrps.VTA)));
mgrps.VTA_250 = find(dirTable.DAType=="DAT" & dirTable.stimParams(:,1)<=0.25);
nvs.VTA_250 = length(unique(mname(mgrps.VTA_250)));
mgrps.MFB = find(dirTable.DAType=="MFB");
nvs.MFB = length(unique(mname(mgrps.MFB)));
mgrps.GrCs_all = find(dirTable.GrCs=="Y");
nvs.GrCs_all = length(unique(mname(mgrps.GrCs_all)));
mgrps.GrCs_CF = find(dirTable.GrCs=="Y" & dirTable.CFType~="none");
nvs.GrCs_CF = length(unique(mname(mgrps.GrCs_CF)));
mgrps.GrCs_VTA = find(dirTable.DAType=="DAT" & dirTable.GrCs=="Y");
nvs.GrCs_VTA = length(unique(mname(mgrps.GrCs_VTA)));
mgrps.GrCs_MFB = find(dirTable.DAType=="MFB" & dirTable.GrCs=="Y");
nvs.GrCs_MFB = length(unique(mname(mgrps.GrCs_MFB)));
mgrps.DA1s_grcs = find(dirTable.Delay==1 & dirTable.GrCs=="Y");
nvs.DA1s_grcs = length(unique(mname(mgrps.DA1s_grcs)));
mgrps.DA1s_grcs_mfb = find(dirTable.Delay==1 & dirTable.GrCs=="Y" & dirTable.DAType=="MFB");
nvs.DA1s_grcs_mfb = length(unique(mname(mgrps.DA1s_grcs_mfb)));
mgrps.DA1s_grcs_dat = find(dirTable.Delay==1 & dirTable.GrCs=="Y" & dirTable.DAType=="DAT");
nvs.DA1s_grcs_dat = length(unique(mname(mgrps.DA1s_grcs_dat)));
mgrps.DA2s_grcs = find(dirTable.Delay==2 & dirTable.GrCs=="Y");
nvs.DA2s_grcs = length(unique(mname(mgrps.DA2s_grcs)));
mgrps.DA2s_grcs_mfb = find(dirTable.Delay==2 & dirTable.GrCs=="Y" & dirTable.DAType=="MFB");
nvs.DA2s_grcs_mfb = length(unique(mname(mgrps.DA2s_grcs_mfb)));
mgrps.DA2s_grcs_dat = find(dirTable.Delay==2 & dirTable.GrCs=="Y" & dirTable.DAType=="DAT");
nvs.DA2s_grcs_dat = length(unique(mname(mgrps.DA2s_grcs_dat)));
mgrps.grcs_2s_has1smatch = mgrps.DA2s_grcs(arrayfun(@(x)isfield(micedats{x},"chronicGreen"),mgrps.DA2s_grcs));
nvs.grcs_2s_has1smatch = length(unique(mname(mgrps.grcs_2s_has1smatch)));
mgrps.grcs_2s_has1smatch_mfb = mgrps.DA2s_grcs(arrayfun(@(x)isfield(micedats{x},"chronicGreen") & dirTable.DAType(x)=="MFB",mgrps.DA2s_grcs));
nvs.grcs_2s_has1smatch_mfb = length(unique(mname(mgrps.grcs_2s_has1smatch_mfb)));
mgrps.grcs_1s_has2smatch = mgrps.DA1s_grcs(ismember(dirTable.DA_Dir(mgrps.DA1s_grcs),dirTable.Alt_Delay_Dir(mgrps.grcs_2s_has1smatch)));
mgrps.DA1s_grcs_haswater = find(~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y");
nvs.DA1s_grcs_haswater = length(unique(mname(mgrps.DA1s_grcs_haswater)));
mgrps.DA1s_grcs_haswater_matched = mgrps.DA1s_grcs_haswater(arrayfun(@(x)isfield(micedats{x},"chronicGreen"),mgrps.DA1s_grcs_haswater));
nvs.DA1s_grcs_haswater_matched = length(unique(mname(mgrps.DA1s_grcs_haswater_matched)));
mgrps.DA1s_grcs_haswater_matched_mfb = mgrps.DA1s_grcs_haswater(arrayfun(@(x)isfield(micedats{x},"chronicGreen")& dirTable.DAType(x)=="MFB",mgrps.DA1s_grcs_haswater));
nvs.DA1s_grcs_haswater_matched_mfb = length(unique(mname(mgrps.DA1s_grcs_haswater_matched_mfb)));
mgrps.DA1s_grcs_haswater_mfb = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y" & dirTable.DAType=="MFB");
nvs.DA1s_grcs_haswater_mfb = length(unique(mname(mgrps.DA1s_grcs_haswater_mfb)));
mgrps.DA1s_grcs_haswater_dat = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y" & dirTable.DAType=="DAT");
nvs.DA1s_grcs_haswater_dat = length(unique(mname(mgrps.DA1s_grcs_haswater_dat)));
mgrps.DA1s_grcs_haswater_waterfirst = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y"& dirTable.FirstRew=="water");
nvs.DA1s_grcs_haswater_waterfirst = length(unique(mname(mgrps.DA1s_grcs_haswater_waterfirst)));

mgrps.DA1s_haswater = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir));
nvs.DA1s_haswater = length(unique(mname(mgrps.DA1s_haswater)));
mgrps.DA1s_waterfirst = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.FirstRew=="water");
nvs.DA1s_waterfirst = length(unique(mname(mgrps.DA1s_waterfirst)));

mgrps.CF_DA = find(dirTable.CFType~="none");
nvs.CF_DA = length(unique(mname(mgrps.CF_DA)));
mgrps.CFs_haswater = find(~ismissing(dirTable.WaterDir) & dirTable.CFType~="none");
nvs.CFs_haswater = length(unique(mname(mgrps.CFs_haswater)));
mgrps.CFs_waterfirst = find(~ismissing(dirTable.WaterDir) & dirTable.CFType~="none" & dirTable.FirstRew=="water");
nvs.CFs_waterfirst = length(unique(mname(mgrps.CFs_waterfirst)));
mgrps.CFs_haswater_matched = mgrps.CFs_haswater(arrayfun(@(x)isfield(micedats{x},"chronicRed"),mgrps.CFs_haswater));
nvs.CFs_haswater_matched = length(unique(mname(mgrps.CFs_haswater_matched)));
mgrps.CFs_haswater_MFB = find(~ismissing(dirTable.WaterDir) & dirTable.CFType~="none" & dirTable.DAType=="MFB");
nvs.CFs_haswater_MFB = length(unique(mname(mgrps.CFs_haswater_MFB)));
mgrps.CFs_haswater_VTA = find(~ismissing(dirTable.WaterDir) & dirTable.CFType~="none" & dirTable.DAType=="DAT");
nvs.CFs_haswater_VTA = length(unique(mname(mgrps.CFs_haswater_VTA)));
mgrps.CF_gcamp = find(dirTable.CFType=="gcamp");
nvs.CF_gcamp = length(unique(mname(mgrps.CF_gcamp)));
mgrps.CF_rcamp = find(dirTable.CFType=="rcamp");
nvs.CF_rcamp = length(unique(mname(mgrps.CF_rcamp)));
mgrps.CFs_VTA = find(dirTable.DAType=="DAT" & dirTable.CFType~="none");
nvs.CFs_VTA = length(unique(mname(mgrps.CFs_VTA)));
mgrps.CFs_MFB = find(dirTable.DAType=="MFB" & dirTable.CFType~="none");
nvs.CFs_MFB = length(unique(mname(mgrps.CFs_MFB)));
mgrps.CF_gcamp_VTA = find(dirTable.CFType=="gcamp" & dirTable.DAType=="DAT");
nvs.CF_gcamp_VTA = length(unique(mname(mgrps.CF_gcamp_VTA)));

mgrps.male = find(dirTable.Sex=="M");
nvs.male = length(unique(mname(mgrps.male)));
mgrps.female = find(dirTable.Sex=="F");
nvs.female = length(unique(mname(mgrps.female)));

disp(nvs)
% behavior
dlcnames = ["forelimbspeed","lowjawspeed","nosespeed","hindlimbspeed"];
rtyps = ["Water","1-s DA","DA-first","2-s DA"];
rleg = ["VTA","MFB","H2O"];
dirsuse = 1:ndirs;
ndirsuse = length(dirsuse);
for dd = 1:ndirsuse
    d=dirsuse(dd);
    for j = 1:2
        processcur=true;
    if j==1
        curd = micedats{d}; 
    elseif j==2 
        if isfield(micedats{d},'waterdat'), curd=micedats{d}.waterdat; 
        else, processcur=false;
        end
    end
    if processcur
    for algnuse="endAlgn"
    if isfield(curd.(algnuse),"dlc")
        dlcmedf = curd.(algnuse).dlc;
        lowerjawix = find(contains(curd.dlc.bodyparts,"lower","IgnoreCase",true)...
            & contains(curd.dlc.bodyparts,"jaw","IgnoreCase",true));
        noseix = find(contains(curd.dlc.bodyparts,"nose","IgnoreCase",true));
        forelimbix = find(contains(curd.dlc.bodyparts,"fore","IgnoreCase",true) &...
            ((contains(curd.dlc.bodyparts,"right","IgnoreCase",true) | ...
            contains(curd.dlc.bodyparts,"ipsi","IgnoreCase",true))));
        leverix = find(contains(curd.dlc.bodyparts,"lever","IgnoreCase",true));
        hindlimbix = find(contains(curd.dlc.bodyparts,"hind","IgnoreCase",true) &...
            ((contains(curd.dlc.bodyparts,"right","IgnoreCase",true) | ...
            contains(curd.dlc.bodyparts,"ipsi","IgnoreCase",true))));
        dlcixes = {forelimbix,lowerjawix,noseix,hindlimbix};
        wintest = winfn(curd.tmpxDLC,[-1 3]);
        if j==1, dirname=dirTable.DA_Dir(d); 
        else, dirname=dirTable.WaterDir(d); end
        leverraw = dlcmedf(:,:,[leverix]);
        dlcpos = squeeze(leverraw(:,:,1));
        nipos = squeeze(curd.(algnuse).pos(:,:,2));
        nipos = interp1(curd.tmpxx',nipos',curd.tmpxDLC',"linear","extrap")';
        badlevertrials=[];
        for k = 1:size(leverraw,1)
            curcorr = corr(dlcpos(k,:)',nipos(k,:)');
            if curcorr<0.85, badlevertrials=[badlevertrials; k]; end % Discard trials with poor DLC/encoder match
        end
        for dix = 1:length(dlcixes)
           curix = dlcixes{dix};
        if length(curix)==2
        badtrials=badlevertrials;
        curraw = dlcmedf(:,:,[curix]);
        if isfield(curd.(algnuse),"dlclikeli")
        curlikeix = unique(ceil(curix/2));
        curlike = curd.(algnuse).dlclikeli(:,:,curlikeix);
        for tr = 1:size(curraw,1)
            tmptrans=diff(find(diff([0 curlike(tr,wintest)<0.9 0])));
            tmptrans = tmptrans(1:2:end);
            if max(tmptrans)>0.2/curd.dtDLC
                badtrials = [badtrials; tr];  % discard trials with low DLC tracking confidence
            end
        end
        end
        for tr = 1:size(curraw,1)
            tmptrans=diff(find(diff([0 isnan(curraw(tr,wintest)) 0])));
            tmptrans = tmptrans(1:2:end);
            if max(tmptrans)>1/curd.dtDLC, badtrials = [badtrials; tr]; end
        end
        goodtrials=setdiff(1:size(curraw,1),badtrials);
        badtimepoints=[];
        if isfield(curd.(algnuse),"dlclikeli")
        badtimepoints = [badtimepoints; find(curlike<0.9)];
        end
        tmp1 = squeeze(curraw(:,:,1));
        tmp2 = squeeze(curraw(:,:,2));
        tmp1(badtimepoints)=nan;
        tmp2(badtimepoints)=nan;
        curraw = fillmissing(cat(3,tmp1,tmp2),'linear',2);
        speed = diff(curraw(:,[1 1:end],:),[],2)./curd.dtDLC;
        speed = squeeze(sqrt(sum(speed.^2,3)));
        speed(badtrials,:) = nan;
        wth = find(all(isnan(speed(goodtrials,:)),2));
        badtrials = [badtrials; wth];
        goodtrials=setdiff(1:size(curraw,1),badtrials);
        badspeed = find(sum(speed(:,wintest)>1000,2)>0.3/curd.dtDLC);
        assert(all(all(~isnan(speed(goodtrials,:)),2)));
        speed(badspeed,:) = nan; 
        curd.(algnuse).(dlcnames(dix)) = speed;
        assert(size(speed,1)==curd.n_mv)
        goodtrials = setdiff(1:size(speed,1),union(badtrials,badspeed)); % Discard trials with questionably high DLC "speeds"
        assert(all(all(~isnan(speed(goodtrials,:)))));
        end
        end
    end
    curd.rewdel = (curd.rewtimes-curd.trueend)*curd.dtb;
    medrewdel=median(curd.rewdel);
    curd.attmptRate = 1./median(diff(curd.truestart)*curd.dtb)*60;
            
    curd.mvlen = sqrt(sum(curd.rewAlgn.pos(:,curd.tmpxx==0,:).^2,3));

    % Calculate SUCCESS rate (successes per minute)
    curd.succRate = 1./median(diff(curd.truestart(curd.mvlen>6))*curd.dtb)*60;

    curd.compltd=nnz(curd.mvlen>6)/numel(curd.mvlen);

    curd.mvdurs = (curd.trueend-curd.truestart)*curd.dtb*1000;
    curd.goodMvmt(curd.rewdel>dirTable.Delay(d)*1.5)=0; % Discard trials with questionably long measured delays
    curd.goodMvmt(curd.rewdel<dirTable.Delay(d)*0.5)=0; % Discard trials with questionably short measured delays
    if j==1, micedats{d}=curd; elseif j==2 && isfield(micedats{d},'waterdat'), micedats{d}.waterdat=curd; end
    end
    end
    end
end
%% Fig1f,g
rng(0);
reachtrange=[-0.25 0.65];
[~,t_ax_reach_tmplt_s] = winfn(micedats{1}.tmpxx,reachtrange);
ret_trange=[-0.5 5];
[~,t_ax_ret_tmplt_s] = winfn(micedats{1}.tmpxx,ret_trange);
t_ax_trials = 0:1:(36*60);
ntaxtrials = length(t_ax_trials);
cumultrials = cell(1,3);
avgreach = cell(1,3);
avgreach_ret = cell(1,3);
curmnames=cell(1,3);
for r = 1:3
    cumultrials{r}=zeros(ntaxtrials,0);
    avgreach{r} = zeros(length(t_ax_reach_tmplt_s),0);
    avgreach_ret{r} = zeros(length(t_ax_ret_tmplt_s),0);
    for d = 1:ndirs
        proc=false;
        if r==1 && dirTable.Delay(d)==1 && dirTable.DAType(d)=="DAT", curd = micedats{d}; proc=true;
        elseif r==2 && dirTable.Delay(d)==1 && dirTable.DAType(d)=="MFB", curd = micedats{d}; proc=true;
        elseif r==3 && dirTable.Delay(d)==1 && isfield(micedats{d},'waterdat'), curd = micedats{d}.waterdat; proc=true;
        end
        if proc
        [t_ax_reach,t_ax_reach_s] = winfn(curd.tmpxx,reachtrange);
        mvuse = find(curd.goodMvmt & curd.mvlen>6);
        rewtimes_s = round(curd.rewtimes(mvuse)*curd.dtb);
        rewtimes_s=min(max(rewtimes_s,0),t_ax_trials(end));
        trIndicator = zeros(ntaxtrials,1);
        [~,rewardIndeces] = ismember(rewtimes_s,t_ax_trials);
        trIndicator(rewardIndeces)=1;
        trIndicator = cumsum(trIndicator);
        trIndicator((rewardIndeces(end)+1):end)=nan;
        cumultrials{r} = cat(2,cumultrials{r},trIndicator);
        rewuse = find(curd.goodMvmt & curd.rewarded & curd.mvlen>6);
        cur = mean(curd.startAlgn.pos(rewuse,t_ax_reach,2),1)';
        curi = interp1(t_ax_reach_s,cur,t_ax_reach_tmplt_s,"linear","extrap")';
        avgreach{r} = cat(2,avgreach{r},curi);
        curmnames{r} = unique([curmnames{r},dirTable.mname(d)]);
        end
    end
end
figure; 
hall1=[];
hold on; h2=plot(t_ax_trials/60,cumultrials{1},'r');
hold on; h3=plot(t_ax_trials/60,cumultrials{2},'b');
hall1=[hall1 h2(1) h3(1)]; 
plotord("rand");
axis tight; 
figureformat_forsaving
legend(hall1,rleg(1:2))
xlabel("Time (min)")
titstr = sprintf("%d/%d %s and %d/%d %s sessions/mice",size(avgreach{1},2),length(curmnames{1}),...
    rleg(1),size(avgreach{2},2),length(curmnames{2}),rleg(2));
title("Fig1g: "+titstr)
ylabel("Cumulative number of trials")
export_nature_master(gcf,xlout,exportSrcData);

figure; h=plot(t_ax_reach_tmplt_s,avgreach{1},'r');
hold on; h2=plot(t_ax_reach_tmplt_s,avgreach{2},'b');
uistack(h,"top")
axis tight; 
figureformat_forsaving
legend([h(1),h2(1)],rleg(1:2))
xlabel("Time relative to reach onset (s)")
ylabel("Position (mm)")
xticks(-0.2:.1:.8)
yticks(0:2:8)
title("Fig1f: "+titstr)
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
%% DLC
rng(0);
% 1st run: 1-s DA reward vs omission | EDFig4b,c
% 2nd run: 1-s vs 2-s rewarded | EDFig4e,f
% 3rd run: 1-s DA vs water omission | Fig3o-s
% 4th run: 1-s rewarded VTA vs MFB  | EDFig5e,f
% 5th run: 1-s omission VTA vs MFB  | EDFig5g,h
bartitls=["EDFig4c","EDFig4f","Fig3s","EDFig5f","EDFig5h"];
curvtitls=["EDFig4b","EDFig4e","Fig3o-r","EDFig5e","EDFig5g"];
dlcmags={};
for k = 1:5
    switch k
        case 1
            toComp = {["1-s DA","rewarded","both"],["1-s DA","omission","both"]};
            labls=["DA rewarded","DA omitted"];
            ccplt=[0 0 1; 1 0 0];
            measWin=[1.2 1.7];
        case 2
            toComp = {["1-s DA","rewarded","both"],["2-s DA","rewarded","both"]};
            labls=["1-s DA","2-s DA"];
            ccplt=[0.5 0 0.5; 0.318 0.698 0.961];
            measWin=[1.5 2];
        case 3 
            toComp = {["Water","omission",""],["1-s DA","omission","both"]};
            labls=["Water","DA"];
            ccplt=[0.157 0.471 0.231; 0.659 0.086 0.541];
            measWin=[0.5 1];
        case 4
            toComp = {["1-s DA","rewarded","DAT"],["1-s DA","rewarded","MFB"]};
            labls=["VTA rewarded","MFB rewarded"];
            ccplt=[0.659 0.086 0.541].*[1.4; 0.6];
            measWin=[1.2 1.7];
        case 5
            toComp = {["1-s DA","omission","DAT"],["1-s DA","omission","MFB"]};
            labls=["VTA omitted","MFB omitted"];
            ccplt=[0.659 0.086 0.541].*[1.2; 0.8];
            measWin=[0.5 1];
    end
pltlabls = ["Jaw","R Forelimb","Nose","R Hindlimb"];
dlcnames = ["lowjawspeed","forelimbspeed","nosespeed","hindlimbspeed"];
ndlcnms = length(dlcnames);
nplt = length(dlcnames); 
dlcsess = zeros(ndlcnms,2);
dlcmnames = cell(nplt,2);
dlcsesso = zeros(ndlcnms,2);
dlcmnameso = cell(nplt,2);
dlcsessnameso = cell(nplt,2);
rewtrialsbodyspeed = cell(ndlcnms,2);
omittrialsbodyspeed = cell(ndlcnms,2);
rewbodyspeedmouse = cell(ndlcnms,2);
omitbodyspeedmouse = cell(ndlcnms,2);
algnuse = "endAlgn";
endAdd=double(algnuse=="endAlgn");
xluse = [-2 2]+endAdd;
firstdlcmouse = find(cellfun(@(x)isfield(x,'tmpxDLC'),micedats),1);
[~,t_ax_jaw_s] = winfn(micedats{firstdlcmouse}.tmpxDLC,xluse);
rtypuse=[toComp{1}(1),toComp{2}(1)];
[~,ruse]=ismember(rtypuse,rtyps);
for rr = 1:length(toComp)
    rtyp=rtypuse(rr);
    r=ruse(rr);
    for d = 1:ndirs
        processcur=false;
        curd = micedats{d};
        if rtyp=="1-s DA" && dirTable.Delay(d)==1
            if toComp{rr}(3)=="both" || (toComp{rr}(3)==dirTable.DAType(d))
            processcur=true;
            end
            if ismember("2-s DA",rtypuse) && ~(ismember(dirTable.mname(d),dirTable.mname(dirTable.Delay==2))), processcur=false; end
            if ismember("Water",rtypuse) && ~(isfield(micedats{d},'waterdat')), processcur=false; end
        elseif rtyp=="Water" && isfield(micedats{d},'waterdat')
            curd = micedats{d}.waterdat; 
            processcur=true;
        elseif rtyp=="2-s DA" && dirTable.Delay(d)==2
            processcur=true; 
        end
        if processcur
        rewuse = find(curd.goodMvmt & curd.rewarded & curd.mvlen>=6);
        omituse = find(curd.goodMvmt & ~curd.rewarded & curd.mvlen>=6);
        if 1
        for n = 1:nplt
        if isfield(curd.(algnuse),dlcnames(n))
            [t_ax_jaw_cur,t_ax_jaw_cur_s] = winfn(curd.tmpxDLC,xluse);
            curspd = curd.(algnuse).(dlcnames(n))(rewuse,t_ax_jaw_cur);
            badtrials = find(any(isnan(curspd),2));
            curspd(badtrials,:) = [];
            if size(curspd,1)>1
            curspd = interp1(t_ax_jaw_cur_s,curspd',t_ax_jaw_s,[],"extrap")';
            assert(all(~isnan(curspd(:))));
            rewtrialsbodyspeed{n,rr} = cat(1,rewtrialsbodyspeed{n,rr},curspd);
            rewbodyspeedmouse{n,rr} = cat(1,rewbodyspeedmouse{n,rr},mean(curspd,1)); 
            if length(omituse)>1
            curspd = curd.(algnuse).(dlcnames(n))(omituse,t_ax_jaw_cur);
            badtrials = find(any(isnan(curspd),2));
            curspd(badtrials,:) = [];
            if size(curspd,1)>1
            curspd = interp1(t_ax_jaw_cur_s,curspd',t_ax_jaw_s,[],0)';
            curspd = butter_filtfilt(2,0.5,curspd')';
            omittrialsbodyspeed{n,rr} = cat(1,omittrialsbodyspeed{n,rr},curspd); 
            omitbodyspeedmouse{n,rr} = cat(1,omitbodyspeedmouse{n,rr},mean(curspd,1)); 
            dlcsesso(n,rr) = dlcsesso(n,rr)+1;
            dlcmnameso{n,rr} = cat(1,dlcmnameso{n,rr},dirTable.mname(d));
            if r~=1
            dlcsessnameso{n,rr} = cat(1,dlcsessnameso{n,rr},dirTable.DA_Dir(d));
            else
                dlcsessnameso{n,rr} = cat(1,dlcsessnameso{n,rr},dirTable.WaterDir(d));
            end
            end
            end
            dlcsess(n,rr) = dlcsess(n,rr)+1;
            dlcmnames{n,rr} = cat(1,dlcmnames{n,rr},dirTable.mname(d));
            end
        end
        end
        end
        end
    end
end
toplt=cell(nplt,2);
dlcnamesplt=cell(nplt,2);
for kk =1:2
    if toComp{kk}(2)=="rewarded"
        toplt(:,kk) = rewbodyspeedmouse(:,kk); 
        dlcnamesplt(:,kk) = dlcmnames(:,kk);
    elseif toComp{kk}(2)=="omission"
        toplt(:,kk) = omitbodyspeedmouse(:,kk);
        dlcnamesplt(:,kk) = dlcmnameso(:,kk);
    end
end
if ismember(toComp{1}(3),["both",""])
for n=1:nplt
mboth=intersect(dlcnamesplt{n,1},dlcnamesplt{n,2});
ixuse1 = find(ismember(dlcnamesplt{n,1},mboth));
ixuse2 = find(ismember(dlcnamesplt{n,2},mboth));
toplt{n,1}=toplt{n,1}(ixuse1,:);
toplt{n,2}=toplt{n,2}(ixuse2,:);
dlcnamesplt{n,1}=dlcnamesplt{n,1}(ixuse1,:);
dlcnamesplt{n,2}=dlcnamesplt{n,2}(ixuse2,:);
end
end
nMice = cellfun(@(x)numel(unique(x)),dlcnamesplt);
nSess = cellfun(@numel,dlcnamesplt);
figure(pos=[1502 186 334 714]); 
t = tiledlayout(nplt,1);
clear h h2 hAx;
titstr=curvtitls(k);
for n = 1:nplt
hAx(n)=nexttile;
if ~isempty(toplt{n,1})
h(n,:)=errorbar_shadeSEM(t_ax_jaw_s,toplt{n,1}',ccplt(1,:));
h2(n,:)=errorbar_shadeSEM(t_ax_jaw_s,toplt{n,2}',ccplt(2,:));
title([pltlabls(n); compose( ...
    "n mice/sessions: %s %d/%d; %s %d/%d", ...
    labls(1),nMice(n,1),nSess(n,1), ...
    labls(2),nMice(n,2),nSess(n,2))]);
axis tight; 
if n==1
end
uistack([h(1) h2(1)],'top')
xlim(xluse); xticks(xluse(1):xluse(2))
end
end
for a = 1:nplt
    axes(hAx(a))
    ylim tight;
    yl=ylim;ylim([0 yl(2)]);
    hold on; plot([-1 -1]+endAdd,ylim,'k',[0 0]+endAdd,ylim,'k');
    if ismember("2-s DA",rtypuse), hold on; plot([2 2],ylim,'k'); end
    if a==1, legend([h(a,1) h2(a,1)],labls); if k==2, yticks([0:40:180]); end; end
end
ylabel(t,"Speed (pix/s)")
xlabel("Time relative to movement (s)");
title(t,titstr);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

prerewdlc = winfn(t_ax_jaw_cur_s,measWin);

vp={};
for n = 1:nplt
for rr  = 1:length(ruse)
if(~isempty(toplt{n,rr}))
vp{rr+(n-1)*2}=mean(toplt{n,rr}(:,prerewdlc),2);
    end
end
end
tmpcol=repmat(ccplt([1 2],:),nplt,1);
h=barwitherr_stde(vp,dots=true,col=tmpcol,ranksumgrps={[1 2],[3 4],[5 6],[7 8]});
legend(h(1:2),labls)
dlcmags{k}=vp;
ylabel("Speed from "+strvec(measWin)+" s");
xticklabels(repelem(pltlabls,2));
titstr=gca;
titstr=string(titstr.Title.String);
titstr(1)=bartitls(k);
title(titstr);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
end
%% Compute unaligned neuron avgs
% 1: all CFs
% 2: all GrCs
[allCFs_rew,allGrCs_rew,allCFs_omit,allGrCs_omit,GrCsChronInfo,CFsChronInfo,...
ant,anti,post,posti,allCFs,allGrCs,mvCFs,is_rewGrCs,is_omitGrCs]=...
deal(cell(1,length(rtyps)));
bodparam="forelimbspeed";
cnames = ["GrCs","CFs"];
snames = ["sigFilt_right_green","sprate_right_red"];
ncnames = ["nc_right_green","nc_right_red"];
chronnms = ["chronicGreen","chronicRed"];
algnuses = ["endAlgn","endAlgn","endAlgn","endAlgn";...
            "rewAlgn","rewAlgn","rewAlgn","rewAlgn"];
for c= 1:2
ctyp = cnames(c);
for r = 1:4
curalgn = algnuses(c,r);
rtyp = rtyps(r);
curd = micedats{1};
if curalgn=="endAlgn", tplt_lims = [-1 4];
elseif curalgn=="rewAlgn", tplt_lims = [-2 2];
end
if c==1, [~,tplt_tmplt_s] = winfn(curd.tmpx_right,tplt_lims); curtplt_s=tplt_tmplt_s; 
elseif c==2, [~,tplt_tmplt_s_CF] = winfn(curd.tmpx_right,tplt_lims); curtplt_s=tplt_tmplt_s_CF;
end
dtim_tmplt=mean(diff(tplt_tmplt_s));
if c==1, GrCsChronInfo{r} = table(Size=[0 0]);
elseif c==2, CFsChronInfo{r} = table(Size=[0 0]);
end
dirsuse = find(dirTable.Delay==1);
if rtyp=="DA-first", dirsuse = find(dirTable.FirstRew=="DA" & dirTable.Delay==1); end
if rtyp=="2-s DA", dirsuse = find(dirTable.Delay==2); end
for dd = 1:length(dirsuse)
    d=dirsuse(dd);
    proc=false;
    if ismember(rtyp,["1-s DA","DA-first","2-s DA"]), curd = micedats{d}; proc=true; 
    elseif rtyp=="Water" && isfield(micedats{d},'waterdat')
            curd = micedats{d}.waterdat; proc=true; 
    end
    if proc
    [tplt,tplt_s] = winfn(curd.tmpx_right,tplt_lims);
    rewuse = find(curd.rewarded & curd.goodMvmt & curd.mvlen>6);
    omituse = find(~curd.rewarded & curd.goodMvmt & curd.mvlen>6);
    if (cnames(c)=="GrCs" && strcmpi(dirTable.GrCs(d),"Y")) || (cnames(c)=="CFs" && ~strcmpi(dirTable.CFType(d),"none"))
        curgrc = curd.(curalgn).(snames(c))(:,:,tplt);
        curgrci = permute(interp1(tplt_s,permute(curgrc,[3 1 2]),curtplt_s,"linear","extrap"),[2 3 1]);
        if isfield(curd,"trashframes"), 
            rewuseg = rewuse(~ismember(curd.frame_right(curd.rewtimes(rewuse)),curd.trashframes));
            omituseg = omituse(~ismember(curd.frame_right(curd.rewtimes(omituse)),curd.trashframes));
        else, rewuseg=rewuse; omituseg=omituse; 
        end
        % Compute reliability over odd vs even trials
        halves={rewuseg(1:2:end),rewuseg(2:2:end)};
        halvesSig={};
        for tg = 1:2
            curavg = squeeze(mean(curgrci(halves{tg},:,:),1));
            halvesSig{tg}=curavg;
        end
        tmprel=diag(corr(halvesSig{1}',halvesSig{2}'));
        tmprel(tmprel<0)=0;
        tmprel=2*tmprel./(1+tmprel);
        Kcur=100/length(rewuseg);
        tmprel=Kcur*tmprel./(1+tmprel*(Kcur-1));
        curd.reliab=tmprel;

        tmpmn = squeeze(mean(curgrci(rewuseg,:,:),1));
        if ctyp=="GrCs"
        allGrCs_rew{r} = cat(1,allGrCs_rew{r},tmpmn);
        if isempty(omituse), allGrCs_omit{r} = cat(1,allGrCs_omit{r},nan(size(tmpmn)));
        else, allGrCs_omit{r} = cat(1,allGrCs_omit{r},squeeze(mean(curgrci(omituseg,:,:),1)));
        end
        allGrCs{r} = cat(1,allGrCs{r},squeeze(mean(curgrci([rewuseg; omituseg],:,:),1)));
        if r>1
        [xcwin,xcwin_s]=winfn(curtplt_s,[0 4]);
        curtaus=zeros(size(curgrci,2),1);
        for curc = 1:size(curgrci,2)
        tmpxc=zeros(length(omituse),length(xcwin)*2-1); 
        for curtr = 1:length(omituse)
            [tmpxc(curtr,:),lags]=xcorr(curgrci(omituseg(curtr),curc,xcwin));
        end
        lags = lags*dtim_tmplt;
        ix1=find(lags==0);
        curtau = fit(lags(ix1:end)',mean(tmpxc(:,ix1:end))','exp1');
        curtaus(curc) = -1/curtau.b;
        end
        curd.stTaus=curtaus;
        sprintf(d+", ");
        else, curd.stTaus=zeros(size(curgrci,2),1);
        end
        else
            allCFs_rew{r} = cat(1,allCFs_rew{r},tmpmn);
        if isempty(omituse), allCFs_omit{r} = cat(1,allCFs_omit{r},nan(size(tmpmn)));
        else, allCFs_omit{r} = cat(1,allCFs_omit{r},squeeze(mean(curgrci(omituseg,:,:),1)));
        end
        allCFs{r} = cat(1,allCFs{r},squeeze(mean(curgrci([rewuseg; omituseg],:,:),1)));
        curd.stTaus=zeros(size(curgrci,2),1);
        end
        tmpGrCInfo = table(Size=[curd.(ncnames(c)),0]);
        tmpGrCInfo.stTau=curd.stTaus;
        tmpGrCInfo.hasDLC(:) = isfield(curd.(curalgn),bodparam);
        tmpGrCInfo.nOmit(:) = length(omituseg);
        tmpGrCInfo.sessionNum(:) = d;
        tmpGrCInfo.cellNum = (1:curd.(ncnames(c)))';
        tmpGrCInfo.reliab=curd.reliab;
        if isfield(micedats{d},chronnms(c))
            ch = micedats{d}.(chronnms(c)).finalMatchesMat;
            mxes = max(ch,[],1);
            assert(length(unique(mxes))==2);
            [~,ixopt] = ismember(curd.(ncnames(c)),mxes);
            [~,ch2] = ismember(1:curd.(ncnames(c)),ch(:,ixopt));
            tmpGrCInfo.otherCellNum = ch(ch2,setdiff(1:2,ixopt));
        else
            tmpGrCInfo.otherCellNum = zeros(curd.(ncnames(c)),1);
        end
        if ctyp=="GrCs"
        GrCsChronInfo{r} = cat(1,GrCsChronInfo{r},tmpGrCInfo);
        else
            CFsChronInfo{r} = cat(1,CFsChronInfo{r},tmpGrCInfo);
        end
    end
    end
end
end
end
% Categorize neurons
algnptnm = "Movement";
if algnptnm == "Movement", endAdd=1; else, endAdd=0; end
clear febyl
ruse = 1:4;
for r = ruse
    endAdd2=endAdd;
    if r==4 && endAdd2~=0, endAdd2=2; end
    prerew_lims = [-0.1 0]+endAdd2;
prerew_win = winfn(tplt_tmplt_s,prerew_lims);
rew_lims = [0.1 0.2];
rew_win = winfn(tplt_tmplt_s_CF,rew_lims);
mv_win = winfn(tplt_tmplt_s_CF,[-1.1 -0.9]);
postrew_lims = [1.4 1.7];
postrew_win = winfn(tplt_tmplt_s,postrew_lims);
baseline_lims = [-1.3 -1]+endAdd;
rewdec_lims = [0.4 0.7]+endAdd2;
del_lims = [-1+endAdd 0+endAdd2];
ix_del = winfn(tplt_tmplt_s,del_lims);
ix_del_half = winfn(tplt_tmplt_s,[-0.5+endAdd 0+endAdd2]);
del_lims_4s = [-1+endAdd 3+endAdd];
ix_del_4s = winfn(tplt_tmplt_s,del_lims_4s);
baseline_win = winfn(tplt_tmplt_s,baseline_lims);
rewdec_win = winfn(tplt_tmplt_s,rewdec_lims);
ngc = size(allGrCs_rew{r},1);
for c= 1:ngc
    delay_activ_indeces = find(allGrCs{r}(c,ix_del)>0.1);
    if isempty(delay_activ_indeces), delay_activ_indeces = 1:length(ix_del); end
    if max(allGrCs_omit{r}(c,ix_del_4s))>abs(min(allGrCs_omit{r}(c,ix_del_4s)))
        curpos=1;
    else
    curpos=-1;
    end
    delay_activ_indeces_4s = find(curpos*allGrCs_omit{r}(c,ix_del_4s)>0.1);
    if isempty(delay_activ_indeces_4s), delay_activ_indeces_4s = 1:length(ix_del_4s); end
    delay_activ_indecesi = find(allGrCs{r}(c,ix_del)<-0.1);
    if isempty(delay_activ_indecesi), delay_activ_indecesi = 1:length(ix_del); end
    tmp4 = allGrCs{r}(c,ix_del(delay_activ_indeces));
    tmp4=(tmp4-min(tmp4));
    GrCsChronInfo{r}.delay_activ_cent(c) = sum(tmp4./sum(tmp4).*tplt_tmplt_s(ix_del(delay_activ_indeces)));
    
    tmp4 = curpos*allGrCs_omit{r}(c,ix_del_4s(delay_activ_indeces_4s));
    tmp4=(tmp4-min(tmp4));
    if sum(tmp4)~=0
        GrCsChronInfo{r}.delay_activ_cent_4s(c) = ...
        sum(tmp4./sum(tmp4).*tplt_tmplt_s(ix_del_4s(delay_activ_indeces_4s)));
    else
        GrCsChronInfo{r}.delay_activ_cent_4s(c) = ...
        mean(tplt_tmplt_s(ix_del_4s));
    end
    tmp4 = -allGrCs{r}(c,ix_del(delay_activ_indecesi));
    tmp4=(tmp4-min(tmp4));
    GrCsChronInfo{r}.delay_activ_centi(c) = sum(tmp4./sum(tmp4).*tplt_tmplt_s(ix_del(delay_activ_indecesi)));
end
GrCsChronInfo{r}.delay_activ_cent = coerce(GrCsChronInfo{r}.delay_activ_cent,del_lims);
GrCsChronInfo{r}.delay_activ_centi = coerce(GrCsChronInfo{r}.delay_activ_centi,del_lims);
GrCsChronInfo{r}.delay_activ_cent_4s = coerce(GrCsChronInfo{r}.delay_activ_cent_4s,del_lims_4s);
[~,GrCsChronInfo{r}.sortIx] = sort(GrCsChronInfo{r}.delay_activ_cent);
[~,GrCsChronInfo{r}.sortIxi] = sort(GrCsChronInfo{r}.delay_activ_centi);
GrCsChronInfo{r}.prerew_grc = mean(allGrCs{r}(:,prerew_win),2);
GrCsChronInfo{r}.postrew = mean(allGrCs_rew{r}(:,postrew_win),2);
GrCsChronInfo{r}.postomit = mean(allGrCs_omit{r}(:,postrew_win),2);
GrCsChronInfo{r}.del_act = mean(allGrCs{r}(:,ix_del),2);
GrCsChronInfo{r}.half_del_act = mean(allGrCs{r}(:,ix_del_half),2);
[~,GrCsChronInfo{r}.prerewSortIx] = sort(GrCsChronInfo{r}.prerew_grc);
GrCsChronInfo{r}.prerewmbase_grc = GrCsChronInfo{r}.prerew_grc-mean(allGrCs{r}(:,baseline_win),2);
GrCsChronInfo{r}.mvmag = mean(allGrCs{r}(:,baseline_win),2);
GrCsChronInfo{r}.prerewmrewdec_grc = GrCsChronInfo{r}.prerew_grc-mean(allGrCs_rew{r}(:,rewdec_win),2);
if r~=4
CFsChronInfo{r}.postrew = mean(allCFs_rew{r}(:,rew_win),2);
CFsChronInfo{r}.mvmag = mean(allCFs_rew{r}(:,mv_win),2);
[~,CFsChronInfo{r}.sortIx] = sort(CFsChronInfo{r}.postrew);
[~,CFsChronInfo{r}.prerewSortIx] = sort(CFsChronInfo{r}.postrew);
post{r} = find(CFsChronInfo{r}.postrew>1.3);
mvCFs{r} = find(CFsChronInfo{r}.mvmag>1.3);
end
ant{r} = find(GrCsChronInfo{r}.prerewmrewdec_grc>0 & GrCsChronInfo{r}.prerewmbase_grc>0);
anti{r} = find(GrCsChronInfo{r}.prerewmrewdec_grc<0 & GrCsChronInfo{r}.prerewmbase_grc<0);
% stats 
tmpant = zeros(size(GrCsChronInfo{r},1),1);
tmpanti = zeros(size(GrCsChronInfo{r},1),1);
uniqS = unique(GrCsChronInfo{r}.sessionNum);
is_post = zeros(size(GrCsChronInfo{r},1),1);
is_omit = zeros(size(GrCsChronInfo{r},1),1);
for kses = 1:length(uniqS)
    d=uniqS(kses);
    currows=find(GrCsChronInfo{r}.sessionNum==d);
    if r>1, curd=micedats{d}; else, curd=micedats{d}.waterdat; end
    rewuse = find(curd.rewarded & curd.goodMvmt & curd.mvlen>6);
    omituse = find(~curd.rewarded & curd.goodMvmt & curd.mvlen>6);
    tmpwinpre=winfn(prerew_lims,curd.tmpx_right);
    tmpsigpre=squeeze(mean(curd.endAlgn.sigFilt_right_green([rewuse; omituse],:,tmpwinpre),3));
    pvls = arrayfun(@(c)signrank(tmpsigpre(:,c)),1:length(currows));
    pvls_pos=pvls; pvls_pos(mean(tmpsigpre)<0)=1;
    pvls_neg=pvls; pvls_neg(mean(tmpsigpre)>0)=1;
    tmpant(currows)=pvls_pos;
    tmpanti(currows)=pvls_neg;
    tmpwinomit=winfn([1.4 1.7],curd.tmpx_right);
    tmpwinrew=winfn([1.2 1.4],curd.tmpx_right);
    tmpsigrew=squeeze(mean(curd.endAlgn.sigFilt_right_green(rewuse,:,tmpwinrew),3));
    tmpsigpost=squeeze(mean(curd.endAlgn.sigFilt_right_green(rewuse,:,tmpwinomit),3));
    tmpsigomit=squeeze(mean(curd.endAlgn.sigFilt_right_green(omituse,:,tmpwinomit),3));
    cur_pvls_post=arrayfun(@(c)ranksum(tmpsigrew(:,c),tmpsigpre(:,c)),1:length(currows));
    cur_pvls_omit=arrayfun(@(c)signrank(tmpsigomit(:,c)),1:length(currows));

    is_post(currows)=cur_pvls_post<0.05 & mean(tmpsigrew,1)>0 & mean(tmpsigrew,1)>mean(tmpsigpre,1);
    is_omit(currows)=cur_pvls_omit<0.05 & mean(tmpsigomit,1)>0 & mean(tmpsigomit,1)>mean(tmpsigpost,1);
end
ant_sig{r} = intersect(ant{r},find(tmpant<0.05));
anti_sig{r} = intersect(anti{r},find(tmpanti<0.05));
is_rewGrCs{r} = find(is_post);
is_omitGrCs{r} = find(is_omit);
end
%% Plot rasters
sc1=[-0.3 0.3];
sc_ant=[-0.4 0.4];
sc_spikerate = [0 1.8];
rasterlist = ["Fig1b,h: DA 1-s v DA 2-s all grcs",...
    "Fig1c,d,i,j: DA 1-s v DA 2-s antic GrCs",...
    "Fig1e,f,k,l: DA 1-s v DA 2-s antic-inh GrCs",...
    "Fig3b,c: Water v DA all GrCs",...
    "Fig3d-g: Water v DA antic GrCs",...
    "EDFig3a: Water v DA antic supp GrCs",...
    "Fig5b,e: Water v DA all CFs"];
nrasters=length(rasterlist);
rastercols = {["rew"],["rew","omit"],["rew","omit"],["rew"],...
    ["rew","omit"],["rew","omit"],["rew"]};
rasterctyps = ["GrCs","GrCs","GrCs","GrCs","GrCs","GrCs","CFs"];
rasterrows = {["1-s DA","2-s DA"],["1-s DA","2-s DA"],...
    ["1-s DA","2-s DA"],["Water","1-s DA"],...
            ["Water","1-s DA"],["Water","1-s DA"],["1-s DA","Water"]};
rastercgrps = ["all","ant_sig","anti_sig","all","ant_sig","anti_sig","all"];
rastersorts = ["prerewSortIx","sortIx","sortIxi","prerewSortIx","sortIx","sortIxi","prerewSortIx"];
xllist = {[-1 4],[-1 4],[-1 4],[-1 3],[-1 3],[-1, 3],[-2 2]};
rasterscs = {sc1,sc_ant,sc_ant,sc1,sc1,sc1,sc_spikerate};
rasterhandles = [];
for ra = 1:nrasters
    ncols = length(rastercols{ra});
    nrows = length(rasterrows{ra});
    rasterhandles(ra)=figure(pos=[1151 296 456*ncols 468*nrows]);
    t=tiledlayout(nrows,ncols,tilesp="compact",pad="compact");
    curaxs=[];
for nrow = 1:nrows
    for ncol=1:ncols
        signame = "all"+rasterctyps(ra)+"_"+rastercols{ra}(ncol);
        r = find(rtyps==rasterrows{ra}(nrow));
        cursig = eval(signame+"{"+r+"}");
        curinf = eval(rasterctyps(ra)+"ChronInfo{"+r+"}");
        sortuse=eval("curinf."+rastersorts(ra));
        cuse = 1:length(sortuse);
        if ismember("Water",rasterrows{ra}) && rasterrows{ra}(nrow)=="1-s DA" && rasterctyps(ra)=="GrCs"
            cuse = cuse(~ismissing(dirTable(curinf.sessionNum(cuse),"WaterDir")));
        end
        cgrp=cuse;
        if rastercgrps(ra)~="all"
            cuse = intersect(cuse,eval(rastercgrps(ra)+"{"+r+"}"));
        end
        if rastercols{ra}(ncol)=="omit"
            noomit = find(all(isnan(cursig),2));
            cuse=setdiff(cuse,noomit); 
        end
        sortuse=sortuse(ismember(sortuse,cuse));
        endAdd2=endAdd;
        if r==4 && endAdd2~=0, endAdd2=2; end
        curaxs(end+1)=nexttile;
        cursc = rasterscs{ra};
        if rasterctyps(ra)=="GrCs"
            imagesc(tplt_tmplt_s,[],cursig(sortuse,:),cursc);
            hold on; plot([0 0]+endAdd2,ylim,'k',[-1 -1]+endAdd,ylim,'k'); 
        else
            imagesc(tplt_tmplt_s_CF,[],cursig(sortuse,:),cursc);
            hold on; plot([0 0],ylim,'k',[-1 -1],ylim,'k'); 
        end
        if ncol==1 
            titstr = rasterrows{ra}(nrow); 
            tmpnm = length(unique(mname(curinf.sessionNum(cuse))));
            titstr=titstr+": "+length(cuse)+" cells ("+round(length(cuse)/length(cgrp)*100,2)+"%),"+tmpnm+" mice";
            ylabel(titstr);
        end
        title(rasterrows{ra}(nrow)+"_"+rastercols{ra}(ncol),interp="none");
        if length(cuse)<200, yticks(0:50:200);
        elseif length(cuse)<500, yticks(0:50:500);
        elseif length(cuse)<1000, yticks(0:100:1000)
        elseif length(cuse)<2000, yticks(0:200:2000)
        else, yticks(0:500:5000);
        end
        if nrow==nrows && (ncol==ncols || (contains(rasterlist(ra), "Water v DA") && contains(rasterlist(ra), "GrCs"))), hcb=colorbar; ylabel(hcb,"Activity (zsc)"); end
        xlim(xllist{ra})
    end
end
title(t,rasterlist(ra));
ylabel(t,rasterctyps(ra));
xlabel(t,"Time relative to movement (s)");
figureformat_forsaving(true);
export_nature_master(gcf,xlout,exportSrcData);
end
%% Plot unaligned single-cell averages for Water v  DA
rng(0);
ccplt = [0.157 0.471 0.231; 0.659 0.086 0.541; 0.5 0 0.5; 0.318 0.698 0.961]; 
ebrows = ["rew","omit"];
ebcols = {["GrCs"]};
coltitls = {["Fig3k,l: Positive delay-ramping"]};
rasterylbls = ["Rewarded","Omitted reward"];
ebgrps = {["ant_sig"]};
eblines = {{["Water","1-s DA"]}};
ebxls = {[-1 3]};
nrows = length(ebrows);
for rd = 1:length(coltitls)
ncols = length(ebcols{rd});
figure(pos=[1696         374         490*ncols         781]);
t=tiledlayout(nrows,ncols,tilesp="compact",pad="compact");
ax=[];
lh={};
leglabls=cell(ncols,1);
for nrow = 1:nrows
    for ncol =1:ncols
    ax(nrow,ncol)=nexttile;
    signame = "all"+ebcols{rd}(ncol)+"_"+ebrows(nrow);
    lh{nrow,ncol} = [];
    nlines = length(eblines{rd}{ncol});
    for l = 1:nlines
    r = find(rtyps==eblines{rd}{ncol}(l));
    cursig = eval(signame+"{"+r+"}");
    curcgrp = eval(ebgrps{rd}(ncol)+"{"+r+"}");
    if ~isempty(curcgrp)
    if rasterrows{ra}(nrow)=="omit" 
        noomit = find(all(isnan(cursig),2));
        curcgrp=setdiff(curcgrp,noomit); 
    end
    curinf = eval(ebcols{rd}(ncol)+"ChronInfo{"+r+"}");
    if ismember("Water",eblines{rd}{ncol}) && ebcols{rd}(ncol)=="GrCs"
        curcgrp = curcgrp(~ismissing(dirTable.WaterDir(curinf.sessionNum(curcgrp))));
        superset = find(~ismissing(dirTable.WaterDir(curinf.sessionNum)));
    else, superset = 1:size(cursig,1);
    end
    endAdd2=endAdd;
    tmpcuse = cursig(curcgrp,:);
    leglabls{ncol}(l)=eblines{rd}{ncol}(l)+" ("+round(length(curcgrp)/length(superset)*100)+"%)"+...
        ", "+length(curcgrp)+" cells, "+length(unique(mname(curinf.sessionNum(superset))))+" mice";
    if ebcols{rd}(1)=="GrCs"
        lh{nrow,ncol}(l) = errorbar_shadeSEM(tplt_tmplt_s,tmpcuse',ccplt(r,:));
    else
        lh{nrow,ncol}(l) = errorbar_shadeSEM(tplt_tmplt_s_CF,tmpcuse',ccplt(r,:));
    end
    end
    end
    drawnow; pause(0.1);
    hold on; plot(xlim,[0 0],'k')
    ylim tight;
    xlim(ebxls{rd});
    xticks(ebxls{rd}(1):ebxls{rd}(2))
    end
end
ylabel(t,rasterylbls(nrow)+" activity (zsc)");
title(t,coltitls{rd}(ncol)+" "+ebcols{rd}(ncol)); 
xlabel(t,"Time relative to movement (s)"); 
arrayfun(@(x)linkaxes(ax(:,x)),1:ncols);
for nrow=1:nrows
    for ncol=1:ncols
        axes(ax(nrow,ncol))
        hold on; plot([0 0]+endAdd2,ylim,'k',[-1 -1]+endAdd,ylim,'k'); 
        if ncol==1 || rd==2, plot([0 0]+endAdd2+1,ylim,'k'); end
        yl=ylim;
        if ebcols{rd}(ncol)=="GrCs", yticks(round(yl(1),1):0.1:round(yl(end),1))
        else, yticks(round(yl(1)):0.5:round(yl(end)))
        end
    end
end
for ncol=1:ncols
axes(ax(1,ncol)); legend(lh{1,ncol},leglabls{ncol},...
    'location','northeast','Box','off'); 
end
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
end

ruse=[2 4];
violincell({GrCsChronInfo{2}.delay_activ_cent_4s,GrCsChronInfo{4}.delay_activ_cent_4s},...
    col=ccplt(ruse,:),Kernel="parabolic",bandw=0.05,medians=true); 
xlim tight; ylim tight;
ylabel("Center of activity (reward omission) rel to movement (s)")
xticklabels(rtyps([2 4]))
xlabel("DA delay")
titstr=string(gca().Title.String);
title(["Fig2o";titstr])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

figure;
h=[];
ruse=[2,4];
for rr = 1:2
    r=ruse(rr);
xct = 2.5;
winxc = winfn([0 4],tplt_tmplt_s);
curcgrp = 1:size(allGrCs_omit{r},1);
test = arrayfun(@(x)xcorr(allGrCs_omit{r}(x,winxc),round(xct/mean(diff(tplt_tmplt_s))),"normalized"),curcgrp,unif=0);
[~,lags] = xcorr(allGrCs_omit{r}(1,winxc),round(xct/mean(diff(tplt_tmplt_s))),"normalized");
test = double(cat(1,test{:}));
test2=test;
test(:,lags==0)=nan;
xcors = [];
scnt=1;
for s = 1:ndirs
    curcs=find(GrCsChronInfo{r}.sessionNum==s);
    if ~isempty(curcs)
        xcors(scnt,:)=mean(test(curcs,:),1);
        scnt=scnt+1;
    end
end
h(rr)=errorbar_shadeSEM(lags*dtim_tmplt,xcors',ccplt(r,:));
axis tight;
xlim([-2 2]);
xlabel("Lag (s)");
ylabel("Autocorrelation (normalized)");
ix1=find(lags==0,1);
lags = lags*dtim_tmplt;
if ~exist("testhalf","var") || length(testhalf)<4 || isempty(testhalf{r})
for c = 1:size(xcors,1)
    tmp=mean([xcors(c,ix1:end); xcors(c,ix1:-1:1)],1)';
    tmp(1)=1;
    if all(~isnan(tmp(:)))
    junk = fit(lags(ix1:end)',tmp,'exp1');
    junk = -1/junk.b;
    testhalf{r}(c)=junk;
    else
        testhalf{r}(c)=0;
    end
end
end
end
legend(h,["1-s","2-s"])
yticks(0:.1:1)
title("Fig2p");
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

if exist("testhalf","var"), 
    barwitherr_stde({testhalf{2},testhalf{4}},col=ccplt([2 4],:),...
        medians=true,dots=true,titl="EDFig2a"); 
    ylabel("Autocorrelation exp tau");
    xticklabels(rtyps([2 4]))
    xlabel("DA delay")
    figureformat_forsaving;
    export_nature_master(gcf,xlout,exportSrcData);
end
%% Cell numbers, percentages, MFB/VTA breakdown, etc
rng(0);
% Rew v omission 1-s/2-s antic
anticDA_haswater = ant_sig{2}(ismember(GrCsChronInfo{2}.sessionNum(ant_sig{2}),mgrps.DA1s_grcs_haswater));
anticiDA_haswater = anti_sig{2}(ismember(GrCsChronInfo{2}.sessionNum(anti_sig{2}),mgrps.DA1s_grcs_haswater));
allgrchaswater = find(ismember(GrCsChronInfo{2}.sessionNum,mgrps.DA1s_grcs_haswater));
ccplt = [0.157 0.471 0.231; 0.659 0.086 0.541; 0.5 0 0.5; 0.318 0.698 0.961]; 
figure(pos=[1     1   332   407]);
t=tiledlayout(2,1,tilesp="compact");
nexttile(1)
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(ant_sig{2},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{2}(ant_sig{2},:)',[1 0 0]);
legend([h1 h2],["Rewarded","Omitted"])
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[1 1],ylim,'k');
title("Fig2s: "+length(ant_sig{2})+" cells ("+round(length(ant_sig{2})/size(allGrCs_rew{2},1)*100)+"%)")
nexttile(2)
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{4}(ant_sig{4},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{4}(ant_sig{4},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[2 2],ylim,'k');
xlabel("Time relative to movement (s)")
ylabel(t,"Fluorescence (zsc)")
title("Fig2t: "+ length(ant_sig{4})+" cells ("+round(length(ant_sig{4})/size(allGrCs_rew{4},1)*100)+"%)")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

% 1-s v 2-s rewarded antic
figm([132 409 332 275]);
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(ant_sig{2},:)',ccplt(2,:));
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{4}(ant_sig{4},:)',ccplt(4,:));
uistack([h1 h2],"top")
ylim tight;
hold on;
plot([0 0],ylim,'k',[1 1],ylim,'k');
titstr="EDFig4d: "+length(ant_sig{2})+" cells ("+round(length(ant_sig{2})/size(allGrCs_rew{2},1)*100)+"%)";
xlabel("Time relative to movement (s)")
ylabel("Fluorescence (zsc)")
title([titstr,length(ant_sig{4})+" cells ("+round(length(ant_sig{4})/size(allGrCs_rew{4},1)*100)+"%)"]);
legend([h1 h2],["1-s","2-s"])
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

% Rew v omission CF DA H2O
figm([1     1   332   407]);
t=tiledlayout(2,1,tilesp="compact");
ax=[];
ax(1)=nexttile(1);
h1=errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_rew{2}(post{2},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_omit{2}(post{2},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[1 1],ylim,'k');
legend([h1 h2],["Rewarded","Omitted"])
ax(2)=nexttile(2);
h1=errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_rew{1}(post{1},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_omit{1}(post{1},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
linkaxes(ax);
plot([0 0],ylim,'k',[1 1],ylim,'k');
xlabel("Time relative to movement (s)")
ylabel(t,"CF spike rate (zsc)")
nwater = length(post{1}); nDA=length(post{2}); tmpnmice=(nvs.CF_DA);
pctwater = round(nwater/size(allCFs_rew{1},1),2)*100; pctDA = round(nDA/size(allCFs_rew{2},1),2)*100;
title(ax(1),["Fig5c: water ("+pctwater+"%, "+nwater+" CFs), "+"DA ("+pctDA+"%, "+nDA+" CFs), ",tmpnmice+" mice"],fontweight="normal") 
title(ax(2),"Fig5f")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% Rew CF time to peak
[tmpwin,tmpwin_s] = winfn(tplt_tmplt_s_CF,[0 0.5]);
time2peakCF={};
[~,tmp] = max(allCFs_rew{2}(post{2},tmpwin),[],2);
time2peakCF{1} = tmpwin_s(tmp);
[~,tmp] = max(allCFs_rew{1}(post{1},tmpwin),[],2);
time2peakCF{2} = tmpwin_s(tmp);
violincell(time2peakCF,col=[0.5 0 0.5; 0.5 0.5 0],...
    Kernel="parabolic",bandw=0.01,medians=true,orient="horizontal"); 
xticklabels(["DA","Water"]);
ylabel("Peak response tim rel to reward (s)")
titstr=string(gca().Title.String);
title(["Fig5j";titstr]);
axis tight;
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);


% mfb v vta GrC
GrCs_DA1s_MFB_all = find(ismember(GrCsChronInfo{2}.sessionNum,mgrps.DA1s_grcs_mfb));
GrCs_DA1s_VTA_all = find(ismember(GrCsChronInfo{2}.sessionNum,mgrps.DA1s_grcs_dat));
GrCs_DA1s_MFB = intersect(ant_sig{2},GrCs_DA1s_MFB_all);
GrCs_DA1s_VTA = intersect(ant_sig{2},GrCs_DA1s_VTA_all);
GrCs_DA1s_MFB = intersect(GrCsChronInfo{2}.sortIx,GrCs_DA1s_MFB,'stable');
GrCs_DA1s_VTA = intersect(GrCsChronInfo{2}.sortIx,GrCs_DA1s_VTA,'stable');
% mfb v vta rasters GrC
figure;
t=tiledlayout(2,1,tilesp="compact");
nexttile(1)
imagesc(tplt_tmplt_s,[],allGrCs_rew{2}(GrCs_DA1s_MFB,:),[-0.3 0.3]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]); colorbarm("Fluorescence (zsc)");
ncur = length(GrCs_DA1s_MFB); curpct = round(ncur/length(GrCs_DA1s_MFB_all)*100);
title("EDFig5a-MFB, "+ncur+" GrCs, "+curpct+"%, "+ length(unique(dirTable.mname(mgrps.DA1s_grcs_mfb)))+" mice")
nexttile(2)
imagesc(tplt_tmplt_s,[],allGrCs_rew{2}(GrCs_DA1s_VTA,:),[-0.3 0.3]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]); colorbarm("Fluorescence (zsc)");
ncur = length(GrCs_DA1s_VTA); curpct = round(ncur/length(GrCs_DA1s_VTA_all)*100);
title("EDFig5a-VTA, "+length(GrCs_DA1s_VTA)+" GrCs, "+curpct+"%, "+length(unique(dirTable.mname(mgrps.DA1s_grcs_dat)))+" mice")
ylabel(t,"Ramping GrCs");
xlabel("Time relative to movement (s)")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% mfb v vta line plots ant GrCs
figure;
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(GrCs_DA1s_MFB,:)',[0 0 1]);
ncur = length(GrCs_DA1s_MFB); curpct = round(ncur/length(GrCs_DA1s_MFB_all)*100);
titstr="MFB, "+ncur+" GrCs, "+curpct+"%, "+ length(unique(dirTable.mname(mgrps.DA1s_grcs_mfb)))+" mice";
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(GrCs_DA1s_VTA,:)',[1 0 1]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]); 
legend([h1 h2],["MFB","VTA"]);
ncur = length(GrCs_DA1s_VTA); curpct = round(ncur/length(GrCs_DA1s_VTA_all)*100);
title(["EDFig5d: "+titstr,"VTA, "+length(GrCs_DA1s_VTA)+" GrCs, "+curpct+"%, "+length(unique(dirTable.mname(mgrps.DA1s_grcs_dat)))+" mice"])
ylabel("Activity (zsc)");
xlabel("Time relative to movement (s)")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% mfb v vta antic ramp mag GrC
mags={GrCsChronInfo{2}.prerew_grc(GrCs_DA1s_MFB),GrCsChronInfo{2}.prerew_grc(GrCs_DA1s_VTA)};
violincell(mags,col=[0.5 0 0.5; 0.5 0.5 0],...
    Kernel="parabolic",bandw=0.01,medians=true); 
xlim tight; ylim tight;
ylabel("Delay ramp magnitude (zsc)");
xticklabels(["MFB","VTA"]);
titstr=string(gca().Title.String);
title(["EDFig5b";titstr])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% mfb v vta GrC
duse = {mgrps.DA1s_grcs_mfb,mgrps.DA1s_grcs_dat};
ruse = [2 2];
fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(ant_sig{r})==x),duse{d});
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),duse{d});
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt([1 2],:),titl="EDFig5c")
ylabel("Positive delay-ramping (% of GrCs)");
xticklabels(["MFB","VTA"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% rew v omission antic inhib 1-s/2-s
figure;
t=tiledlayout(2,1,tilesp="compact");
nexttile(1);
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(anti_sig{2},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{2}(anti_sig{2},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[1 1],ylim,'k');
hold on; plot(xlim,[0 0],'k')
legend([h1 h2],["Rewarded","Omitted"])
n1s = length(anti_sig{2}); n2s=length(anti_sig{4});  
pct1s = round(n1s/size(allGrCs_rew{2},1),2)*100; pct2s = round(n2s/size(allGrCs_omit{4},1),2)*100;
title("EDFig2e-1s ("+pct1s+"%, "+n1s+" GrCs), "+nvs.DA1s_grcs+" mice",fontweight="normal",fontsize=9) 

nexttile(2)
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{4}(anti_sig{4},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{4}(anti_sig{4},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[2 2],ylim,'k');
hold on; plot(xlim,[0 0],'k')
title("EDFig2e-2s ("+pct2s+"%, "+n2s+" GrCs), "+nvs.DA2s_grcs+" mice",fontweight="normal",fontsize=9) 
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% rew v omission antic inhib DA/water
figure;
t=tiledlayout(2,1,tilesp="compact");
nexttile(1)
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{2}(anticiDA_haswater,:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{2}(anticiDA_haswater,:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[1 1],ylim,'k');
hold on; plot(xlim,[0 0],'k')
nDA = length(anticiDA_haswater); nH2O=length(anti_sig{1});  
pctDA = round(nDA/length(allgrchaswater),2)*100; pctH2O = round(nH2O/size(allGrCs_omit{1},1),2)*100;
legend([h1 h2],["Rewarded","Omitted"])
title("EDFig3b-DA ("+pctDA+"%, "+nDA+" GrCs), ",fontweight="normal",fontsize=9) 

nexttile(2)
h1=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_rew{1}(anti_sig{1},:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,allGrCs_omit{1}(anti_sig{1},:)',[1 0 0]);
uistack([h1 h2],"top")
ylim tight;
plot([0 0],ylim,'k',[1 1],ylim,'k');
hold on; plot(xlim,[0 0],'k')
title("EDFig3b-water ("+pctH2O+"%, "+nH2O+" GrCs), "+nvs.DA1s_grcs_haswater+" mice",fontweight="normal",fontsize=9) 
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% rew v omit 1-s/2-s CDFs
f=figure;
prlim=[1.4 1.7];
postrew_win = winfn(tplt_tmplt_s,prlim);
postrew = median(allGrCs_rew{2}(ant_sig{2},postrew_win),2);
postomit = median(allGrCs_omit{2}(ant_sig{2},postrew_win),2);
postrew_win = winfn(tplt_tmplt_s,prlim+1);
postrew2 = median(allGrCs_rew{4}(ant_sig{4},postrew_win),2);
postomit2 = median(allGrCs_omit{4}(ant_sig{4},postrew_win),2);
xbin = -0.5:.01:1.5;
t=tiledlayout(2,1);
nexttile(1);
histogram_cell({postrew,postomit},xbin,title="1-s DA Delay",col=[0 0 1; 1 0 0],fig=f);
titstr=string(gca().Title.String);
title(["Fig2u";titstr]);
legend("rewarded","omitted reward")
xticks([-0.5:.5:1])
xlim([-0.45 1.15])
nexttile(2);
histogram_cell({postrew2,postomit2},xbin,title="2-s DA Delay",col=[0 0 1; 1 0 0],fig=f);
ylabel(t,"Cumulative frac of delay-ramping GrCs");
xlabel("Post-reward/omission activity (zsc)");
xticks([-0.5:.5:1])
xlim([-0.45 1.15])
titstr=string(gca().Title.String);
title(["Fig2v";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% rew v omit water/DA CDFs
f=figure;
postrew_win = winfn(tplt_tmplt_s,prlim);
postrew = median(allGrCs_rew{2}(anticDA_haswater,postrew_win),2);
postomit = median(allGrCs_omit{2}(anticDA_haswater,postrew_win),2);
postrew2 = median(allGrCs_rew{1}(ant_sig{1},postrew_win),2);
postomit2 = median(allGrCs_omit{1}(ant_sig{1},postrew_win),2);
t=tiledlayout(2,1);
nexttile(1);
xt = -0.35:.005:0.9;
histogram_cell({postrew2,postomit2},xt,title="Water reward",col=[0 0 1; 1 0 0],fig=f);
legend("rewarded","omitted reward")
titstr=string(gca().Title.String);
title(["Fig3m";titstr]);
nexttile(2);
xt = -0.3:.005:0.9;
histogram_cell({postrew,postomit},xt,title="DA Reward",col=[0 0 1; 1 0 0],fig=f);
ylabel(t,"Cumulative frac of delay-ramping GrCs")
xlabel("Post-reward/omission activity (zsc)")
titstr=string(gca().Title.String);
title(["Fig3n";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water-first v DA-first
GrCs_sessions_waterFirst = find(dirTable.Delay==1 & dirTable.GrCs=="Y" & dirTable.FirstRew=="water");
GrCs_sessions_DAFirst = find(dirTable.Delay==1 & dirTable.GrCs=="Y" & dirTable.FirstRew=="DA");
GrCs_waterFirst = find(ismember(GrCsChronInfo{2}.sessionNum,GrCs_sessions_waterFirst));
GrCs_DAFirst = find(ismember(GrCsChronInfo{2}.sessionNum,GrCs_sessions_DAFirst));
GrCs_waterFirst_ant = intersect(ant_sig{2},GrCs_waterFirst);
GrCs_DAFirst_ant = intersect(ant_sig{2},GrCs_DAFirst);
GrCs_waterFirst_ant = intersect(GrCsChronInfo{2}.sortIx,GrCs_waterFirst_ant,'stable');
GrCs_DAFirst_ant = intersect(GrCsChronInfo{2}.sortIx,GrCs_DAFirst_ant,'stable');
% water-first v DA-first rasters
figure(pos=[665   736   350   290]);
t=tiledlayout(2,1,tilesp="tight");
nexttile(1)
imagesc(tplt_tmplt_s,[],allGrCs_rew{2}(GrCs_DAFirst_ant,:),[-0.3 0.3]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]); colorbarm("Fluorescence (zsc)");
title("DA-first ("+round(length(GrCs_DAFirst_ant)/length(GrCs_DAFirst)*100)+"%)")
nexttile(2)
imagesc(tplt_tmplt_s,[],allGrCs_rew{2}(GrCs_waterFirst_ant,:),[-0.3 0.3]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]); colorbarm("Fluorescence (zsc)");
ylabel(t,"DA ramping GrCs")
xlabel("Time relative to movement (s)")
title("Water-first ("+round(length(GrCs_waterFirst_ant)/length(GrCs_waterFirst)*100)+"%)")
title(t,"EDFig3c: ",fontsize=8)
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water-first v DA-first mag violin
mags={GrCsChronInfo{2}.prerew_grc(GrCs_DAFirst_ant),GrCsChronInfo{2}.prerew_grc(GrCs_waterFirst_ant)};
violincell(mags,col=[0.5 0 0.5; 0.5 0.5 0],...
    Kernel="parabolic",bandw=0.01,medians=true); 
xlim tight; ylim tight;
ylabel("Delay ramp magnitude (zsc)");
xticklabels(["DA (DA-first)","DA (Water-first)"]);
titstr=string(gca().Title.String);
title(["EDFig3f";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% water-first v DA-first prevalence bars
duse = {GrCs_sessions_DAFirst,GrCs_sessions_waterFirst};
ruse = [2 2];
fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(ant_sig{r})==x),duse{d});
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),duse{d});
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt(ruse,:),titl="EDFig3d")
ylabel("Positive delay-ramping (% of GrCs)");
xticklabels(["DA (DA-first)","DA (Water-first)"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(anti_sig{r})==x),duse{d});
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),duse{d});
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt(ruse,:),title="EDFig3e")
ylabel("Negative delay-ramping (% of GrCs)");
xticklabels(["DA (DA-first)","DA (Water-first)"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);


% mfb v vta CFs
CFs_MFB_all = find(ismember(CFsChronInfo{2}.sessionNum,mgrps.CFs_MFB));
CFs_VTA_all = find(ismember(CFsChronInfo{2}.sessionNum,mgrps.CFs_VTA));
CFs_MFB = intersect(post{2},CFs_MFB_all);
CFs_VTA = intersect(post{2},CFs_VTA_all);
CFs_MFB = intersect(CFsChronInfo{2}.sortIx,CFs_MFB,'stable');
CFs_VTA = intersect(CFsChronInfo{2}.sortIx,CFs_VTA,'stable');

% mfb v vta rasters
figm([97 763 310 376]);
t=tiledlayout(2,1,tilesp="compact");
nexttile(1)
imagesc(tplt_tmplt_s_CF,[],allCFs_rew{2}(CFs_MFB,:),[0.4 1.8]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-2 2]); colorbarm("Spike rate (Hz)");
ncur = length(CFs_MFB); curpct = round(ncur/length(CFs_MFB_all)*100);
title("EDFig8a: MFB, "+ncur+" CFs, "+curpct+"%, "+ length(unique(dirTable.mname(mgrps.CFs_MFB)))+" mice")
nexttile(2)
imagesc(tplt_tmplt_s_CF,[],allCFs_rew{2}(CFs_VTA,:),[0.4 1.8]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-2 2]); colorbarm("Spike rate (Hz)");
ncur = length(CFs_VTA); curpct = round(ncur/length(CFs_VTA_all)*100);
title("EDFig8b: VTA, "+length(CFs_VTA)+" CFs, "+curpct+"%, "+length(unique(dirTable.mname(mgrps.CFs_VTA)))+" mice")
ylabel(t,"DA-responsive CFs");
xlabel(t,"Time relative to movement (s)")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% mfb v vta rew CF line plot
figm([97 763 310 376]);
t=tiledlayout(2,1,tilesp="compact");
nexttile(1)
errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_rew{2}(CFs_MFB,:)',[0 0 1]);
ylim tight; yl=ylim;
hold on; plot([0 0],ylim,'k',[-1 -1],ylim,'k'); xlim([-2 2]); 
ncur = length(CFs_MFB); curpct = round(ncur/length(CFs_MFB_all)*100);
title("EDFig8c: MFB, "+ncur+" CFs, "+curpct+"%, "+ length(unique(dirTable.mname(mgrps.CFs_MFB)))+" mice")
nexttile(2)
errorbar_shadeSEM(tplt_tmplt_s_CF,allCFs_rew{2}(CFs_VTA,:)',[0 0 1]);
ylim(yl);
hold on; plot([0 0],ylim,'k',[-1 -1],ylim,'k'); xlim([-2 2]); 
ncur = length(CFs_VTA); curpct = round(ncur/length(CFs_VTA_all)*100);
title("EDFig8d: VTA, "+length(CFs_VTA)+" CFs, "+curpct+"%, "+length(unique(dirTable.mname(mgrps.CFs_VTA)))+" mice")
ylabel(t,"DA-responsive CF fluorescence (zsc)");
xlabel(t,"Time relative to movement (s)")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% mfb v vta antic ramp mag
mags={CFsChronInfo{2}.postrew(CFs_MFB),CFsChronInfo{2}.postrew(CFs_VTA)};
violincell(mags,col=[0.5 0 0.5; 0.5 0.5 0],...
    Kernel="parabolic",bandw=0.1,medians=true); 
xlim tight; ylim tight;
yl=ylim; ylim([0 yl(2)]);
ylabel("DA response magnitude (Hz)");
xticklabels(["MFB","VTA"]);
titstr=string(gca().Title.String);
title(["EDFig8f";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
% mfb v vta CF prevalence bars
duse = {mgrps.CFs_MFB,mgrps.CFs_VTA};
ruse = [2 2];
fracs={}; denom_all={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum(post{r})==x),duse{d});
denom=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum==x),duse{d});
denom_all{d}=denom;
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt([1 2],:),dotsc=denom_all,titl="EDFig8e")
ylabel("DA-responsive CFs (%)");
xticklabels(["MFB","VTA"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
%% Cell precentages and mags
rng(0);
% 1s 2s pos antic
duse = {mgrps.DA1s_grcs,mgrps.DA2s_grcs};
ruse = [2 4];
fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(ant_sig{r})==x),duse{d});
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),duse{d});
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt(ruse,:),titl="Fig2m")
ylabel("Positive delay-ramping (% of GrCs)");
xticklabels(rtyps(ruse))
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% 1s 2s neg antic
fracs_i={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(anti_sig{r})==x),duse{d});
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),duse{d});
fracs_i{d}=numer./denom*100;
end
barwitherr_stde(fracs_i,dots=true,color=ccplt(ruse,:),title="Fig2n")
ylabel("Negative delay-ramping (% of GrCs)");
xticklabels(rtyps(ruse))
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da pos antic
DA1s_grcs_haswater = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y");
ruse = [1 2];
fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(ant_sig{r})==x),DA1s_grcs_haswater);
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),DA1s_grcs_haswater);
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt(ruse,:),paired=true,title="Fig3h")
ylabel("Delay-ramping (% of GrCs)");
xticklabels(rtyps(ruse))
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da neg antic
DA1s_grcs_haswater = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.GrCs=="Y");
ruse = [1 2];
fracs={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum(anti_sig{r})==x),DA1s_grcs_haswater);
denom=arrayfun(@(x)nnz(GrCsChronInfo{r}.sessionNum==x),DA1s_grcs_haswater);
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,color=ccplt(ruse,:),paired=true,title="Fig3i")
ylabel("Neg delay-ramping (% of GrCs)");
xticklabels(rtyps(ruse))
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da pos antic mag
mags={GrCsChronInfo{1}.prerew_grc(ant_sig{1}),GrCsChronInfo{2}.prerew_grc(anticDA_haswater)};
violincell(mags,col=ccplt(ruse,:),...
    Kernel="parabolic",bandw=0.01,medians=true); 
xlim tight; ylim tight;
ylabel("Delay ramp magnitude (zsc)");
xticklabels(rtyps(ruse))
ylim tight;
titstr=string(gca().Title.String);
title(["Fig3j";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da rew CFs
DA1s_CFs = find(dirTable.Delay==1 & dirTable.CFType~="none");
water_CFs = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir) & dirTable.CFType~="none");
duse = {DA1s_CFs,water_CFs};
ruse = [2 1];
fracs={};
denom_all={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum(post{r})==x),duse{d});
denom=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum==x),duse{d});
denom_all{d}=denom;
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,col=ccplt(ruse,:),dotsc=denom_all,titl="Fig5g")
ylabel("Reward-responding (% of CFs)");
xticklabels(rtyps(ruse))
ax1=gca;
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da mv CFs
fracs={};
denom_all={};
for d = 1:2
r=ruse(d);
numer=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum(mvCFs{r})==x),duse{d});
denom=arrayfun(@(x)nnz(CFsChronInfo{r}.sessionNum==x),duse{d});
denom_all{d}=denom;
fracs{d}=numer./denom*100;
end
barwitherr_stde(fracs,dots=true,col=ccplt(ruse,:),dotsc=denom_all,titl="Fig5h")
ylabel("Reach-responding (% of CFs)");
xticklabels(rtyps(ruse))
linkaxes([gca,ax1])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% water da rew CF mags
mags={CFsChronInfo{2}.postrew(post{2}),CFsChronInfo{1}.postrew(post{1})};
violincell(mags,col=ccplt(ruse,:),...
    Kernel="parabolic",bandw=0.06,medians=true); 
ylabel("CF Reward response (zsc)");
xticklabels(rtyps(ruse))
ylim tight;
titstr=string(gca().Title.String);
title(["Fig5i";titstr]);
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
%% Basis sets unaligned
nGrCTot = cellfun(@(x)(size(x,1)),allGrCs_rew);
titstrs = ["Fig2w","Fig2x"];
clear bins;
cuse = {1:nGrCTot(1),1:nGrCTot(2),[],1:nGrCTot(4)};
grcsuse = allGrCs_rew;
figure(pos=[593   265   484   594]);
[tpltdel,tpltdel_s] = winfn(tplt_tmplt_s,[-1.1 1.1]+endAdd);
t = tiledlayout(2,1,tilesp="compact",pad="compact");
a=[];
ruse=[2 4];
for kk = 1:length(ruse)
    k=ruse(kk);
    if k~=4, xb = [-1.1 -0.8 -0.6 -0.45 -0.35 -0.02]+endAdd;
    else, xb = [-1.1 -0.6 -0.2 0.2 0.6 0.95]+endAdd; end
    nb=length(xb)-1;
    cm = flipud(cool(nb));
    [~,~,bins{k}]=histcounts(GrCsChronInfo{k}.delay_activ_cent(cuse{k}),xb);
    a(end+1)=nexttile;
    clear h;
    for i = 1:nb
        tmp = grcsuse{k}(bins{k}==i,tpltdel);
    h(i)=errorbar_shadeSEM(tpltdel_s,tmp',cm(i,:),linew=1.2);
    hold on;
    end
    axis tight;
    uistack(h,"top")
    title([titstrs(kk),rtyps(k)+", bin cnts: "+strvec(arrayfun(@(x)nnz(bins{k}==x),1:max(bins{k}))),"bin edges: "+strvec(xb)])
end
for k = 1:length(a), nexttile(k); hold on; plot([-1 -1]+endAdd,ylim,'k',[0 0]+endAdd,ylim,'k',[0 0]+(endAdd~=0)*2,ylim,'k'); end
xlabel(t,"Time rel to movement (s)");
ylabel(t,"Activity (zsc)");
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% v2 water/DA cell identity alignment
rng(0);
refix = 2; secix = setdiff(1:2,refix);
grc_chron_ref = find(GrCsChronInfo{refix}.otherCellNum>0);
[~,grc_chron_sec] = ismember(GrCsChronInfo{refix}{grc_chron_ref,["sessionNum","otherCellNum"]},...
    GrCsChronInfo{secix}{:,["sessionNum","cellNum"]},'rows');
chronGrCsDA=allGrCs_rew{refix}(grc_chron_ref,:);
chronGrCsH2O=allGrCs_rew{secix}(grc_chron_sec,:);
CF_chron_ref = find(CFsChronInfo{refix}.otherCellNum>0);c;
chronCFsDA=allCFs_rew{refix}(CF_chron_ref,:);
[~,CF_chron_sec] = ismember(CFsChronInfo{refix}{CF_chron_ref,["sessionNum","otherCellNum"]},...
    CFsChronInfo{secix}{:,["sessionNum","cellNum"]},'rows');
chronCellNums = {[grc_chron_sec grc_chron_ref],[CF_chron_sec CF_chron_ref]};
chronCFsH2O=allCFs_rew{secix}(CF_chron_sec,:);

tmp = intersect(post{2},CF_chron_ref);
[~,chronRewDA_CFs] = ismember(tmp,CF_chron_ref);
tmp = intersect(post{1},CF_chron_sec);
[~,chronRewH2O_CFs] = ismember(tmp,CF_chron_sec);
chronRewBoth_CFs = intersect(chronRewH2O_CFs,chronRewDA_CFs);
nChronGrC = length(grc_chron_ref);
nChronCF = length(CF_chron_ref);
windel=[-1 1];
ixdel = winfn(tplt_tmplt_s,windel);
% control for R3
ixdelrm = winfn(tplt_tmplt_s,[-.2 0.1]);
ixdel = setdiff(ixdel,ixdelrm);
%
ixuse = ixdel;
[water_DA_corr,corrp] = corr(chronGrCsDA(:,ixuse)',chronGrCsH2O(:,ixuse)');
corrp=diag(corrp);
water_DA_corr = diag(water_DA_corr);
[water_DA_corr_rand,corrp_rand] = corr(chronGrCsDA(:,ixuse)',chronGrCsH2O(randperm(size(chronGrCsH2O,1)),ixuse)');
corrp_rand=diag(corrp_rand);
water_DA_corr_rand = diag(water_DA_corr_rand);

% benjamini hochberg
% 1. Set False Discovery Rate (1%)
q_threshold = 0.01; 
% 2. Sort p-values ascending and keep track of original indices
m = length(corrp);
sorted_p = sort(corrp);
% 3. Calculate the Benjamini-Hochberg critical values
critical_values = (1:m)' / m * q_threshold;
% 4. Find the largest p-value that is less than its critical value
max_id = find(sorted_p <= critical_values, 1, 'last');
fdr_p_cutoff = sorted_p(max_id);    
% Find the minimum r-value that corresponds to this p-value
r_passed = water_DA_corr(corrp <= fdr_p_cutoff);
min_r_fdr = min(r_passed(r_passed > 0));
fprintf('FDR p-value cutoff: %.1e\n', fdr_p_cutoff);
fprintf('Effectively equivalent to r > %.2f\n', min_r_fdr);

issigs = corrp<fdr_p_cutoff & water_DA_corr>0;
issigs_rand = water_DA_corr_rand>0 & corrp_rand<fdr_p_cutoff;

sigchron = find(issigs);
disp(round(100*numel(sigchron)/numel(issigs))+"% of GrCs water-DA generalize");

sigchron_rand = find(issigs_rand);
disp("vs "+round(numel(sigchron_rand)/numel(issigs_rand)*100)+"% by chance");

nDA=arrayfun(@(x)micedats{x}.nc_right_green,mgrps.DA1s_grcs_haswater_matched);
nH2O=arrayfun(@(x)micedats{x}.waterdat.nc_right_green,mgrps.DA1s_grcs_haswater_matched);
nMatched = arrayfun(@(x)sum(all(micedats{x}.chronicGreen.finalMatchesMat~=0,2)),mgrps.DA1s_grcs_haswater_matched);
barwitherr_stde({nDA,nH2O,nMatched},dots=true,title="EDFig7e")
ylabel("GrCs per session")
xticklabels(["DA","Water","Matched"])
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% cross reward alignment
sigs = {chronGrCsH2O,chronGrCsDA;chronCFsH2O,chronCFsDA};
infs = {GrCsChronInfo,CFsChronInfo};
titstrs=["Fig4k-n","Fig5l-o"];
cbarlabls=["Fluorescence (zsc)","Spike rate (Hz)"];
xls = {[-1 3],[-2 2]};
for c = 1:2
    figure(pos=[1730         309        650         652]);
    t = tiledlayout(2,2,pad="compact",tilesp="compact");
for t1=  1:2
    for t2 = 1:2
            nexttile;
            cursig = sigs{c,t2};
            if c==1
                [~,cursort] = sort(infs{c}{t1}.prerew_grc(chronCellNums{c}(:,t1)));
            else
                [~,cursort] = ismember(infs{c}{t1}.sortIx,chronCellNums{c}(:,t1));
            end
            cursort = cursort(cursort~=0);
            clims = {[-0.3 0.3],[-0.3 0.3]; [0 1.8],[0 1.8]};
            if c==1,
            imagesc(tplt_tmplt_s,[],cursig(cursort,:),clims{c,t2});
            else
            imagesc(tplt_tmplt_s_CF,[],cursig(cursort,:),clims{c,t2});
            end
            if t1==2
                if endAdd==0, xlabel("Time rel to "+rtyps(t2)+" (s)"); 
                else, xlabel("Time rel to movement (s)");  end
            end
            if t2~=1
                yticklabels([]);
            end
            xlim(xls{c});
            hold on; plot([0 0]+endAdd,ylim,'k',[-1 -1]+endAdd,ylim,'k');
            if t2==2, 
                colorbarm(cbarlabls(c));
            end
            title(rtyps(t2)+" sorted by "+rtyps(t1)); 
    end
end
title(t,titstrs(c)+": "+size(cursig,1)+"cells",fontsize=9,fontweight="normal")
ylabel(t,cnames(c));
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
end
%% DA-H2O Correlated GrCs
figure(pos=[ 1182         113         560         238]); h=histogram(water_DA_corr(~issigs),-1:.1:1);
hold on; h2=histogram(water_DA_corr(issigs),h.BinEdges); 
xlabel("DA-H2O Correlation (r)"); ylabel("Number of GrCs")
hold on; xlim([-1 1]); 
legend([h,h2],["All tracked GrCs","DA-H2O-correlated ("+round(100*mean(issigs))+"%)"],location="NorthEast",AutoUpdate=0)
ylim(ylim.*[1 1.1]);
plot([0 0],ylim,'k',LineWidth=2)
title("Fig4o");
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

figure(pos=[ 1182         113         560         238]); h=histogram(water_DA_corr,h.BinEdges,DisplayStyle="stairs",EdgeColor=[1 0 0]);
hold on; h3=histogram(water_DA_corr_rand,h.BinEdges,DisplayStyle="stairs",EdgeColor=[0 0 0]); 
xlabel("DA-H2O Correlation (r)"); ylabel("Number of GrCs")
hold on; xlim([-1 1]); 
ylim(ylim.*[1 1.1]);
plot([0 0],ylim,'k',LineWidth=2)
legend([h h3],["True","Random"])
title("EDFig7f: p="+num2str(ranksum_disp(water_DA_corr,water_DA_corr_rand),2))
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

[~,grcchronsortix_DA]=sort(GrCsChronInfo{2}.half_del_act(grc_chron_ref(issigs)));
toplt = {chronGrCsDA(sigchron(grcchronsortix_DA),:),chronGrCsH2O(sigchron(grcchronsortix_DA),:)};
figure; 
t=tiledlayout(1,2,tilesp="tight"); 
for pl = 1:2
nexttile(pl);
imagesc(tplt_tmplt_s,[],toplt{pl},[-0.4,0.3])
axis tight; xlim([-2 2]+endAdd);
hold on; plot([0 0]+endAdd,ylim,'k',[-1 -1]+endAdd,ylim,'k');
xlabel("Time relative to movement (s)")
if pl==1, ylabel(length(sigchron)+" DA-H2O-correlated GrCs, "+round(length(sigchron)/...
    nChronGrC*100)+"% of total"); 
    title("DA reward");
else
yticklabels([]);
colorbarm("Fluorescence (zsc)")
title("Water reward")
end
end
title(t,"Fig4p")
export_nature_master(gcf,xlout,exportSrcData);
%% example Water-DA GrCs
grcchronsortix_DA_truenumsref = grc_chron_ref(sigchron(flipud(grcchronsortix_DA)));
grcchronsortix_DA_truenumssec = grc_chron_sec(sigchron(flipud(grcchronsortix_DA)));
scnumsDA=GrCsChronInfo{2}(grcchronsortix_DA_truenumsref,["sessionNum","cellNum"]);
scnumsH2O=GrCsChronInfo{1}(grcchronsortix_DA_truenumssec,["sessionNum","cellNum"]);
cshow=[];
cshow=cat(1,cshow,find(scnumsDA.sessionNum==24 & scnumsDA.cellNum==156));
cshow=cat(1,cshow,find(scnumsDA.sessionNum==15 & scnumsDA.cellNum==47));
cshow=cat(1,cshow,find(scnumsDA.sessionNum==24 & scnumsDA.cellNum==153));
cshow=cat(1,cshow,find(scnumsDA.sessionNum==16 & scnumsDA.cellNum==45));
titstrs=["Fig4q","Fig4r","EDFig7g","EDFig7h"];
for kk = 1:length(cshow)
    k=cshow(kk);
    figure(pos=[863   553   448   296]);
    curd = micedats{scnumsDA{k,"sessionNum"}};
    curc = scnumsDA{k,"cellNum"};
    truse = find(curd.goodMvmt & curd.rewarded);
    [tplt,tplt_s] = winfn(curd.tmpx_right,[-1 3]);
    trdat = squeeze(curd.endAlgn.sigFilt_right_green(truse,curc,tplt));
    h1=errorbar_shadeSEM(tplt_s,trdat',ccplt(2,:));
    ylabel("Fluorescence in DA (zsc)")
    axis tight;
    hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]);
    curd2 = micedats{scnumsDA{k,"sessionNum"}}.waterdat;
    curc = scnumsH2O{k,"cellNum"};
    truse2 = find(curd2.goodMvmt & curd2.rewarded);
    [tplt2,tplt_s2] = winfn(curd2.tmpx_right,[-1 3]);
    trdat2 = squeeze(curd2.endAlgn.sigFilt_right_green(truse2,curc,tplt2));
    yyaxis right;
    h2=errorbar_shadeSEM(tplt_s2,trdat2',ccplt(1,:));
    title(titstrs(kk)+": "+k+", "+scnumsDA{k,"sessionNum"}+" "+scnumsDA{k,"cellNum"}+...
        ", "+scnumsH2O{k,"sessionNum"}+" "+scnumsH2O{k,"cellNum"})
    axis tight;
    ylabel("Fluorescence in Water (zsc)")
    legend([h1 h2],["DA","Water"])
    figureformat_forsaving;
    export_nature_master(gcf,xlout,exportSrcData);
end
%% DA-H2O Correlated CFs
rng(0);
grpuse = chronRewBoth_CFs;
nBoth=length(chronRewBoth_CFs);
pctBoth = round(nBoth/nChronCF,2)*100;
pctH2O = round(length(chronRewH2O_CFs)/nChronCF,2)*100;
pctDA = round(length(chronRewDA_CFs)/nChronCF,2)*100;

figure;
grp1=setdiff(1:length(CF_chron_ref),chronRewBoth_CFs);
s1=scatter(CFsChronInfo{2}.postrew(CF_chron_ref(grp1)),CFsChronInfo{1}.postrew(CF_chron_sec(grp1)),MarkerEdgeColor="none",MarkerFaceColor=[0 0 1]);
hold on;
s2=scatter(CFsChronInfo{2}.postrew(CF_chron_ref(chronRewBoth_CFs)),CFsChronInfo{1}.postrew(CF_chron_sec(chronRewBoth_CFs)),MarkerEdgeColor=[1 .5 0],linew=1,MarkerFaceColor=[0 0 1]);
axis tight;
xl=xlim; yl=ylim;
plot(1.3*[1 1],[1.3 yl(2)],col=0.6*ones(1,3));
plot([1.3 xl(2)],1.3*[1 1],col=0.6*ones(1,3));
text(2.8,3,num2str(pctBoth)+"% of CFs",col=[1 .5 0])
xlabel("DA response (Hz)");
ylabel("Water response (Hz)")
title("Fig5p");
legend([s1,s2],["All","Doubly-responsive"])
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

ns=10000;
pctrand=zeros(ns,1);
for s = 1:ns
shuffChron = shufflev(CFsChronInfo{1}.postrew(CF_chron_sec));
shuffboth = find(CFsChronInfo{2}.postrew(CF_chron_ref)>1.3 & shuffChron>1.3);
pctrand(s)=numel(shuffboth)/numel(CF_chron_ref)*100;
end
figure; h=histogram(pctrand,norm="prob",DisplaySt="stairs"); 
pcttrue=numel(grpuse)/numel(CF_chron_ref)*100;
hold on; h2=plot(pcttrue*[1 1],ylim,'r');
title("EDFig8i: p="+nnz(pctrand>pcttrue)/ns);
xlabel("Water+DA-responsive CFs");
legend("Random")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

[~,cfchronsortix_DA]=sort(CFsChronInfo{2}.postrew(CF_chron_ref(grpuse)));
[~,cfchronsortix_H2O]=sort(CFsChronInfo{1}.postrew(CF_chron_sec(grpuse)));
[~,cfchronsortix_H2ODA]=sort(abs(CFsChronInfo{1}.postrew(CF_chron_sec(grpuse))-CFsChronInfo{2}.postrew(CF_chron_ref(grpuse))),'descend');
tmpnmice=(nvs.CF_DA);
srtuse=cfchronsortix_H2O;
toplt = {chronCFsH2O(grpuse(srtuse),:),chronCFsDA(grpuse(srtuse),:)};
figure; 
t = tiledlayout(1,2,tilesp="compact",pad="compact");
[tplt_cur,tplt_cur_s]=winfn(tplt_tmplt_s_CF,[-1.2 1.2]);
for pl = 1:2
nexttile;
imagesc(tplt_cur_s,[],toplt{pl}(:,tplt_cur),[0,1.8])
axis tight;
hold on; plot([0 0],ylim,'k',[-1 -1],ylim,'k');
xlabel("Time relative to movement (s)")
if pl==1, ylabel(length(grpuse)+" DA-H2O-correlated CFs, "+round(length(grpuse)/...
    nChronCF*100)+"% of total"); 
    title("DA reward");
else
yticklabels([]);
title("Water reward")
end
end
colorbarm("Spike rate (Hz)");
title(t,"Fig5q")
export_nature_master(gcf,xlout,exportSrcData);

figm([1     1   332   1000]);
t=tiledlayout(3,1,tilesp="tight",pad="tight");
toplts={chronRewH2O_CFs,chronRewDA_CFs,chronRewBoth_CFs};
pcts=[pctH2O,pctDA,pctBoth];
titstrs=["EDFig8j: Water-responsive (","EDFig8k: DA-responsive (","Fig5t: Both ("];
for k =1:3
    nexttile(k);
ccplt = [0.157 0.471 0.231; 0.659 0.086 0.541; 0.5 0 0.5; 0.318 0.698 0.961]; 
toplt = toplts{k};
h1=errorbar_shadeSEM(tplt_tmplt_s_CF,chronCFsH2O(toplt,:)',ccplt(1,:));
h2=errorbar_shadeSEM(tplt_tmplt_s_CF,chronCFsDA(toplt,:)',ccplt(2,:));
uistack([h1 h2],"top")
xlim([-1.2 1.2])
ylim tight;
title(titstrs(k)+pcts(k)+"%, "+tmpnmice+" mice)",fontweight="normal") 
if k==1,legend([h1,h2],["Water","DA"]); end
end
xlabel(t,"Time relative to movement (s)")
ylabel(t,"CF spike rate (zsc)")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
%% example Water-DA CFs
srtuse=cfchronsortix_H2ODA;
cfchronsortix_DA_truenumsref = CF_chron_ref(grpuse(flipud(srtuse)));
cfchronsortix_DA_truenumssec = CF_chron_sec(grpuse(flipud(srtuse)));
CFscnumsDA=CFsChronInfo{2}(cfchronsortix_DA_truenumsref,["sessionNum","cellNum"]);
CFscnumsH2O=CFsChronInfo{1}(cfchronsortix_DA_truenumssec,["sessionNum","cellNum"]);
cshow=[];
cshow=cat(1,cshow,find(CFscnumsDA.sessionNum==6 & CFscnumsDA.cellNum==16));
cshow=cat(1,cshow,find(CFscnumsDA.sessionNum==4 & CFscnumsDA.cellNum==34));
titstrs=["Fig5r","Fig5s"];
for kk = 1:length(cshow)
    f=figure;
    k=cshow(kk);
    curd = micedats{CFscnumsDA{k,"sessionNum"}};
    curc = CFscnumsDA{k,"cellNum"};
    truse = find(curd.goodMvmt & curd.rewarded);
    [tplt,tplt_s] = winfn(curd.tmpx_right,[-2 2]);
    trdat = squeeze(curd.rewAlgn.sprate_right_red(truse,curc,tplt));
    h1=errorbar_shadeSEM(tplt_s,trdat',ccplt(2,:));
    axis tight;
    curd = micedats{CFscnumsDA{k,"sessionNum"}}.waterdat;
    curc = CFscnumsH2O{k,"cellNum"};
    truse = find(curd.goodMvmt & curd.rewarded);
    [tplt,tplt_s] = winfn(curd.tmpx_right,[-2 2]);
    trdat = squeeze(curd.rewAlgn.sprate_right_red(truse,curc,tplt));
    
    h2=errorbar_shadeSEM(tplt_s,trdat',ccplt(1,:));
    hold on; plot([-1 -1],ylim,'k',[0 0],ylim,'k'); 
    title(titstrs(kk)+": "+k+", "+CFscnumsDA{k,"sessionNum"}+" "+CFscnumsDA{k,"cellNum"}+...
        ", "+CFscnumsH2O{k,"sessionNum"}+" "+CFscnumsH2O{k,"cellNum"})
    axis tight;
    xlim([-1.2 1.2])
    ylabel("Fluorescence (zsc)")
    xlabel("Time relative to reward (s)")
    legend([h1 h2],["DA","Water"])
    figureformat_forsaving;
    export_nature_master(f,xlout,exportSrcData);
end
%% 1s-2s DA cell identity alignment
rng(0);
refix = 4; secix = setdiff([2 4],refix);
grc_chron_ref = find(GrCsChronInfo{refix}.otherCellNum>0);
grc_chron_ref_rows = GrCsChronInfo{refix}{grc_chron_ref,["sessionNum","cellNum"]};
[~,othersessionnum] = ismember(dirTable.Alt_Delay_Dir(grc_chron_ref_rows(:,1)),dirTable.DA_Dir);
assert(all(othersessionnum~=0));
matchrow = [othersessionnum GrCsChronInfo{refix}{grc_chron_ref,"otherCellNum"}];
[~,grc_chron_sec] = ismember(matchrow, GrCsChronInfo{secix}{:,["sessionNum","cellNum"]},'rows');
assert(all(grc_chron_sec~=0));
chronGrCs2s=allGrCs_rew{refix}(grc_chron_ref,:);
chronGrCs1s=allGrCs_rew{secix}(grc_chron_sec,:);
chronCellNums = [grc_chron_sec grc_chron_ref];
nChronGrC = length(grc_chron_ref);
unique(dirTable.mname(GrCsChronInfo{refix}.sessionNum(grc_chron_ref)));

[winscale,winscale_s] = winfn(tplt_tmplt_s,[-1 4]);
grcwinsc2s = chronGrCs2s(:,winscale);
grcwinsc1s = chronGrCs1s(:,winscale);
windel = winfn(winscale_s,[0 2]);
windel1s = winfn(winscale_s,[0 1]);
grcdelds2s = grcwinsc2s(:,windel(1:2:end));
grcwinsc2s(:,windel1s)=grcdelds2s;
winpost2s = winfn(tplt_tmplt_s,[2 4]);
grcpost2s = chronGrCs2s(:,winpost2s);
winpost1s = winfn(tplt_tmplt_s,[1 3]);
grcwinsc2s(:,winpost1s)=grcpost2s;
ixuse2 = winfn(winscale_s,[-1 3]);

[corr_2s_1s,corrp] = corr(grcwinsc2s(:,ixuse2)',grcwinsc1s(:,ixuse2)');

corrp=diag(corrp);
corr_2s_1s = diag(corr_2s_1s);

% benjamini hochberg
% 1. Set your acceptable False Discovery Rate (e.g., 1% or 0.01)
q_threshold = 0.01; 
% 2. Sort p-values ascending and keep track of original indices
m = length(corrp);
[sorted_p, sort_idx] = sort(corrp);
% 3. Calculate the Benjamini-Hochberg critical values
critical_values = (1:m)' / m * q_threshold;
% 4. Find the largest p-value that is less than its critical value
max_id = find(sorted_p <= critical_values, 1, 'last');
fdr_p_cutoff = sorted_p(max_id);    
% Find the minimum r-value that corresponds to this p-value
r_passed = corr_2s_1s(corrp <= fdr_p_cutoff);
min_r_fdr = min(r_passed(r_passed > 0));
fprintf('FDR p-value cutoff: %.1e\n', fdr_p_cutoff);
fprintf('Effectively equivalent to r > %.2f\n', min_r_fdr);

issigs = corr_2s_1s>=0.4;
sigchron = find(issigs);
disp(round(100*numel(sigchron)/numel(issigs))+"% of GrCs 1s-2s generalize");

delaySpecific = find(~issigs);
reliab1=GrCsChronInfo{refix}.reliab(grc_chron_ref);
reliab2=GrCsChronInfo{secix}.reliab(grc_chron_sec);
only2s = find(reliab1(delaySpecific)>0.4 & reliab2(delaySpecific)<0.4);
only1s = find(reliab1(delaySpecific)<0.4 & reliab2(delaySpecific)>0.4);
crap = find(reliab1(delaySpecific)<0.4 & reliab2(delaySpecific)<0.4);
remapper= find(reliab1(delaySpecific)>0.4 & reliab2(delaySpecific)>0.4);
generalizerPct=round(length(sigchron)/length(issigs)*100);
only2sPct=round(length(only2s)/length(issigs)*100);
only1sPct=round(length(only1s)/length(issigs)*100);
crapPct=round(length(crap)/length(issigs)*100);
remapPct=round(length(remapper)/length(issigs)*100);
figure;
piechart([generalizerPct,only2sPct,only1sPct,crapPct,remapPct],...
    ["Generalizers","Only 2-s reliable","Only 1-s reliable","Unclassified","Reliable non-generalizers"]);
title("EDFig7i")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

[corr_2s_1s_rand,corrp_rand] = corr(grcwinsc2s(:,ixuse2)',grcwinsc1s(randperm(size(grcwinsc1s,1)),ixuse2)');

corrp_rand=diag(corrp_rand);
corr_2s_1s_rand = diag(corr_2s_1s_rand);

issigs_rand = corrp_rand<=0.05 & corr_2s_1s_rand>=0.4;
sigchron_rand = find(issigs_rand);
disp("vs "+round(numel(sigchron_rand)/numel(issigs_rand)*100)+"% by chance");

% 1s-2s alignment
figure(pos=[1730         309        800         652])
t = tiledlayout(2,2,pad="compact",tilesp="tight");
sigs = {chronGrCs1s,chronGrCs2s};
infs = GrCsChronInfo([2 4]);
rtypsuse = rtyps([2 4]);
for t1=  1:2
    for t2 = 1:2
        if t2==1, endAdd2=1; else, endAdd2=2; end
        nexttile;
        cursig = sigs{t2};
        [~,cursort] = ismember(infs{t1}.prerewSortIx,chronCellNums(:,t1));
        cursort = cursort(cursort~=0);
        clims = {[-0.3 0.3],[-0.3 0.3]};
        imagesc(tplt_tmplt_s,[],cursig(cursort,:),clims{t2});
        if t1==2, xlabel("Time relative to "+rtypsuse(t2)+" (s)"); end
        if t2==1, 
            ylabel(cnames(1)+" sorted by "+rtypsuse(t1));
        else
            yticklabels([]);
        end
        xlim([-1 3])
        hold on; plot([0 0]+endAdd2,ylim,'k',[-1 -1]+endAdd,ylim,'k');
    end
end
colorbarm("Fluorescence (zsc)");
title(t,"Fig4b-e");
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

figure(pos=[ 1182         113         560         238]); 
xbin=-1:0.1:1;
h=histogram(corr_2s_1s(~issigs),xbin);
hold on; 
h2=histogram(corr_2s_1s(issigs),xbin); 
xlabel("1-s / 2-s Temporal scaling (r)"); ylabel("Number of GrCs")
hold on; xlim([-1 1]); 
legend([h,h2],["All tracked GrCs","Temporally scaled GrCs ("+round(100*mean(issigs))+"%)"],location="NorthEast",AutoUpdate=0)
ylim(ylim.*[1 1.1]);
plot([0 0],ylim,'k',LineWidth=2)
figureformat_forsaving;
title("Fig4f: "+size(cursig,1)+"cells",fontsize=9,fontweight="normal")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% Generalizer histogram
figure(pos=[ 1182         113         560         238]); h=histogram(corr_2s_1s,xbin,DisplayStyle="stairs",EdgeColor=[1 0 0]);
hold on; h3=histogram(corr_2s_1s_rand,h.BinEdges,DisplayStyle="stairs",EdgeColor=[0 0 0]); 
xlabel("1-s / 2-s Temporal scaling (r)"); ylabel("Number of GrCs")
hold on; xlim([-1 1]); 
ylim(ylim.*[1 1.1]);
plot([0 0],ylim,'k',LineWidth=2)
title("EDFig7b: p="+num2str(ranksum_disp(corr_2s_1s,corr_2s_1s_rand),2))
legend([h h3],["True","Random"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% Generalizer rasters
[~,grcchronsortix_2s]=sort(GrCsChronInfo{4}.del_act(grc_chron_ref(issigs)));
toplt = {chronGrCs1s(sigchron(grcchronsortix_2s),:),chronGrCs2s(sigchron(grcchronsortix_2s),:)};
figure(pos=[2478         569         560         261]); 
t=tiledlayout(1,2,tilesp="tight");
for pl = 1:2
if pl==2, endAdd2=2; else, endAdd2=endAdd; end
nexttile(pl); imagesc(tplt_tmplt_s,[],toplt{pl},[-0.4,0.3])
axis tight;
if pl==2, yticks([]); end
hold on; plot([0 0]+endAdd2,ylim,'k',[-1 -1]+endAdd,ylim,'k');
if pl==1, title("1-s DA delay"); else, title("2-s DA delay"); end
end
colorbarm("Fluorescence (zsc)");
ylabel(t,["2-s/1-s temporally scaled GrCs",length(sigchron)+" cells, "+round(length(sigchron)/...
    nChronGrC*100)+"% of total"],interp="none"); 
xlabel(t,"Time relative to movement (s)")
title(t,"Fig4g")
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);

% Matched cell counts bar
n1s=arrayfun(@(x)micedats{x}.nc_right_green,mgrps.grcs_1s_has2smatch);
n2s=arrayfun(@(x)micedats{x}.nc_right_green,mgrps.grcs_2s_has1smatch);
nMatched = arrayfun(@(x)sum(all(micedats{x}.chronicGreen.finalMatchesMat~=0,2)),mgrps.grcs_2s_has1smatch);
barwitherr_stde({n1s,n2s,nMatched},dots=true,title="EDFig7a")
ylabel("GrCs per session")
xticklabels(["1s","2s","Matched"])
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
%% example 1-s-2-s generalizer cells
grcchronsortix_2s_truenumsref = grc_chron_ref(sigchron(flipud(grcchronsortix_2s)));
grcchronsortix_1s_truenumssec = grc_chron_sec(sigchron(flipud(grcchronsortix_2s)));
scnums2s=GrCsChronInfo{4}(grcchronsortix_2s_truenumsref,["sessionNum","cellNum"]);
scnums1s=GrCsChronInfo{2}(grcchronsortix_1s_truenumssec,["sessionNum","cellNum"]);
nc = size(scnums1s,1);
cshow=[];
cshow=cat(1,cshow,find(scnums2s.sessionNum==46 & scnums2s.cellNum==64));
cshow=cat(1,cshow,find(scnums2s.sessionNum==40 & scnums2s.cellNum==30));
cshow=cat(1,cshow,find(scnums2s.sessionNum==46 & scnums2s.cellNum==89));
cshow=cat(1,cshow,find(scnums2s.sessionNum==40 & scnums2s.cellNum==9));
titstrs=["Fig4h","Fig4i","EDFig7c","EDFig7d"];
for kk = 1:length(cshow)
    figure;
    k=cshow(kk);
    ax=axes;
    curd = micedats{scnums2s{k,"sessionNum"}};
    curc = scnums2s{k,"cellNum"};
    truse = find(curd.goodMvmt & curd.rewarded);
    [tplt,tplt_s] = winfn(curd.tmpx_right,[-1 3]);
    trdat = squeeze(curd.endAlgn.sigFilt_right_green(truse,curc,tplt));
    yyaxis right;
    h1=errorbar_shadeSEM(tplt_s,trdat',ccplt(4,:));
    axis tight;
    ylabel("Fluorescence in 2-s (zsc)")
    curd = micedats{scnums1s{k,"sessionNum"}};
    curc = scnums1s{k,"cellNum"};
    truse = find(curd.goodMvmt & curd.rewarded);
    [tplt,tplt_s] = winfn(curd.tmpx_right,[-1 3]);
    trdat = squeeze(curd.endAlgn.sigFilt_right_green(truse,curc,tplt));
    yyaxis left;
    h2=errorbar_shadeSEM(tplt_s,trdat',ccplt(2,:));
    hold on; plot([0 0],ylim,'k-',[1 1],ylim,'k-',[2 2],ylim,'k-'); 
    title(titstrs(kk)+": "+k+", "+scnums2s{k,"sessionNum"}+" "+scnums2s{k,"cellNum"}+...
        ", "+scnums1s{k,"sessionNum"}+" "+scnums1s{k,"cellNum"})
    axis tight;
    ylabel("Fluorescence in 1-s (zsc)")
    ax.YAxis(1).Color = [0 0 0];
    ax.YAxis(2).Color = [0 0 0];
    legend([h1 h2],["2-s","1-s"]);
    figureformat_forsaving
    export_nature_master(gcf,xlout,exportSrcData);
end
%% behavior quantifications
rng(0);
opto1s = find(dirTable.Delay==1 & dirTable.DAType=="DAT");
MFB1s = find(dirTable.Delay==1 & dirTable.DAType=="MFB");
water1s = find(dirTable.Delay==1 & ~ismissing(dirTable.WaterDir));
dagrps = {opto1s,MFB1s,water1s};
[attmptRates,mnames,mvlens,mvdurs,compltd,succRates] = deal({});
for k = 1:3
    curn = length(dagrps{k});
    for j = 1:curn
        curix = dagrps{k}(j);
        if k<3, curd = micedats{curix}; else, curd=micedats{curix}.waterdat; end   
        attmptRates{k}(j) = curd.attmptRate;
        if attmptRates{k}(j)<4, disp(dirTable(curix,:)); end
        
        mnames{k}(j) = dirTable.mname(curix);
        mvlens{k}(j) = median(curd.mvlen);
        succtrs = find(curd.goodMvmt & curd.mvlen>6 & curd.rewarded);
        mvdurs{k}(j) = median(curd.trueend(succtrs)-curd.truestart(succtrs))*curd.dtb*1000;
        compltd{k}(j) = curd.compltd;
        succRates{k}(j)=curd.succRate;
    end
end
ccplt=[1 0 0; 0 0 1; 0.2 0.2 0.2];
barwitherr_stde(attmptRates,dots=true,ranksumgrps={[1,2],[2,3],[1,3]},col=ccplt,titl="Fig1h")
xticklabels(rleg);
ylabel("Reach attempts per minute")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
barwitherr_stde(succRates,dots=true,ranksumgrps={[1,2],[2,3],[1,3]},col=ccplt,titl="Fig1i")
xticklabels(rleg);
ylabel("Successes per minute")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
barwitherr_stde(mvlens,dots=true,ranksumgrps={[1,2],[2,3],[1,3]},col=ccplt,titl="Fig1k")
ylabel("Reach length (mm)")
xticklabels(rleg);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
barwitherr_stde(mvdurs,dots=true,ranksumgrps={[1,2],[2,3],[1,3]},col=ccplt,titl="EDFig1a")
ylabel("Reach duration (ms)")
xticklabels(rleg);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
barwitherr_stde(compltd,dots=true,ranksumgrps={[1,2],[2,3],[1,3]},col=ccplt,titl="Fig1j")
xticklabels(rleg);
ylabel("Completed reaches (% of total)")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% imaging stats
rng(0);
nGrC_MFB = arrayfun(@(x)micedats{x}.nc_right_green,mgrps.GrCs_MFB);
nGrC_H2O = arrayfun(@(x)micedats{x}.waterdat.nc_right_green,mgrps.DA1s_grcs_haswater);
nGrC_VTA = arrayfun(@(x)micedats{x}.nc_right_green,mgrps.GrCs_VTA);
nGrC_all = cat(1,nGrC_MFB,nGrC_H2O,nGrC_VTA);
barwitherr_stde({nGrC_all,nGrC_MFB,nGrC_VTA,nGrC_H2O},dots=true,titl="EDFig1l");
ylabel("Detected GrCs");
xticklabels(["All","MFB","VTA","H2O"]);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

nCF_GC8_DA = arrayfun(@(x)micedats{x}.nc_right_red,mgrps.CF_gcamp);
nCF_GC8_H2O = arrayfun(@(x)micedats{x}.waterdat.nc_right_red,intersect(mgrps.CF_gcamp,mgrps.CFs_haswater));
nCF_GC8 = cat(1,nCF_GC8_DA,nCF_GC8_H2O);
nCF_RC2_DA = arrayfun(@(x)micedats{x}.nc_right_red,mgrps.CF_rcamp);
nCF_RC2_H2O = arrayfun(@(x)micedats{x}.waterdat.nc_right_red,intersect(mgrps.CF_rcamp,mgrps.CFs_haswater));
nCF_RC2 = cat(1,nCF_RC2_DA,nCF_RC2_H2O);
barwitherr_stde({nCF_RC2,nCF_GC8},dots=true,titl="EDFig1m");
xticklabels(["40x (RCaMP2)","16x (GCaMP8m)"]);
ylabel("Detected CFs");
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

sprateCF_GC8_DA = arrayfun(@(x)mean(micedats{x}.sprate_right_red),mgrps.CF_gcamp);
sprateCF_GC8_H2O = arrayfun(@(x)mean(micedats{x}.waterdat.sprate_right_red),...
    intersect(mgrps.CF_gcamp,mgrps.CFs_haswater));
sprateCF_GC8 = cat(1,sprateCF_GC8_DA,sprateCF_GC8_H2O);
sprateCF_RC2_DA = arrayfun(@(x)mean(micedats{x}.sprate_right_red),mgrps.CF_rcamp);
sprateCF_RC2_H2O = arrayfun(@(x)mean(micedats{x}.waterdat.sprate_right_red),...
    intersect(mgrps.CF_rcamp,mgrps.CFs_haswater));
sprateCF_RC2 = cat(1,sprateCF_RC2_DA,sprateCF_RC2_H2O);
barwitherr_stde({sprateCF_RC2,sprateCF_GC8},dots=true,titl="EDFig1n");
xticklabels(["40x (RCaMP2)","16x (GCaMP8m)"]);
ylabel("CF spike rate (Hz)")
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% Single-trial autocorrelation
rng(0);
tau1=GrCsChronInfo{2}.stTau;
tau2=GrCsChronInfo{4}.stTau;
physThresh=0.1;
violincell({tau1(tau1>physThresh),tau2(tau2>physThresh)},bandw=0.04)
ylabel("Single-trial tau, omitted reward (s)");
xticklabels(["1-s delay","2-s delay"]);
titstr=string(gca().Title.String);
title(["EDFig2b";titstr]);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% Kinematic v Reward-anticipation Regression
rng(0);
ruse=[2 4];
allkinR2 = cell(1,length(ruse));
allCogR2 = cell(1,length(ruse));
allRamps = cell(1,length(ruse));
excells = [49 1; 50 20; 53 5; 24 39; 39 10];
excellnms=["EDFig4g1","EDFig4g2","EDFig4g3","EDFig4h","EDFig4i"];
for rr = 1:length(ruse)
    r=ruse(rr);
    cuse = sort(ant_sig{r});
    
    suse = unique(GrCsChronInfo{r}.sessionNum(cuse));
    nduse = length(suse);
    
    for dd = 1:nduse
        d = suse(dd);
        curcuse = GrCsChronInfo{r}.cellNum(cuse(GrCsChronInfo{r}.sessionNum(cuse)==d));
        curcuse_tot=cuse(GrCsChronInfo{r}.sessionNum(cuse)==d);
        
        if r>1
            curd = micedats{d}; 
        else
            curd = micedats{d}.waterdat; 
        end
        
        if isfield(curd.endAlgn, "dlc")
            allspd = [];
            for k = 1:length(dlcnames)
                if isfield(curd.endAlgn, dlcnames(k)) && ~all(isnan(curd.endAlgn.(dlcnames(k))(:)))
                    allspd = cat(3, allspd, curd.endAlgn.(dlcnames(k)));
                end
            end
            
            if ~isempty(allspd)
                gooddlc = ~any(any(isnan(allspd), 2), 3);
                
                if nnz(gooddlc)>10
                    % 1. DEFINE NEURAL INDICES (Keep ALL good behavioral trials)
                    rewuse_neural  = find(curd.goodMvmt & curd.rewarded & curd.mvlen>=6);
                    omituse_neural = find(curd.goodMvmt & ~curd.rewarded & curd.mvlen>=6);
                    
                    % 2. DEFINE KINEMATIC INDICES (Only keep trials where DLC tracking survived)
                    rewuse_dlc  = find(curd.goodMvmt & curd.rewarded & curd.mvlen>=6 & gooddlc);
                    omituse_dlc = find(curd.goodMvmt & ~curd.rewarded & curd.mvlen>=6 & gooddlc);
                    if ~isempty(omituse_dlc)
                    if r==4
                    twinlims = [0 4]; rewtime=2;
                    else
                        twinlims = [0 3]; rewtime=1;
                    end
                    [t_GrC, t_GrC_s] = winfn(curd.tmpx_right, twinlims);
                    [tplt_dlc, tplt_dlc_s] = winfn(curd.tmpxDLC, twinlims);
                    
                    % 3. COMPUTE NEURAL AVERAGES (Using max trials to protect SNR)
                    GrC_rew = permute(mean(curd.endAlgn.sigFilt_right_green(rewuse_neural, curcuse, t_GrC), 1), [2 3 1]);
                    GrC_omit = permute(mean(curd.endAlgn.sigFilt_right_green(omituse_neural, curcuse, t_GrC), 1), [2 3 1]);
                    % Define a smoothing window (e.g., 5 frames. Adjust based on your frame rate so it's ~150ms)
                    smooth_win = 5; 
                    
                    % Smooth the neural data along the time dimension (Dim 2)
                    GrC_rew = smoothdata(GrC_rew, 2, 'gaussian', smooth_win);
                    GrC_omit = smoothdata(GrC_omit, 2, 'gaussian', smooth_win);
                    
                    % 4. COMPUTE KINEMATIC AVERAGES (Using the strict DLC subset)
                    body_rew = squeeze(mean(allspd(rewuse_dlc, tplt_dlc, :), 1))';
                    body_omit = squeeze(mean(allspd(omituse_dlc, tplt_dlc, :), 1))';
                    
                    % 5. RUN VARIANCE PARTITIONING
                    cpltuse=find(excells(:,1)==suse(dd));
                    cplt=excells(cpltuse,2);
                    cpltnms=excellnms(cpltuse);
                    results = compute_concatenated_VP(GrC_rew, GrC_omit, t_GrC_s, rewtime, body_rew, body_omit, tplt_dlc_s,cplt,suse(dd),cpltnms);
                    
                    allkinR2{rr} = cat(1, allkinR2{rr}, results.deltaR2_Kin');
                    allCogR2{rr} = cat(1, allCogR2{rr}, results.deltaR2_Cog');
                    allRamps{rr} = cat(1, allRamps{rr}, ...
                        GrCsChronInfo{r}.postomit(curcuse_tot)-GrCsChronInfo{r}.postrew(curcuse_tot));
                    end
                end
            end
        end
        fprintf('%d,', dd);
    end
end
fprintf('\n');

figure('Name', 'Panel A: Raw Scatter', 'Position', [100, 100, 500, 500]);
rampplt=cat(1,allRamps{:});
kinplt=cat(1,allkinR2{:});
cogplt=cat(1,allCogR2{:});
scatter(rampplt, kinplt, 30, ...
    'MarkerFaceColor', [0.2 0.2 0.2], ... 
    'MarkerEdgeColor', 'none', ...
    'MarkerFaceAlpha', 0.4); 

xlabel('Post-omit minus post-reward (zsc)', 'FontSize', 14);
ylabel('Unique Kinematic Variance (\DeltaR^2)', 'FontSize', 14);
[r,p]=corr(rampplt, kinplt,typ="spearman");
title("EDFig4j: \rho="+round(r,2)+", p="+round(p,2)+", n="+length(rampplt),interp="tex");
xlim([min(rampplt)-0.1, max(rampplt)+0.1]);
ylim([min(kinplt)-0.02, max(kinplt)+0.02]);
grid on;
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);

splt=median(rampplt);
violincell({kinplt(rampplt<splt),cogplt(rampplt<splt),kinplt(rampplt>=splt),cogplt(rampplt>=splt)},bandw=0.01,ranksumgrps={[1 2],[3 4]})
xticklabels(["Body (weak ramping)","Reward (weak ramping)","Body (strong ramping)","Reward (strong ramping)"]);
ylabel("Unique variance explained")
titstr=string(gca().Title.String);
title(["EDFig4k";titstr]);
figureformat_forsaving
export_nature_master(gcf,xlout,exportSrcData);
%% Reward-activated GrCs
subsplt=is_rewGrCs{2};
srtuse=GrCsChronInfo{2}.postrew;
labls="Reward-activated";
figure;
curactrew=allGrCs_rew{2}(subsplt,:);
curactomit=allGrCs_omit{2}(subsplt,:);
[~,srtix]=sort(srtuse(subsplt));
imagesc(tplt_tmplt_s,[],curactrew(srtix,:),[-0.5 0.5]);
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]);
colorbarm("Fluorescence (zsc)");
xlabel("Time relative to movement (s)");
ylabel(labls+", "+length(subsplt)+" GrCs ("+round(length(subsplt)/size(allGrCs_rew{2},1)*100,2)+"%)");
title("EDFig2f");
figureformat_forsaving(true); 
export_nature_master(gcf,xlout,exportSrcData);
figure;
h1=errorbar_shadeSEM(tplt_tmplt_s,curactrew(srtix,:)',[0 0 1]);
h2=errorbar_shadeSEM(tplt_tmplt_s,curactomit(srtix,:)',[1 0 0]);
uistack([h1 h2],"top");
ylim tight;
hold on; plot([0 0],ylim,'k',[1 1],ylim,'k'); xlim([-1 3]);
xlabel("Time relative to movement (s)");
ylabel("Fluorescence (zsc)");
legend([h1 h2],["Rewarded","Omitted"]);
title("EDFig2g: "+labls+", "+length(subsplt)+" GrCs ("+round(length(subsplt)/size(allGrCs_rew{2},1)*100,2)+"%)");
figureformat_forsaving;
export_nature_master(gcf,xlout,exportSrcData);
