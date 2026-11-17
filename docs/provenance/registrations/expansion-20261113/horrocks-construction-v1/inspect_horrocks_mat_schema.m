function report = inspect_horrocks_mat_schema(inputFile)
% OWNER ONLY, after exact ZIP and selected member digest verification.
% Schema inspection only; no fitting, spike binning, trial selection or scores.
% This source has not been executed. Whole archive/member rights remain gates.
inventory = whos('-file',inputFile);
names = {inventory.name};
assert(all(ismember({'trials','units'},names)), 'Missing source variables');
assert(strcmp(inventory(strcmp(names,'trials')).class,'struct'));
assert(strcmp(inventory(strcmp(names,'units')).class,'struct'));
S = load(inputFile,'trials','units');
assert(isstruct(S.trials) && isscalar(S.trials));
assert(isfield(S.trials,'Speed2D') && isstruct(S.trials.Speed2D));
T = S.trials.Speed2D;
requiredTrialFields = {'PDstart','PDend','Contrast1','numDots1','VelX1','WheelSpeed'};
requiredUnitFields = {'spike_times','isi_viol','amplitude_cutoff','amplitude'};
assert(all(isfield(T,requiredTrialFields)));
assert(isstruct(S.units) && all(isfield(S.units,requiredUnitFields)));
for k = 1:numel(T)
    for f = 1:5
        value = T(k).(requiredTrialFields{f});
        assert(isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value));
    end
    assert(isnumeric(T(k).WheelSpeed) && isreal(T(k).WheelSpeed) && ...
        isvector(T(k).WheelSpeed) && ~isempty(T(k).WheelSpeed) && ...
        all(isfinite(T(k).WheelSpeed)));
end
for k = 1:numel(S.units)
    x = S.units(k).spike_times;
    assert(isnumeric(x) && isreal(x) && (isvector(x) || isempty(x)) && all(isfinite(x)));
    for f = 2:4
        value = S.units(k).(requiredUnitFields{f});
        assert(isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value));
    end
end
report.schema = 'horrocks-mat-structure-observation-v1';
report.original_trial_count = numel(T);
report.original_unit_count = numel(S.units);
report.nTrials_variable_present = any(strcmp(names,'nTrials'));
report.required_trial_fields = requiredTrialFields;
report.required_unit_fields = requiredUnitFields;
report.wheel_time_support_verified = false;
report.identity_and_content_join_verified = false;
report.scientifically_admitted = false;
end
