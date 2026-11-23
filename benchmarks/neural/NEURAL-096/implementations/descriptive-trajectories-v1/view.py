"""Typed observation-only SVG heatmaps for the matched NEURAL-096 condition.

Both prior panels retain all 54 units and 20 phase bins on a shared global scale.
The renderer never calculates or displays a prior difference or reference answer.
RGB quantization and finite display size lose precision relative to the numeric
means; matched underlying observations do not mean identical representations.
This source component does not establish a model transport or participant boundary.
"""
from __future__ import annotations

import math
from xml.sax.saxutils import escape


SCHEMA = "neural096-matched-prior-mean-observations/v1"
CELL_KEYS = frozenset(("cell_id", "source_split", "observation_segment", "is_eye",
                       "theta", "n_long", "n_short", "long_rate_hz", "short_rate_hz"))
OPTIONAL_CELL_KEYS = frozenset(("supported", "missing_priors"))
WIDTH = 1360
HEIGHT = 1180
CELL_WIDTH = 24
CELL_HEIGHT = 16
PANEL_TOP = 152
PANEL_LEFTS = (170, 850)
MAX_SVG_BYTES = 512 * 1024


class ViewError(ValueError):
    """Invalid or incomplete matched observations or typed view selection."""


def require(condition, message):
    if not condition:
        raise ViewError(message)


def number(value):
    require(type(value) in (int, float), "rates and display scale must be numeric")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ViewError("number outside finite range") from exc
    require(math.isfinite(result) and result >= 0, "finite nonnegative rate required")
    return result


def ordered_cells():
    for split in ("train", "val"):
        for segment in range(6):
            for eye in range(2):
                for direction in (0, 180):
                    yield (f"{split}-segment{segment}-eye{eye}-direction{direction}",
                           split, segment, bool(eye), direction)


def validate_observation(observation):
    """Check the complete observation, including cells not selected for display.

    This is consistency validation, not authentication of independent source
    provenance. The operator must first build and bind the observation packet.
    """
    require(type(observation) is dict and observation.get("schema") == SCHEMA,
            "matched observation schema required")
    require(type(observation.get("phase_bins")) is int
            and observation["phase_bins"] == 20, "all 20 phase bins required")
    units = observation.get("unit_ids")
    require(type(units) is list and len(units) == 54
            and all(type(unit) is int and -(2**63) <= unit < 2**63 for unit in units)
            and len(set(units)) == 54, "all 54 unique integer source units required")
    scale = number(observation.get("display_rate_max_hz"))
    require(scale > 0, "positive common display scale required")
    cells = observation.get("cells")
    require(type(cells) is list and len(cells) == 48, "all 48 support cells required")
    totals = {"train": 0, "val": 0}
    maximum = 0.0
    for cell, expected in zip(cells, ordered_cells()):
        require(type(cell) is dict and CELL_KEYS <= set(cell)
                and set(cell) <= CELL_KEYS | OPTIONAL_CELL_KEYS,
                "only declared observation cell fields are allowed")
        key, split, segment, eye, direction = expected
        require(cell["cell_id"] == key and type(cell["cell_id"]) is str
                and cell["source_split"] == split and type(cell["source_split"]) is str
                and type(cell["observation_segment"]) is int
                and cell["observation_segment"] == segment
                and type(cell["is_eye"]) is bool and cell["is_eye"] is eye
                and type(cell["theta"]) is int and cell["theta"] == direction,
                "cell identity or canonical order mismatch")
        missing = []
        for prior in ("long", "short"):
            count = cell["n_" + prior]
            require(type(count) is int and 0 <= count <= 204, "invalid cell trial count")
            totals[split] += count
            matrix = cell[prior + "_rate_hz"]
            if count == 0:
                require(matrix is None, "absent prior must be null, never a zero matrix")
                missing.append(prior)
                continue
            require(type(matrix) is list and len(matrix) == 54,
                    "all unit rows must be visible")
            for row in matrix:
                require(type(row) is list and len(row) == 20, "all phase bins must be visible")
                for value in row:
                    rate = number(value)
                    require(rate <= scale, "display clipping is forbidden")
                    maximum = max(maximum, rate)
        if "supported" in cell:
            require(type(cell["supported"]) is bool and cell["supported"] is (not missing),
                    "support flag disagrees with prior counts")
        if "missing_priors" in cell:
            require(cell["missing_priors"] == missing, "missing-prior declaration disagrees")
    require(totals == {"train": 150, "val": 54}, "complete original split counts required")
    require(scale == (maximum if maximum > 0 else 1.0),
            "display scale must be the complete packet maximum (or 1 Hz for all zero)")
    return cells, units, scale


def color(rate, scale):
    """White at zero, blue at the shared maximum; 256 display intensities."""
    shade = round(255 * (1.0 - rate / scale))
    return f"#{shade:02x}{shade:02x}ff"


