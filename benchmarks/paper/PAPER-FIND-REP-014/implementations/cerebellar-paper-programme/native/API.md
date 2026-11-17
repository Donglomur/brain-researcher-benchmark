# Native source component

This implements the root-accepted PAPER-FIND-REP-014 source design. It does not authorize actual input loading, MATLAB/toolbox execution, fitting or scoring. Every operation below is a future trusted phase under the owner's concrete engine, original clock and resource ledger. These private helpers are excluded from both candidate environments. A and B use their own committed reconstruction programs; B may receive only the exact 42 original author files.

## Python bridge

bridge.py exposes:

- validate_bindings(bindings): verifies the fixed canonical BINDINGS identity and all42 original files, nine branches, ten input objects and67 roots.
- assembly_plan(original_root, helper_root, bindings, helper_pins, role): produces61 pinned source-copy records:42 originals, nine saved wrappers, three native export helpers and seven new preparation helpers. helper_pins maps every PREPARATION_FILES name to {bytes,sha256} from the owner's reviewed executable manifest. Only operator/reference roles are allowed. No body reads or execution occur here.
- assemble(fresh_workspace, plan, max_read_bytes, max_write_bytes): captures every exact source body before creating a new workspace, then writes exclusively, checks progress, fsyncs files/directories and returns a full inventory with logical source read/write bytes. The owner journals/retires the workspace even after failure. No original arrays are read by this Python function.
- launch_spec(action, matlab, workspace, data_root, output_root, role, branch=None, limits_path=None, initial_seed=None): returns {argv,cwd,action,role,required_outputs,...} for the engine; it never runs a process. matlab is an approved absolute executable in the frozen image; cwd is /work. The fixed expression adds the workspace and dependencies using escaped MATLAB string literals.

For action=prepare, role is operator, limits_path is an absolute immutable file and branch/seed are absent. It invokes nb_i_prepare and requires PREPARED.json plus every declared NPY. For action=branch, role is reference, limits_path is absent, branch is one of the exact nine names, and initial_seed is an explicit integer in [0,2^32). It invokes unchanged nb_run_BRANCH and writes NATIVE.json. The seed is a prospective repeatability choice, not historical execution evidence; source resets and plot RNG calls remain intact. The owner may invoke argv with subprocess.run(check=True) inside its engine-controlled worker; no callback or arbitrary command is needed.

Original root is the existing cerebellar-dopamine-paper-paper-exposure-v2 tree: private/source/code, private/native-prepared-r3 wrappers, and three export helpers. BINDINGS pins all paths/sizes/SHA256 values. The owner must authenticate the complete source/image/mount closure, native toolbox/Java versions and all ten complete input bodies before invocation. Python role checks do not replace that external boundary.

## Preparation operation

nb_i_prepare(data_root, output_root, limits_file) requires an existing empty owned output directory. Limits have exactly max_files, max_file_bytes, max_output_bytes, max_metadata_bytes, max_collection_items and max_native_elements. They are positive exact integers, with metadata≤file≤whole-output bounds. Caps refuse complete output; they never trim a collection, cell or time interval.

The function censuses every variable in all ten originals, including embedded bsln/control aggregates. Numeric census leaves contain class/shape/emptiness only; numeric payload bodies are not hidden in JSON. Private strings and collection membership remain available for identity admission. Native load expansion, decompression and input-read traffic are unknown and require actual isolated operation controls; a MAT header/element cap does not establish a memory bound.

Both MainData parts are concatenated in original order after reproducing unrestricted sequential load precedence: each required micedats1, micedats2 and dirTable variable comes from the last of mainData1.mat/mainData2.mat whose authenticated census declares it. Missing/incompatible required values refuse. Names do not imply files. main_load_sequence and main_variable_owners record the exact observed ownership; bridge.resolve_variable_owners provides the matching pure-metadata check. Complete released trial arrays are exported. Flags must be compatible with native column-vector selection, and event orientations must agree; preparation does not silently repair implicit-expansion failures. Selection uses exact source goodMvmt, strict mvlen>6, measured-delay and event-frame trash rules. No response/reliability/significance cell selection is added. GrC uses endAlgn.sigFilt_right_green; CF uses rewAlgn.sprate_right_red. First-session nearest-inclusive grids and literal source linear interpolation/extrapolation are retained, before trial averaging or partitioning. Native errors are failures, not repaired or reduced cohorts.

