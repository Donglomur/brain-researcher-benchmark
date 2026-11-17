%% Place to save reduced data structures
YOURDATAPATH = '';
savePath = [YOURDATAPATH '/' 'locked' '/'];

%% Individual datasets
mouseInfoAll = {{'cfa17', '200825'}, ...
    {'cfa17', '200827'}, ...
    {'cfa19', '200820'}, ...
    {'cfa19', '200826'}, ...
    {'cfa20', '201114'}, ...
    {'cfa20', '201118'}, ...
    {'cfa22', '220605'}, ...
    {'cfa22', '220611'}, ...
    {'cfa24', '220727'}, ...
    {'cfa24', '220724'}};

%% Loop over all datasets
% Perform each specific locking and gather locked structs for saving

%% Joint angle kinematics decoding
% Saves the output to a reduced data format with 3 structs
% kinematics: all kinematic data, from eventLockKinematics
% neurons: all neural data, from eventLockData and eventLockRADICaL
% M: metadata as in full R, with config struct of locking params
% KEEPS ALL NEURONS, NEED TO SCREEN BY MODULATION LATER

% Params
% We will decode with only -100:10:400 in most cases, but include -200:800
% for the lagged Wiener filter decoding
config.preT = -200;
config.postT = 800;
config.tBase = 10;
config.smoothSD = 35;
config.tPtsRADICaL = -200:10:800; % the time window RADICaL was fit on, used to find appropriate time indices
config.eventName = 'liftTimeDLC';
config.dataPath = YOURDATAPATH;

for dataset = mouseInfoAll
    mouse = dataset{1}{1};
    session = dataset{1}{2};
    
    % Load and lock
    [kinematics, neurons, M, Rconfig] = loadLock4Decode(mouse, session, config);
    M.config = Rconfig;
    save(sprintf('%s%s_%s_liftLocked', savePath, mouse, session), 'kinematics', 'neurons', 'M') 
end

%% Target decoding, original and kinematics-partial
% Saves the output to a reduced data format with 3 structs
% kinematics: all kinematic data, from eventLockKinematics
% neurons: all neural data, from eventLockData
% M: metadata as in full R, with config struct of locking params
% INCLUDES ONLY TOP 100 MODULATED NEURONS BY ZETA MODULATION TEST

% Params
% Includes -100:10:500
config.preT = -100;
config.postT = 500;
config.tBase = 10;
config.smoothSD = 35;
config.eventName = 'waterTime';
config.dataPath = YOURDATAPATH;

% Loop over all datasets
for dataset = mouseInfoAll
    mouse = dataset{1}{1};
    session = dataset{1}{2};
    
    % Load and lock
    [neurons, M, Rconfig, kinematics] = loadLock4Classifier(mouse, session, config);
    M.config = Rconfig;
    save(sprintf('%s%s_%s_cueLocked', savePath, mouse, session), 'kinematics', 'neurons', 'M')
end

%% Reaction time decoding
% Reuses the function previously developed for the decoding pipelines, now
% saves the output to a reduced data format with 3 structs
% kinematics: all kinematic data, from eventLockKinematics
% neurons: all neural data, from eventLockData
% M: metadata as in full R, with config struct of locking params
% INCLUDES ONLY TOP 100 MODULATED NEURONS BY ZETA MODULATION TEST

% Params
% Includes -200:10:600
config.preT = -200;
config.postT = 600;
config.tBase = 10;
config.smoothSD = 10; % less smoothing to avoid overlap across bins
config.eventName = 'liftTimeDLC';
config.dataPath = YOURDATAPATH;

% Loop over all datasets
for dataset = mouseInfoAll
    mouse = dataset{1}{1};
    session = dataset{1}{2};
    
    % Load and lock
    [neurons, M, Rconfig] = loadLock4Classifier(mouse, session, config);
    M.config = Rconfig;
    save(sprintf('%s%s_%s_liftLockedRT', savePath, mouse, session), 'neurons', 'M')
end

%% Target decoding, cross-time generalization
% Reuses the function previously developed for the decoding pipelines, now
% saves the output to a reduced data format with 2 structs
% neurons: all neural data, from eventLockData
% M: metadata as in full R, with config struct of locking params
% INCLUDES ONLY TOP 100 MODULATED NEURONS BY ZETA MODULATION TEST

% Params we use for the paper
% Includes -100:10:1000
config.preT = -100;
config.postT = 1000;
config.tBase = 10;
config.smoothSD = 10; % less smoothing to avoid overlap across bins
config.eventName = 'waterTime';
config.dataPath = YOURDATAPATH;

% Loop over all datasets
for dataset = mouseInfoAll
    mouse = dataset{1}{1};
    session = dataset{1}{2};
    
    % Load and lock
    [neurons, M, Rconfig] = loadLock4Classifier(mouse, session, config);
    M.config = Rconfig;
    save(sprintf('%s%s_%s_cueLockedXT', savePath, mouse, session), 'neurons', 'M')
end