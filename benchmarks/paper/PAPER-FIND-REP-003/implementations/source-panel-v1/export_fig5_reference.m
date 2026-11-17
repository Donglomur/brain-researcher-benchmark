function export_fig5_reference(outputsM1_rr, outputsS1_rr, destination)
% EXPORT_FIG5_REFERENCE Operator-only export from completed author Figure 5 outputs.
% No model fitting or source RNG calls. Do not give the resulting JSON to a
% participant: it contains outcomes, author predictions, folds and saved VEs.
% Source: kaufmanlab/GSK26-public, 815b610b3beddfed5a3abf611d3a465ab9e4ce5c.
% This adapter has not been executed in MATLAB or on authentic source outputs.

assert(~isfile(destination), 'Destination already exists');
assert(numel(outputsM1_rr) == 5 && numel(outputsS1_rr) == 5);
mice = {'cfa17', 'cfa19', 'cfa20', 'cfa22', 'cfa24'};
sessionsM1 = {'200825', '200820', '201114', '220605', '220727'};
sessionsS1 = {'200827', '200826', '201118', '220611', '220724'};
reference.schema = 'fig5-source-panel/v1';
reference.task_id = 'PAPER-FIND-REP-003';
reference.source_revision = '815b610b3beddfed5a3abf611d3a465ab9e4ce5c';
reference.role = 'operator_author_reference';
reference.joint_names = {'SHDRf', 'SHDRa', 'SHDRr', 'ELBOf', 'WRSTf', 'WRSTd', 'WRSTr', ...
    'MCP1f', 'MCP2f', 'MCP3f', 'MCP4f', 'MCP1a', 'MCP2a', 'MCP3a', 'MCP4a', ...
    'MCP1o', 'MCP4o', 'P1P2', 'P2P3', 'P3P4', 'PIP1f', 'PIP2f', 'PIP3f', 'PIP4f'};
reference.angle_units = 'degrees';
reference.time_ms = -100:10:400;
reference.sessions = cell(1, 10);
for mouse = 1:5
    reference.sessions{2*mouse-1} = extract_session(outputsM1_rr(mouse), mice{mouse}, sessionsM1{mouse}, 'M1');
    reference.sessions{2*mouse} = extract_session(outputsS1_rr(mouse), mice{mouse}, sessionsS1{mouse}, 'S1');
end
% Full JSON export can be large; run only within an approved native resource
% protocol. Existence checks are operator safeguards, not a secure freeze.
body = jsonencode(reference);
assert(~isfile(destination), 'Destination was created during extraction');
[fid, message] = fopen(destination, 'w');
assert(fid ~= -1, message);
cleanup = onCleanup(@() fclose(fid));
written = fprintf(fid, '%s\n', body);
assert(written >= numel(body), 'Incomplete reference write');
end

function session = extract_session(record, mouse, date, area)
assert(strcmp(record.mouse, mouse), 'Original mouse order required');
o = record.output; % instantaneous full model; not partial, lagged or residual
assert(strcmp(o.kinematicField, 'jointAngles'));
assert(strcmp(o.neuralField, 'radical_rates'));
assert(strcmp(o.regType, 'ridge'));
assert(o.nFolds == 5 && o.nPartitions == 10 && o.nModels == 50);
assert(isequal(size(o.VEs), [50, 24]) && all(isfinite(o.VEs(:))));
ids = [o.outcomes.trialNumber];
assert(numel(ids) >= 10 && numel(unique(ids)) == numel(ids));
assert(isequal(ids, [o.predictors.trialNumber]));
session.mouse = mouse;
session.session = date;
session.area = area;
session.trials = cell(1, numel(ids));
for trial = 1:numel(ids)
    y = o.outcomes(trial).data;
    assert(isequal(size(y), [51, 24]) && all(isfinite(y(:))));
    session.trials{trial} = struct('trial_number', ids(trial), 'joint_angles', y);
end
session.models = cell(1, 50);
for model = 1:50
    test = o.testInds{model};
    train = o.trainInds{model};
    assert(isequal(ids(test), o.trialsTest{model}));
    assert(isequal(ids(train), o.trialsTrain{model}));
    x = cat(1, o.predictors(test).data);
    beta = o.betas{model};
    assert(size(x, 2) == 90 && isequal(size(beta), [91, 24]));
    % Exact resubmission intercept formula from cvRegress.m; baggedDecode
    % reconstructions are not a replacement for held-out predictions per fit.
    prediction = x * beta(2:end, :) + beta(1, :);
    assert(all(isfinite(prediction(:))));
    item.model = model;
    % Cells preserve JSON array shape even for a singleton held-out group.
    item.train_trials = num2cell(ids(train));
    item.test_trials = num2cell(ids(test));
    item.author_prediction = prediction;
    item.author_ve = o.VEs(model, :);
    session.models{model} = item;
end
end
