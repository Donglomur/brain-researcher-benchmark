%--------------------------------------------------------------------------
% Till Habersetzer, 08.07.2025
% Communication Acoustics, CvO University Oldenburg
% till.habersetzer@uol.de 
%--------------------------------------------------------------------------

% ensure that we don't mix up settings
clear settings

% Define paths
%-------------
settings.rootpath       = fullfile('/mnt','localSSDPOOL','username'); % server
% settings.rootpath       = fullfile('M:'); % local computer
settings.path2project   = fullfile(settings.rootpath,'meg_scans');
settings.path2toolboxes = fullfile(settings.rootpath,'toolboxes');

% Defined based on upper paths
settings.path2bids        = fullfile(settings.path2project,'bidsdata');
settings.path2derivatives = fullfile(settings.path2bids,'derivatives');
settings.path2fieldtrip   = fullfile(settings.path2toolboxes,'fieldtrip-20250523');
settings.path2amtoolbox   = fullfile(settings.path2toolboxes,'amtoolbox-1.6.0');
settings.path2mtrftoolbox = fullfile(settings.path2toolboxes,'mTRF-Toolbox-2.7','mtrf');

% Other settings
%---------------
settings.use_maxfilter            = true;
settings.apply_latency_correction = true;
settings.audio_latency            = 3/1000; % 3 ms (see measurements 28.06.24)

% Speech
%-------
% Cross-correlation
settings.fs_audio                  = 44100;
settings.crosscorr.trialdur        = 10; % 10s
settings.crosscorr.filtertype      = 'but';
settings.crosscorr.meg.bpfreq      = [0.5,45];
settings.crosscorr.meg.bpfiltord   = 4; % default FieldTrip (6 reported in Pertersen paper leads to unstable filter)
settings.crosscorr.audio.lpfreq    = 25;
settings.crosscorr.audio.lpfiltord = 3;
settings.crosscorr.fs_down         = 250;
settings.crosscorr.zscore          = false;
settings.crosscorr.timelags        = [-100,900]; % in ms
% Decoder
settings.decoding.trialdur         = 120;
settings.decoding.filtertype       = 'firws';
settings.decoding.bpfreq           = [0.5,4];
settings.decoding.fs_neuro         = 1000;
settings.decoding.fs_down          = 64;
settings.decoding.zscore           = true;
settings.decoding.olsa.prestim     = 0;
settings.decoding.olsa.poststim    = 0.5;
settings.decoding.olsa.padding     = 10; %s zeropad olsa wav files before filtering (in sec)

% mTRF-model hyperparameters
settings.decoding.decoder.n_portion_training = 0.8; % percentage of trials used for training
settings.decoding.decoder.drct               = -1; % direction: backward model
settings.decoding.decoder.tmin               = 0; % minimum time lag (ms)
settings.decoding.decoder.tmax               = 250; % maximum time lag (ms)
settings.decoding.decoder.lambda_exp         = -6:2:6; % exponent regularization values
settings.decoding.decoder.zeropad            = 1; % zero-pad the outer rows of the design matrix or delete them
settings.decoding.decoder.corr_metric        = 'Spearman'; % 'Pearson' specifiy accuracy metric
settings.decoding.decoder.fast               = 1; % use the fast cross-validation method (requires more memory)
settings.decoding.decoder.dim                = 2; % work along the rows, observations in columns
settings.decoding.decoder.type               = 'multi'; % use all lags simultaneously to fit a multi-lag model