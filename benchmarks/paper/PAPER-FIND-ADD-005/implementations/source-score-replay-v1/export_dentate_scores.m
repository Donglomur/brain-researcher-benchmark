function export_dentate_scores(fitFiles, outputFile)
% Export operator-owned author fit artifacts for replay.py; no fitting occurs.
% Requires the pinned author code on the MATLAB path in a clean MATLAB process.
% JSON contains neural targets and must stay in the private evidence directory.

  expectedHash = 'eb712ad14d1b9465ddbaa84c460657eac9cfa7f3f7772212c3fdcbd543287ded';
  actualHash = fileSHA256(which('CategorizedModel'));
  assert(strcmp(actualHash, expectedHash), 'The resolved author class is not the pinned source.');
  assert(~isfile(outputFile), 'Refusing to replace an existing output.');
  if ischar(fitFiles) || isstring(fitFiles)
    fitFiles = cellstr(fitFiles);
  end
  assert(iscell(fitFiles) && ~isempty(fitFiles), 'Provide explicit author fit files.');
  exported = struct('schema', 'dentate-author-score-export-v1', ...
                    'source_commit', '130f5e64f86bd63980f70bb839c02cd264782aef', ...
                    'source_class_sha256', actualHash);
  entries = {};
  for iFile = 1:numel(fitFiles)
    saved = load(fitFiles{iFile}, 'unspecializedModel', 'hierarchicalModel', 'cfg');
    assert(isfield(saved, 'unspecializedModel') && isfield(saved, 'hierarchicalModel') ...
           && isfield(saved, 'cfg'), 'Not a source fitSingleCellGLM save.');
    assert(numel(saved.unspecializedModel) == numel(saved.hierarchicalModel), 'Model list mismatch.');
    for iCell = 1:numel(saved.unspecializedModel)
      base = saved.unspecializedModel{iCell};
      assert(~isempty(base), 'Incomplete source fit: empty unspecialized cell.');
      if isstruct(base)
        record = identityRecord(base.id);
        record.status = 'unfitted';
        record.reason = 'source_unspecialized_model_is_experiment_struct';
        entries{end+1} = record; %#ok<AGROW>
        continue
      end
      assert(isa(base, 'CategorizedModel') && isscalar(base), 'Invalid source model object.');
      expt = base.design.dspec.expt;
      record = identityRecord(expt.id);
      record.status = 'fitted';
      record.source_n_cv_folds = saved.cfg.nCVFolds;
      record.bin_ms = expt.binSize;
      record.bias_column_present = ~isempty(base.design.biasCol);
      record.selected_source_trial_indices = arrayForJSON(find(expt.selectedTrials));
      record.source_trial_numbers = arrayForJSON([expt.trial.trial_nr]);
      record.trial_index_by_bin = arrayForJSON(base.design.trialX);
      record.target_counts = arrayForJSON(base.target);
      record.unspecialized_prediction_means = arrayForJSON(base.prediction);
      record.unspecialized_cv2_neg_log_likelihood = finiteScalar(base.fitInfo.cv2NegLnL);
      record.unspecialized_cv_train_sel_present = ~isempty(base.cvTrainSel);
      hierarchy = saved.hierarchicalModel{iCell};
      assert(isa(hierarchy, 'CategorizedModel') && ~isempty(hierarchy), 'Incomplete source hierarchy.');
      [joint, jointTarget] = hierarchy.jointPrediction();
      assert(isequal(jointTarget, base.target), 'Final hierarchy target differs from base target.');
      record.native_joint_log_likelihood = finiteScalar(CategorizedModel.poissonLogLikelihood(jointTarget, joint));
      leafRecords = cell(1, numel(hierarchy));
      for iLeaf = 1:numel(hierarchy)
        leaf = hierarchy(iLeaf);
        leafRecord = struct();
        leafRecord.trial_indices = arrayForJSON(leaf.design.trialIndices);
        leafRecord.bin_indices = arrayForJSON([leaf.design.dspec.expt.trialBins{leaf.design.trialIndices}]);
        leafRecord.target_counts = arrayForJSON(leaf.target);
        leafRecord.prediction_means = arrayForJSON(leaf.prediction);
        leafRecord.reported_cv2_neg_log_likelihood = finiteScalar(leaf.fitInfo.cv2NegLnL);
        leafRecord.fit_info_equals_progenitor = false;
        if leaf.hasProgenitor()
          leafRecord.fit_info_equals_progenitor = isequaln(leaf.fitInfo, leaf.progenitor.fitInfo);
        end
        leafRecord.cv_train_sel_present = ~isempty(leaf.cvTrainSel);
        leafRecords{iLeaf} = leafRecord;
      end
      record.hierarchical_leaves = leafRecords;
      entries{end+1} = record; %#ok<AGROW>
    end
  end
  exported.cells = entries;
  text = jsonencode(exported);
  fid = fopen(outputFile, 'w');
  assert(fid >= 0, 'Could not create output file.');
  cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
  bytes = unicode2native([text newline], 'UTF-8');
  assert(fwrite(fid, bytes, 'uint8') == numel(bytes), 'Incomplete output write.');
end

function record = identityRecord(experimentID)
  separator = strfind(experimentID, '_');
  assert(~isempty(separator), 'Source experiment ID lacks animal/cell separator.');
  record = struct('monkey', experimentID(1:separator(1)-1), 'cell_id', experimentID(separator(1)+1:end));
  assert(~isempty(record.monkey) && ~isempty(record.cell_id), 'Missing source identity.');
end

function result = arrayForJSON(value)
% Cell array preserves a JSON array even when the source vector has one item.
  assert(isnumeric(value) && isvector(value) && ~isempty(value) && isreal(value) ...
         && all(isfinite(value(:))), 'Expected a finite nonempty source vector.');
  result = num2cell(full(value(:)'));
end

function result = finiteScalar(value)
  assert(isnumeric(value) && isscalar(value) && isreal(value) && isfinite(value), ...
         'Expected a finite scalar source score.');
  result = full(value);
end

function result = fileSHA256(path)
  assert(~isempty(path), 'Pinned CategorizedModel is not on the MATLAB path.');
  fid = fopen(path, 'rb');
  assert(fid >= 0, 'Cannot read author class source.');
  cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
  digest = java.security.MessageDigest.getInstance('SHA-256');
  digest.update(fread(fid, Inf, '*uint8'));
  result = lower(reshape(dec2hex(typecast(digest.digest(), 'uint8'), 2).', 1, []));
end
