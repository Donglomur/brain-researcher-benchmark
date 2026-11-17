function [trl, event] = my_trialfun_olsa(cfg)
%--------------------------------------------------------------------------
% Till Habersetzer, 05.07.2025
% Communication Acoustics, CvO University Oldenburg
% till.habersetzer@uol.de 
%
% Description:
%   Custom FieldTrip trial function ('trialfun') for defining epochs from
%   an OLSA (Oldenburg Sentence Test) experiment.
%
%   Key Steps:
%   -   Reads all events from the dataset specified in cfg.dataset.
%   -   Parses the event type string (e.g., 'olsa: list: X / sentence: Y')
%       to extract the specific list and sentence number for each trial.
%   -   Constructs a detailed 'trl' matrix that includes not only the standard
%       [begin, end, offset] timing but also columns for the trigger value,
%       list number, and sentence number.
%
% Inputs:
%   cfg (struct):   The FieldTrip configuration structure, which must contain
%                   cfg.dataset and cfg.trialdef with pre/post-stim times.
%
% Outputs:
%   trl (matrix):   The Nx6 trial definition matrix with columns:
%                   [begin_sample, end_sample, offset, trigger_value, list_num, sentence_num].
%   event (struct): The original event structure read from the data file.
%--------------------------------------------------------------------------

% Read events
%--------------------------------------------------------------------------
event = ft_read_event(cfg.dataset, 'readbids', 'yes');  
   
val  = [event.value]';
smp  = [event.sample]';
dur  = [event.duration]'; % durations in ms
type = {event.type}';

% Check number of events
%--------------------------------------------------------------------------
n_events = length(val);
if n_events~=120
    error('Unexpected number of events (%i)!',n_events)
end

% Extract list and sentence number
%--------------------------------------------------------------------------
list_num     = zeros(n_events,1);
sentence_num = zeros(n_events,1);

% format specifier
formatSpec = 'olsa: list: %d / sentence: %d';

% Loop through each cell and extract the numbers
for idx = 1:n_events
    values           = sscanf(type{idx}, formatSpec);
    list_num(idx)    = values(1);
    sentence_num(idx) = values(2);
end

% Compute trl-matrix
%--------------------------------------------------------------------------
hdr         = ft_read_header(cfg.dataset);
prestim     = round(hdr.Fs*cfg.trialdef.prestim); % in samples
poststim    = round(hdr.Fs*cfg.trialdef.poststim); % in samples
dur_samples = round(hdr.Fs*dur/1000); % in samples
trl         = [smp - prestim, smp + dur_samples + poststim, - prestim*zeros(n_events,1),val,list_num,sentence_num]; 

end