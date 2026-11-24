# Coordinate roster uniqueness

The registered preparation validator now requires each source coordinate index
to occur at most once within each participant/ROI cell. Previously, different
coordinate labels could select the same measured column repeatedly: conversion
indexes the response matrix using every roster row, and the scorer averages
those columns equally. Such aliases silently change the coordinate weighting.
The check occurs before conversion deserializes any original response container.

The scope of uniqueness is participant × ROI × source index. Independently fixed
ROIs may overlap, and the same index can occur for different participants. The
full ten-person, 46-ROI roster, existing coordinate identities, index bounds,
missing-cell dispositions, split, measurement and R² endpoint are unchanged.
No authentic roster or historical identity is rewritten.

Generated controls are in `tests/test_neural070_coordinate_roster.py`. From the
repository root, run `python3 -B tests/test_neural070_coordinate_roster.py`.
The predecessor accepts a complete 461-row roster whose extra row aliases one
of the 460 required cells. The repaired validator rejects it and still admits
distinct source columns, valid cross-ROI/person overlap and the existing index
bounds. Missing cells remain unavailable rather than being dropped.

This is a preparation integrity repair. It supplies no authentic data, direct
observation packet, participant result or scientific qualification. The runtime
remains inactive, and all existing preparation, native execution, reference,
rights, uncertainty and transport qualification gates remain open. Integration
must bind the changed current source and enroll the affected generated control;
historical source descriptors remain historical.
