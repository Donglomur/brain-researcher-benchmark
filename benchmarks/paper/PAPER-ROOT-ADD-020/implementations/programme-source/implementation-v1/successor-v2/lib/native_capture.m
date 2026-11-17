function capture = native_capture(request)
% FUTURE LITERAL MATLAB CAPTURE TEMPLATE -- NEVER RUN DURING SOURCE AUTHORING.
% This function is not a qualification, sandbox, execution authorization or
% resource controller. A separately authorized external supervisor must admit
% the full release, source/feature/row/cell/time identities, exact MATLAB image,
% all 56 jobs, complete output capacity and original-clock natural completion.
% Do not pass authentic data here before those gates close.
%
% request fields:
%   future_execution_authorized          logical true from trusted supervisor
%   admission_sha256                     full source/runtime/workload admission
%   instrumentation_review_sha256        review of THIS exact wrapper version
%   release_root                         immutable admitted original release
%   matlab_version                       exact admitted version() string
%   expected_times                       14 cells, each COMPLETE admitted t
%   expected_cell_ids                    14 cells, COMPLETE admitted cell IDs
%   role_admission_sha256                14 admitted source/row/cell receipts
%   original_clock_origin               unchanged supervisor monotonic origin
% The returned structure contains private original workspace arrays and source
% text. It belongs only in the future protected reproduction output store.
% Caller must persist/digest it under its admitted envelope and separately
% observe natural process completion. Never expose it to improvement contexts.

assert(isstruct(request) && isequal(request.future_execution_authorized, true), ...
    'paper020:authority', 'Future independently authorized execution required');
assert(exist('OCTAVE_VERSION', 'builtin') == 0, 'paper020:notMATLAB', ...
    'Octave is not literal MATLAB qualification');
assert(strcmp(version, request.matlab_version), 'paper020:version', ...
    'Exact separately admitted MATLAB version required');
assert(valid_sha(request.admission_sha256) && ...
    valid_sha(request.instrumentation_review_sha256), 'paper020:receipt', ...
    'Trusted admission and exact instrumentation review receipts required');
assert(isnumeric(request.original_clock_origin) && isscalar(request.original_clock_origin) ...
    && isfinite(request.original_clock_origin), 'paper020:clock', 'Original clock required');

% Exact original14 roster. Pooled rows are required diagnostics, not additional
% animals; this wrapper makes no pooled/individual identity equivalence claim.
configs = { ...
 'A_TP_set3','A','TP',3; 'A_AM_set2','A','AM',2; ...
 'A_ML_set2','A','ML',2; 'A_PR_set2','A','PR',2; ...
 'B_PR_set2','B','PR',2; 'C_AM_set2','C','AM',2; ...
 'D_ML_set2','D','ML',2; 'E_PR_set3','E','PR',3; ...
 'E_TP_set3','E','TP',3; 'E_AM_set2','E','AM',2; ...
 'pooled_TP_set3','','TP',3; 'pooled_AM_set2','','AM',2; ...
 'pooled_ML_set2','','ML',2; 'pooled_PR_set2','','PR',2};
assert(numel(request.expected_times) == 14 && numel(request.expected_cell_ids) == 14 ...
    && numel(request.role_admission_sha256) == 14, 'paper020:fullRoster', ...
    'Every original configuration requires admitted time/cell/role support');

% Original source pins come from the accepted design evidence index. No author
% source bodies are distributed here. Loading arrays remains in original
% load_data, only inside separately admitted future execution.
names = {'analysis_sta.m','analysis_sta2.m','analysis_sta_time_course.m', ...
 'analysis_sta2_time_course.m',fullfile('code','analysis_STA.m'), ...
 fullfile('code','STA_sub.m'),fullfile('code','STAcorr.m'), ...
 fullfile('code','cosine_sim.m'),fullfile('code','load_data.m'), ...
 fullfile('code','sliding_window_from_psth.m')};
pins = { ...
 '9001856c80ce23d31448c48e50aec0e75f1b299989e415e0dbf40faef8c5eb9b', ...
 '1d8a63729cfce78ea6c214aec22b3c2324edacb7c4795b5409de6e6ccba368f1', ...
 'b119fd943288238a139bb6d7aed13ce39ad1c4af74837751bf931060304a2b4d', ...
 '9dcda750fbfacf77e9a627acde98f21429651207637a92073629036f4070664d', ...
 '7a9b917ceb77d52d7c1347e86ff03ea61607ba7776c5f1d9adeeca235f9b8f5e', ...
 '202d822bcecb459eb00e1722f8c29b0745f5c6ca58a1475f9d1cd77f767a8a30', ...
 '2e477077be3ada4b9089bba07846dcdf3616092ffa8e042b551ca9203214b340', ...
 '9775eff48a352eb825c235d67ab489b34163d47d66144fe45f94d39c561b3b76', ...
 '9dc612d6c2e0bc8e6b125b9dcf22d4ca624e1d8fe1bc3109c88c70f5c5e3ce55', ...
 '8bb67354a5f2ffa8a533ddacb312736fe42bcefa06b4dc2dc09e303156d1f258'};