PREPARED.json schema is filio_i_prepared_v1. It contains files_census, acquisitions, output_files, explicit false identity/provenance verification fields, producer_io and unknowns. Every acquisition key is a technical row%06d-main/water coordinate, not an animal/session identity. original_trial_count denotes released source-array rows, not all physical attempts. source_part identifies the concatenation operand (micedats1 or micedats2), not a publisher file; source_variable, source_owner_file and source_ordinal locate the actual last-loaded variable. source_row locates dirTable in its actual last-loaded owner file. source_path, source_context_path and source_field_paths retain exact locators. collection is main/water. views preserves Water,1-s DA,DA-first,2-s DA membership without duplicating a DA-first target.

source_context preserves scalar DAType,Delay,FirstRew,GrCs,CFType and private DA_Dir/WaterDir/Alt_Delay_Dir. Source vocabularies/missing values are not biological authentication. acquisition.dtb and dtb_seconds both preserve curd.dtb unchanged; the name denotes intended source interpretation, not independently authenticated units. Owner admission must validate units and event/clock/omission joins.

Numeric descriptors have exactly {path,bytes,sha256,shape,dtype}. NPY1 is little-endian C order, allowing only <f8,<f4,<i8,|i1. shape is always a JSON list, including one-dimensional arrays. Source float values and nonfinite statuses remain unchanged. Logical masks become signed-byte0/1; generated trial/window indices are signed64 and one-based. Raw source event/frame vectors preserve original numeric values/classes rather than casting missing frame gaps to integer zeros.

Acquisition arrays: trial_ordinal,rewarded,goodMvmt_original,goodMvmt_source,trash_excluded,eligible,eligible_rewarded,eligible_omitted,mvlen,movement_duration_ms,rewdel_seconds,truestart,trueend,rewtimes,frame_right,behavior_clock,neural_clock,rew_pos,trashframes. Trial vectors retain the full released axis. rew_pos is [trial,behavior_time,2] from rewAlgn.pos; behavior_clock is tmpxx, neural_clock is tmpx_right. Duration is exactly (trueend−truestart)*dtb*1000; rewdel_seconds is exactly (rewtimes−trueend)*dtb. trashframes_present separates missing from empty source fields. The owner derives local handle features: CF u=t, GrC u=t−rewdel. No neural values enter candidate-visible queries.

registrations preserves complete chronicGreen/chronicRed typed trees from the parent source recording for main and water records. Numeric leaves are separate NPY files. Registration orientation, animal identity and physical aliases are not inferred from matches or sizes.

Modality statuses:

- present: full cell_count/required_cells, signal source_path, trial×cell×time targets, target_time,source_time and one-based source_time_indices descriptors.
- structural_absence: native modality flag does not select it; required_cells=0. Available source cell_count is retained, otherwise JSON null.
- outside_selected_views: acquisition.views is empty under native selectors. Full row/clock/behavior/registration census remains; no out-of-scope neural field is required/interpolated. Source cell_count is retained or null; required_cells=0. This status is forbidden for nonempty views.

Missing waterdat has an explicit structural-absence acquisition. Water view appears only when native Delay==1 selects it. Empty/absent dispositions never become invented zero neural responses.

output_files lists every NPY before PREPARED.json. PREPARED itself enters the owner's generic OUTPUTS envelope after MATLAB natural close; it cannot pin itself. There are no numeric payload arrays hidden in PREPARED JSON. Writers check complete writes/closes and hash completed bodies. The isolated output directory is private to the trusted process. Failure may leave partial private files; those fail full-envelope admission and are retired by the owner.

## Reference output and gates

NATIVE.json is the existing filio_native_numeric_v1 export: full67 roots across nine branches, complete shapes/status codes and full-axis masks. Original nb_export has a128,000,000-byte serialized ceiling whose sufficiency is unqualified. No crop/smaller target list replaces full support. Original bodies are byte-preserved after the saved dataDir substitution, excluding declared wrapper prelude and appended exports.

Preparation does not prove physical trial aliases, sample support, chronology, failed-attempt retention, raw processing provenance or biological hierarchy. In particular, frame_right and dt do not justify a guessed raw-sample origin/rounded overlap certificate. These remain independently authenticated owner gates. The six RAM-only controls test metadata behavior and format arithmetic, not MATLAB writer/runtime parity. No actual native or scientific qualification is claimed.