def text(x, y, content, *, size=12, anchor="start", **attributes):
    extra = "".join(f' {key.replace("_", "-")}="{escape(str(value))}"'
                    for key, value in attributes.items())
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"'
            f'{extra}>{escape(str(content))}</text>')


def render_cell(observation, cell_id):
    """Return one typed cell's paired observation panels as UTF-8 SVG bytes."""
    require(type(cell_id) is str, "cell selection must be an exact string ID")
    cells, units, scale = validate_observation(observation)
    selected = [cell for cell in cells if cell["cell_id"] == cell_id]
    require(len(selected) == 1, "unknown observation cell")
    cell = selected[0]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"'
           f' viewBox="0 0 {WIDTH} {HEIGHT}" role="img">',
           '<title>NEURAL-096 prior-specific mean-rate observations</title>',
           '<desc>All 54 source units and 20 phase bins. Same scale for both priors and all cells. '
           'No difference, reference summary, confidence interval or significance conclusion is displayed.</desc>',
           '<rect width="100%" height="100%" fill="white"/>',
           '<defs><linearGradient id="rate-scale"><stop offset="0%" stop-color="#ffffff"/>'
           '<stop offset="100%" stop-color="#0000ff"/></linearGradient></defs>',
           '<g font-family="sans-serif" fill="#111">',
           text(24, 30, "NEURAL-096: prior-specific mean-rate observations", size=21),
           text(24, 55, f'{cell["source_split"]}; recording segment {cell["observation_segment"]}; '
                f'{"eye" if cell["is_eye"] else "hand"}; direction {cell["theta"]} degrees', size=15),
           text(24, 79, "Equal-trial mean of count / actual bin exposure; Hz (spikes/s/source unit)."),
           text(24, 100, "Recording segments are observation support, not verified randomized blocks."),
           text(24, 1165, "Finite display and color precision limit numerical estimates.", size=12)]
    for prior, left in zip(("long", "short"), PANEL_LEFTS):
        matrix = cell[prior + "_rate_hz"]
        count = cell["n_" + prior]
        out.append(f'<g id="{prior}-panel" data-scale-min="0" data-scale-max="{scale:.17g}">')
        out.append(text(left + 240, 132, f"{prior.capitalize()} prior — n = {count}", size=17, anchor="middle"))
        for unit_index, unit_id in enumerate(units):
            top = PANEL_TOP + unit_index * CELL_HEIGHT
            out.append(text(left - 8, top + 12, unit_id, size=10, anchor="end",
                            data_unit_id=unit_id))
            if matrix is not None:
                for phase, rate in enumerate(matrix[unit_index]):
                    out.append(f'<rect class="rate" data-unit="{unit_index}" data-bin="{phase}"'
                               f' x="{left + phase * CELL_WIDTH}" y="{top}"'
                               f' width="{CELL_WIDTH}" height="{CELL_HEIGHT}"'
                               f' fill="{color(float(rate), scale)}"/>')
        if matrix is None:
            out.append(f'<rect x="{left}" y="{PANEL_TOP}" width="480" height="864" fill="#eee"/>')
        for phase in range(21):
            x = left + phase * CELL_WIDTH
            quarter = phase % 5 == 0
            out.append(f'<line x1="{x}" x2="{x}" y1="{PANEL_TOP}" y2="1016"'
                       f' stroke="{"#555" if quarter else "#ddd"}" stroke-width="{1.5 if quarter else 0.25}"/>')
        if matrix is None:
            # Keep the missing-support annotation above the grid and give it an
            # opaque background so lines cannot cross the text.
            out.append(f'<rect x="{left + 8}" y="518" width="464" height="32" fill="#eee"/>')
            out.append(text(left + 240, 540, "UNSUPPORTED: no trials for this prior", anchor="middle", size=14))
        for phase in range(20):
            out.append(text(left + (phase + 0.5) * CELL_WIDTH, 1034, phase + 1, size=10, anchor="middle"))
        for quarter in range(4):
            out.append(text(left + (quarter * 5 + 2.5) * CELL_WIDTH, 1055,
                            f"Q{quarter + 1}", size=12, anchor="middle"))
        out.append(text(left + 240, 1076, "20 phase bins spanning the complete observed Set–Go interval", anchor="middle", size=11))
        out.append('</g>')
    out.append(text(24, 1101, f"Common display scale: 0 to {scale:.6g} Hz. White = 0; blue = maximum.", size=12))
    out.append('<rect x="24" y="1115" width="320" height="12" fill="url(#rate-scale)" stroke="#555"/>')
    for tick in range(5):
        x = 24 + 80 * tick
        out.append(f'<line x1="{x}" x2="{x}" y1="1127" y2="1131" stroke="#555"/>')
        out.append(text(x, 1144, f"{scale * (tick / 4):.6g}", size=10, anchor="middle"))
    out.append('</g></svg>')
    body = "\n".join(out).encode("utf-8")
    require(len(body) <= MAX_SVG_BYTES, "rendered observation exceeds byte bound")
    return body
