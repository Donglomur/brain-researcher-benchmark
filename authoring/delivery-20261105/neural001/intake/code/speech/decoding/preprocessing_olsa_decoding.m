function preprocessing_olsa_decoding(subject,settings)
%--------------------------------------------------------------------------
% Till Habersetzer, 06.07.2025
% Communication Acoustics, CvO University Oldenburg
% till.habersetzer@uol.de 
%
% Description:
%   Performs subject-level preprocessing of OLSA task data for a neural
%   decoding analysis, creating synchronized MEG and audio envelope epochs.
%
%   Key Steps:
%   -   Filters, epochs, and downsamples the continuous MEG data.
%   -   Enriches trial information by loading metadata (e.g., SNR,
%       intelligibility) from the BIDS events.tsv file.
%   -   Constructs the corresponding audio trial sequence by selecting
%       pre-processed envelopes based on the subject's stimulus playlist.
%   -   Performs a final sample-by-sample length matching of neuro-audio
%       pairs and saves the final data to a single .mat file.
%
% Inputs:
%   subject (char/string): The subject identifier (e.g., 'sub-01').
%   settings (struct):     Settings structure with all necessary paths and 
%                          parameters.
%--------------------------------------------------------------------------

%% Script settings 
%--------------------------------------------------------------------------

% Filter settings
filtertype = settings.decoding.filtertype; % windowed sinc type I linear phase FIR filter
bpfreq     = settings.decoding.bpfreq; % meg + audio

% Epoch length for olsa trials
prestim  = settings.decoding.olsa.prestim;
poststim = settings.decoding.olsa.poststim;

% Downsampling frequency
fs_down = settings.decoding.fs_down;

% MEG sampling frequency
fs_neuro = settings.decoding.fs_neuro;

% check whether maxfiltered data should be analyzed
use_maxfilter = settings.use_maxfilter;

% Latency Correction
apply_latency_correction = settings.apply_latency_correction;
audio_latency            = settings.audio_latency;

% Taskname
task = 'olsa';

%% Preprocessing 
%--------------------------------------------------------------------------

% Define datapath
%----------------
if use_maxfilter
    rawdata_path = fullfile(settings.path2derivatives,subject,'maxfilter');
    % Use movement-corrected data first
    filename     = sprintf('%s_task-%s_proc-tsss-mc_meg.fif',subject,task); 
    data_path    = fullfile(rawdata_path,filename);

    % use bids data for events
    event_path = fullfile(settings.path2bids,subject,'meg',sprintf('%s_task-%s_meg.fif',subject,task));
else
    rawdata_path = fullfile(settings.path2bids,subject,'meg');
    filename     = sprintf('%s_task-%s_meg.fif',subject,task);
    data_path    = fullfile(rawdata_path,filename);
    % badchannels  = settings.badchannels; 
    event_path   = data_path;
end

