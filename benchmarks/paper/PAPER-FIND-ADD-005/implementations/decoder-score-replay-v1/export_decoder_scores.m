function export_decoder_scores(fitFiles, outputFile)
% Operator-only export of existing pinned-source decoder saves; no model fit.
% Contains neural labels/predictions: keep all exports private.
% Source identity does not establish the history of the supplied MAT saves.
  expected = 'c1b9008ecdd5d2c6bbd5c10b93e0285e4f7baf4fe1fff0ba77b1c4e6428e3179';
  actual = fileSHA256(which('decodeTrialOutcome'));
  assert(strcmp(actual, expected), 'Resolved decoder source is not the pinned version.');
  assert(~isfile(outputFile), 'Output already exists.');
  if ischar(fitFiles) || isstring(fitFiles), fitFiles = cellstr(fitFiles); end
  assert(iscell(fitFiles) && ~isempty(fitFiles), 'Supply explicit decoder save paths.');
  exported = struct('schema', 'dentate-decoder-score-export-v1', ...
    'source_commit', '130f5e64f86bd63980f70bb839c02cd264782aef', ...
    'source_decoder_sha256', actual);
  entries = {};
  configuration = [];
  for iFile = 1:numel(fitFiles)
    saved = load(fitFiles{iFile}, 'decoder', 'cfg');
    assert(isfield(saved, 'decoder') && iscell(saved.decoder) && isfield(saved, 'cfg'), ...
      'Not a decodeTrialOutcome save.');
    cfg = saved.cfg;
    current = struct('n_cv_folds', cfg.nCVFolds, 'requested_n_shuffles', cfg.nShuffles, ...
      'time_bin_ms', cfg.timeBin, 'minimum_trials', cfg.minNumTrials, ...
      'behavior_variables', {cfg.behavCategories}, 'behavior_events', {cfg.behavEvents}, ...
      'saved_fit_function_strings', {cellfun(@func2str, cfg.fitFcn, 'UniformOutput', false)});
    if isempty(configuration), configuration = current; end
    assert(isequaln(current, configuration), 'Configuration differs across supplied saves.');
    for iCell = 1:numel(saved.decoder)
      value = saved.decoder{iCell};
      assert(isstruct(value) && isscalar(value) && ~isempty(fieldnames(value)), ...
        'Missing or unfinished source cell; do not silently omit it.');
      if isfield(value, 'experiment')
        expt = value.experiment;
        record = identityRecord(expt.id);
        record.status = 'fitted';
      else
        assert(isfield(value, 'id') && isfield(value, 'trial'), 'Unknown source cell form.');
        expt = value;
        record = identityRecord(expt.id);
        record.status = 'insufficient_cell_trials';
      end
      assert(islogical(expt.selectedTrials), 'Source selectedTrials must be logical.');
      record.selected_prefiltered_trial_indices = rowJSON(find(expt.selectedTrials));
      record.source_trial_numbers = rowJSON([expt.trial.trial_nr]);
      % selectedTrials indexes the list AFTER the source current/past-condition prefilter.
      % trial_nr is retained separately; these indices are not original archive positions.
      if strcmp(record.status, 'fitted')
        groupRecords = {};
        for iVariable = 1:numel(cfg.behavCategories)
          variable = cfg.behavCategories{iVariable};
          assert(isfield(value, variable), 'Missing source behavior-variable group.');
          conditions = value.(variable);
          assert(isstruct(conditions) && ~isempty(conditions), 'Missing source subgroup.');
          for iSub = 1:numel(conditions)
            condition = conditions(iSub);
            assert(strcmp(condition.variable, variable), 'Source variable identity differs.');
            assert(islogical(condition.selectedTrials), 'Source subgroup mask must be logical.');
            group = struct('variable', variable, 'subgroup_index', iSub);
            group.values = rowJSON(condition.values);
            group.selected_experiment_trial_indices = rowJSON(find(condition.selectedTrials));
            group.target = rowJSON(condition.target);
            group.trial_weights = rowJSON(condition.trialWeight);
            if isempty(condition.model)
              group.status = 'insufficient_group_trials';
              group.models = {};
            else
              group.status = 'fitted';
              models = cell(1, numel(condition.model));
              for iEvent = 1:numel(condition.model)
                model = condition.model(iEvent);
                assert(ndims(model.prediction) <= 3 && size(model.prediction,3) == 1, ...
                  'Expected only the retained first-experiment prediction.');
                output = struct('alignment', model.alignment);
                output.aligned_time_ms = rowJSON(model.alignedTime);
                output.first_experiment_prediction = matrixJSON(model.prediction(:,:,1));
                output.retained_accuracy = matrixJSON(model.accuracy);
                models{iEvent} = output;
              end
              group.models = models;
            end
            groupRecords{end+1} = group; %#ok<AGROW>
          end
        end
        record.groups = groupRecords;
      end
      entries{end+1} = record; %#ok<AGROW>
    end
  end
  exported.configuration = configuration;
  exported.cells = entries;
  text = jsonencode(exported);
  % Trusted operator location: existence check is not an OS isolation boundary.
  fid = fopen(outputFile, 'w');
  assert(fid >= 0, 'Could not create output.');
  cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
  bytes = unicode2native([text newline], 'UTF-8');
  assert(fwrite(fid, bytes, 'uint8') == numel(bytes), 'Incomplete output write.');
end

function value = rowJSON(array)
  assert(isnumeric(array) && (isempty(array) || isvector(array)) && isreal(array) ...
    && all(isfinite(array(:))), 'Expected finite numeric source vector.');
  value = num2cell(full(reshape(array, 1, [])));
end

function value = matrixJSON(array)
  assert(isnumeric(array) && ismatrix(array) && isreal(array) && ~isempty(array) ...
    && all(isfinite(array(:))), 'Expected finite source matrix.');
  value = cell(1, size(array,1));
  for i = 1:size(array,1), value{i} = rowJSON(array(i,:)); end
end

function record = identityRecord(id)
  separator = strfind(id, '_');
  assert(ischar(id) && ~isempty(separator), 'Missing source experiment identity.');
  record = struct('monkey', id(1:separator(1)-1), 'cell_id', id(separator(1)+1:end));
  assert(~isempty(record.monkey) && ~isempty(record.cell_id), 'Missing monkey/cell identity.');
end

function result = fileSHA256(path)
  assert(~isempty(path), 'Pinned decoder is not on the MATLAB path.');
  fid = fopen(path, 'rb');
  assert(fid >= 0, 'Cannot read resolved decoder.');
  cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
  digest = java.security.MessageDigest.getInstance('SHA-256');
  digest.update(fread(fid, Inf, '*uint8'));
  result = lower(reshape(dec2hex(typecast(digest.digest(), 'uint8'), 2).', 1, []));
end
