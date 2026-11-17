# Typed display of native DoSEI observations

This pure component renders a caller-authenticated paired observation as a
1000×640 PNG. It exposes only `view`, `window` and `gain` actions. It has no file
reader, arbitrary execution, filtering, signal detector or model integration.
No authentic EEG has been rendered with this implementation yet; generated
fixtures and layout inspection do not qualify a complete viewer-only runtime.

Both channels retain microvolt calibration and time in milliseconds relative to
the source marker. Every visible observed value receives a point marker.
Source hardware endpoints use orange markers and do not form connecting lines.
Blank grid cells have a separate gray strip. At a 30-second view this strip may
appear continuous because the common table is 250 Hz and the documented signal
rate is nominally 125 Hz; it is not a corruption or dropout-severity score.
The source reports an empirical rate of 124.28 Hz. Neither aggregate blank counts
nor the renderer establish a fixed every-other-row phase.

The declared policy `dosei_observed_points_gap8_display_v1` draws a line only
between consecutive unflagged observations in a channel, separated by a positive
gap of at most 8 ms, with only source blanks between and no duplicate table-time
crossing. It breaks otherwise. These lines are display geometry; they never
create samples, impute a signal or reproduce an undocumented author plotting
procedure. Zoom and gain change only the view. Values beyond a selected gain
are marked as clipped at that view gain; the underlying observation is unchanged.
Connecting segments are clipped geometrically at the panel boundary, rather
than moving their original vertices onto the gain limits.

This policy requires the exact accepted release profile: the complete saved
verification establishes only quality states 0, 1 and 16, so an unobserved cell
in this release is a source blank rather than another invalid-conversion class.
The same profile must be disclosed to both workflows. Missing, mismatched or
wrong-profile input is refused; there is no silent fallback representation.

`TraceViewer` checks the profile's required source-proof, cohort, input and
array-identity binding fields. These shape/hash checks do not authenticate an
array's provenance or current identity. A host driver still must authenticate
the complete source proof, private case index and closed source-array identity,
bind the actual public packet hash, and isolate the participant. The pure
component explicitly reports that it does not perform source authentication.
Passing a plausible profile object is not authorization to render real data.

Only raster bytes and typed view receipts may cross the viewer-only interface.
The source arrays, private indices and labels, geometry primitives, Python
module, profile-validation plumbing and raw packet stay server-side. The code
workflow receives the same public observation through its separately declared
interface. No source recording ID, filename, absolute clock, target or proof hash
is drawn on the plot.

Generated controls cover sparse connections, duplicate times, endpoint and gap
breaks, complete maximum-size windows, null/empty cases, profile refusal, typed
actions, PNG integrity, explicit gain clipping and private-field rejection.
Actual maximum-window and zoom PNGs were visually inspected during development;
time-tick labels were centered and blank strips labeled as grid cells. The full
benchmark still needs the authenticated host reader, isolated delivery and
admitted canonical scoring policy. No model performance or clinical claim is
established by the viewer.