% Process data if it exists
if isfile(data_path)

    %% Define trials
    %---------------
    % Requires BIDS annotated events (especially the duration column)
    cfg                     = [];
    cfg.trialfun            = 'my_trialfun_olsa'; 
    cfg.dataset             = event_path; % path should always point to original bids-path
    cfg.trialdef.prestim    = prestim;
    cfg.trialdef.poststim   = poststim;
    cfg                     = ft_definetrial(cfg);

    trl = cfg.trl;
 
    % Add event_description
    %----------------------
    event_description              = struct();
    % Extraxt list and sentence numbers
    event_description.list_num     = trl(:,5);
    event_description.sentence_num = trl(:,6);
    % Load events.tsv file to get additional event information
    event                          = readtable(strrep(event_path,'meg.fif','events.tsv'),'FileType', 'text', 'Delimiter', '\t');
    event_description.snrs         = event.SNR;
    event_description.intells      = event.intelligibility;
    event_description.playlist     = event.stim_file;
    clear event

    %% Add latency correction 
    %------------------------
    if apply_latency_correction
        trl(:,1:2) = trl(:,1:2) + round(audio_latency*1000); % in samples
    end

    %% Filter continuous data to avoid edge artifacts
    %------------------------------------------------
    cfg              = [];
    cfg.channel      = 'meg'; 
    cfg.dataset      = data_path;
    cfg.bpfilter     = 'yes';
    cfg.bpfilttype   = filtertype;
    cfg.bpfreq       = bpfreq;
    cfg.plotfiltresp = 'no';
    data             = ft_preprocessing(cfg); 

    if ~isequal(data.fsample,fs_neuro)
        error('Unexpected sampling frequency for meg recordings (%i)!',data.fsample)
    end

    % plot spectrum
    %--------------
    % cfg         = [];
    % cfg.output  = 'pow';
    % cfg.channel = 'meg';
    % cfg.method  = 'mtmfft';
    % cfg.taper   = 'hanning';
    % cfg.foi     = 0:100;    
    % spectr      = ft_freqanalysis(cfg,data);   
    % 
    % figure
    % plot(spectr.freq,db(spectr.powspctrm(:,:)))
    % xlabel('f / Hz')    
    % xlim([0,80])

    %% Epoch data
    %------------
    cfg     = [];
    cfg.trl = trl;  
    epoch   = ft_redefinetrial(cfg,data);
    clear data

    %% Downsampling
    %--------------
    cfg            = [];
    cfg.resamplefs = fs_down;
    cfg.detrend    = 'no';
    epochs_neuro   = ft_resampledata(cfg,epoch);
    clear epoch

    %% Import audio data
    %-------------------
    fname           = 'preprocessed_olsa_envelopes_decoding.mat';
    audio_envelopes = importdata(fullfile(settings.path2derivatives,'stimuli',fname));

    % Loop over playlist and generate epochs_audio
    %---------------------------------------------
    epochs_audio = cell(1,120);

    for trl_idx = 1:120
        fname_audio           = event_description.playlist{trl_idx};
        [~, base_name, ~]     = fileparts(fname_audio);  
        epochs_audio{trl_idx} = audio_envelopes.(sprintf('envelope_%s',base_name));
    end

    %% Match durations of neuro and audio epochs
    %-------------------------------------------
    n_neuro = length(epochs_neuro.trial);
    n_audio = length(epochs_audio);
    
    if ~isequal(n_neuro,n_audio)
        error('Unexpected number of audio trials (%i) and neuro trials (%s)!',n_audio,n_neuro)
    end
    
    check_length = zeros(n_audio,2);
    for trl_idx = 1:n_neuro
        check_length(trl_idx,1) = size(epochs_neuro.trial{trl_idx},2);
        check_length(trl_idx,2) = length(epochs_audio{trl_idx});
    end
    
    % Sanity Check: Distance is bigger than 1 sample
    if any(abs(check_length(:,1)-check_length(:,2))>1)
        error("Trial durations don't match")
    end
    
    % Get index of minimum length for each trial
    [min_durs,~] = min(check_length,[],2);
    
    % Match length of trials
    for trl_idx = 1:n_neuro
        min_dur                     = min_durs(trl_idx);
        epochs_neuro.trial{trl_idx} = epochs_neuro.trial{trl_idx}(:,1:min_dur);
        epochs_neuro.time{trl_idx}  = epochs_neuro.time{trl_idx}(1:min_dur);
        epochs_audio{trl_idx}       = epochs_audio{trl_idx}(1:min_dur);
    end

    %% Save results
    %--------------
    dir2save = fullfile(settings.path2derivatives,subject,'speech');
    if ~exist(dir2save,'dir')
        mkdir(dir2save)
    end
    fname = sprintf('%s_preprocessed_olsa_decoding.mat',subject);
    
    results                   = struct;
    results.settings          = settings;
    results.epochs_neuro      = epochs_neuro;
    results.epochs_audio      = epochs_audio;
    results.event_description = event_description;
    
    save(fullfile(dir2save,fname),'results','-v7.3'); 
    fprintf("\n%s from %s saved.\n",fname,subject)

else
    error('Olsa file is missing (%s)!',subject)

end % file exists

end % end of function