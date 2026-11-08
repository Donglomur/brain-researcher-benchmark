"""Source-confirmed response units; clock units never establish firing-rate units."""
from .strict import need, sha


def require_hz(units):
    need(type(units) is dict and set(units) == {"native_unit", "prepared_unit", "scale", "offset",
         "source_unit_receipt", "packet_target_join_receipt"}, "units", "Complete independently confirmed response-unit provenance required")
    need(units["native_unit"] == units["prepared_unit"] == "Hz"
         and type(units["scale"]) in (int,float) and units["scale"] == 1
         and type(units["offset"]) in (int,float) and units["offset"] == 0,
         "units", "This contract requires source-confirmed Hz and identity response preparation; no inferred per-bin scaling")
    sha(units["source_unit_receipt"]); sha(units["packet_target_join_receipt"])
    return units