sources = cell(size(names));
for k = 1:numel(names)
    source_file = fullfile(request.release_root, names{k});
    fid = fopen(source_file, 'rb');
    assert(fid ~= -1, 'paper020:source', 'Original source file missing');
    close_file = onCleanup(@() fclose(fid));
    bytes = fread(fid, Inf, '*uint8');
    clear close_file
    assert(strcmp(hash_bytes(bytes), pins{k}), 'paper020:sourcePin', ...
        'Original source bytes differ from admitted design evidence');
    sources{k} = char(bytes.');
end

old_dir = pwd; old_path = path;
restore = onCleanup(@() restore_environment(old_dir, old_path)); %#ok<NASGU>
cd(request.release_root);
addpath(fullfile(request.release_root, 'code'), '-begin');
% Every called scientific helper must resolve to the admitted exact file.
helpers = {'analysis_STA','STA_sub','STAcorr','cosine_sim', ...
    'load_data','sliding_window_from_psth'};
for k = 1:numel(helpers)
    assert(strcmp(which(helpers{k}), fullfile(request.release_root,'code',[helpers{k} '.m'])), ...
        'paper020:shadowing', 'Scientific helper is shadowed by unadmitted source');
end
capture.schema = 'paper020_future_literal_matlab_capture_v1';
capture.qualified = false;
capture.status = 'provisional_until_external_full_output_and_natural_exit_admission';
capture.request = request;
capture.source_paths = names;
capture.source_sha256 = pins;
capture.matlab_version = version;
capture.computer = computer;
capture.toolboxes = ver;
capture.histogram_contract = struct('Normalization','probability','BinWidth',0.1, ...
    'configured_xlim',[-1 1],'literal_histogram_edges_captured',false, ...
    'status','plotting_suffix_omitted_edges_require_separate_native_plot_diagnostic');
capture.original_clock_origin = request.original_clock_origin;
capture.started_utc_clock = clock; % descriptive wall clock; does not replace origin
capture.jobs = cell(14,2,2);
methods = {'sta','linear_regression'};
modes = {'static','time_course'};
for c = 1:14
    assert(valid_sha(request.role_admission_sha256{c}), 'paper020:roles', ...
        'Full original role admission missing');
    validate_native_times(request.expected_times{c});
    for method_index = 1:2
        for mode_index = 1:2
            set_id = configs{c,4};
            driver_index = 1 + (set_id == 3) + 2*(mode_index == 2);
            original = sources{driver_index};
            [instrumented, edits] = instrument(original, configs(c,:), ...
                methods{method_index}, modes{mode_index});
            job.configuration = configs{c,1};
            job.family = 'native_literal';
            job.method = methods{method_index};
            job.mode = modes{mode_index};
            job.driver = names{driver_index};
            job.original_source_sha256 = pins{driver_index};
            job.instrumented_source = instrumented;
            job.instrumented_source_sha256 = hash_bytes(uint8(instrumented));
            job.instrumentation_edits = edits;
            job.started_utc_clock = clock;
            job.warning_state = warning;
            lastwarn('');
            try
                % No portable calculations are substituted for original helpers.
                [workspace, transcript] = evaluate_original(instrumented);
                assert(isequal(workspace.t(:), request.expected_times{c}(:)), ...
                    'paper020:timeSupport', 'Original time grid differs from admitted grid');
                assert(size(workspace.sta_fam,1) == numel(request.expected_cell_ids{c}), ...
                    'paper020:cells', 'Original cell support differs; no cropping allowed');
                job.workspace = workspace;
                job.transcript = transcript;
                [job.last_warning, job.last_warning_id] = lastwarn;
                job.status = 'captured_not_qualified';
            catch exception
                job.status = 'failed';
                job.exception_identifier = exception.identifier;
                job.exception_report = getReport(exception, 'extended', 'hyperlinks', 'off');
                job.finished_utc_clock = clock;
                capture.jobs{c,method_index,mode_index} = job;
                capture.status = 'failed_full56_required';
                capture.finished_utc_clock = clock;
                return % partial capture remains explicit; never success-fill jobs
            end
            job.finished_utc_clock = clock;
            capture.jobs{c,method_index,mode_index} = job;
            clear job
        end
    end
end
capture.finished_utc_clock = clock;
end

function [text, edits] = instrument(original, cfg, method, mode)
% Explicit reviewed nonnumeric edits: normalize source line endings, remove
% workspace clear, replace Windows helper path, bind documented configuration
% and source method, omit only plotting suffix; append nonnumeric collectors.
text = strrep(original, sprintf('\r\n'), sprintf('\n'));
text = regexprep(text, '(?m)^\s*clear\s*\n', '');
text = replace_once(text, 'addpath(''.\code'')', '');
active = regexp(text, '(?m)^face_patch = ''[^'']*''; subject = ''[^'']*'';[^\n]*', 'match');
assert(numel(active) == 1, 'paper020:binding', 'Expected one active configuration binding');
text = replace_once(text, active{1}, sprintf('face_patch = ''%s''; subject = ''%s'';',cfg{3},cfg{2}));
text = replace_once(text, 'method = ''sta'';', ['method = ''' method ''';']);
if strcmp(mode,'static')
    marker = '%% histogram bar overlay (figure 2b)';
else
    marker = '%% figure';
end
positions = strfind(text, marker);
assert(numel(positions) == 1, 'paper020:plotBoundary', 'Exact plotting suffix boundary required');
text = text(1:positions-1);
text = replace_once(text, 'rng(''default'')', sprintf('rng(''default'')\ncapture_rng_before = rng;'));
if cfg{4} == 2
    if strcmp(mode,'static')
        needle = 'cs_unfam(i,:) = cosine_sim( sta_unfam_sub1, sta_unfam_sub2, 2);';
        extra = sprintf('\ncapture_pairs{i,1} = struct(''subset_rows'',sub_stim_ind1,''complement_rows'',sub_stim_ind2,''subset_axis'',sta_unfam_sub1,''complement_axis'',sta_unfam_sub2);');
    else
        needle = 'cs_unfam(:,i,j) = cosine_sim( sta_unfam_sub1, sta_unfam_sub2, 2);';
        extra = sprintf('\ncapture_pairs{j,i} = struct(''subset_rows'',sub_stim_ind1,''complement_rows'',sub_stim_ind2,''subset_axis'',sta_unfam_sub1,''complement_axis'',sta_unfam_sub2);');
    end
    text = replace_once(text, needle, [needle extra]);
end
% Full raw/workspace intermediates contain each window in sw or static resp_raw,
% all native arrays, feature basis, times and all subset/complement coefficients.
% Nan masks are preserved in these arrays. No fitted array is exported to A/B
% improvement contexts. Original regress warning/failure behavior is retained.
text = [text sprintf('\ncapture_rng_after = rng;\n')];
if strcmp(mode,'time_course')
    summary = sprintf(['capture_control_per_cell = nanmean(cs_unfam,3);\n' ...
      'capture_familiar_mean = nanmean(cs_fam);\n' ...
      'capture_control_mean = nanmean(capture_control_per_cell);\n' ...
      'capture_familiar_count = sum(~isnan(cs_fam));\n' ...
      'capture_control_count = sum(~isnan(capture_control_per_cell));\n' ...
      'capture_familiar_sem = std(cs_fam,''omitnan'')./sqrt(capture_familiar_count);\n' ...
      'capture_control_sem = std(capture_control_per_cell,''omitnan'')./sqrt(capture_control_count);\n']);
    text = [text summary];
end
edits = {'line_endings_CRLF_to_LF','remove_clear_only','platform_helper_path', ...
 'explicit_original_configuration','explicit_STA_or_OLS_source_method', ...
 'omit_plotting_suffix_only','capture_rng_without_extra_draws', ...
 'capture_all_subset_complement_axes','capture_original_time_summary_formulas'};
end

function [workspace, transcript] = evaluate_original(internal_text)
% Workspace-isolated eval of exactly recorded instrumentation. Source hashes,
% dependency resolution and trusted external isolation remain mandatory.
internal_transcript = evalc(internal_text);
internal_names = who;
workspace = struct();
for internal_i = 1:numel(internal_names)
    internal_name = internal_names{internal_i};
    if strncmp(internal_name,'internal_',9) || strcmp(internal_name,'workspace')
        continue
    end
    workspace.(internal_name) = eval(internal_name);
end
transcript = internal_transcript;
end

function text = replace_once(text, needle, replacement)
positions = strfind(text, needle);
% The source method alternative is commented, but the default needle occurs once.
assert(numel(positions) == 1, 'paper020:instrumentation', 'Instrumentation anchor must occur exactly once');
text = strrep(text, needle, replacement);
end

function validate_native_times(t)
assert(isnumeric(t) && isvector(t) && numel(t)>1 && all(isfinite(t)), ...
    'paper020:times', 'Full finite clock required');
delta = diff(t(:));
assert(delta(1)>0 && all(delta==delta(1)), 'paper020:grid', 'Exact uniform increasing grid required');
width = round(50/delta(1));
assert(width>=1 && mod(width,2)==1, 'paper020:width', 'Odd integral native width required');
centers = find(t>0 & t<500);
half = (width-1)/2;
assert(~isempty(centers) && centers(1)-half>=1 && centers(end)+half<=numel(t) ...
    && any(t>50 & t<300), 'paper020:support', 'Every native static/time window required');
end

function result = valid_sha(value)
result = ischar(value) && numel(value)==64 && ~isempty(regexp(value,'^[0-9a-f]{64}$','once'));
end

function result = hash_bytes(bytes)
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(bytes(:));
raw = typecast(digest.digest(),'uint8');
result = lower(reshape(dec2hex(raw,2).',1,[]));
end

function restore_environment(old_dir, old_path)
cd(old_dir);
path(old_path);
end
