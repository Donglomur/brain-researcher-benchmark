# NEURAL-025: source-declared joint geometry

This note records the author loader's 24-column convention and the separate Figure 5 inverse-geometry implementation at commit `815b610b3beddfed5a3abf611d3a465ab9e4ce5c`. It does **not** establish which code, calibration or sign convention generated the stored `R.jointAngles` arrays. Keep their original column ordinals and the explicit unverified native provenance.

The [loader assigns the labels](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/utils/loadData.m#L91-L93), and the [candidate inverse function packs the corresponding outputs](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/inverseKinematics_PD_vAF.m#L127-L129). The [actual event-locking route](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/eventLockKinematics.m#L173-L179) uses stored `R(tr).jointAngles` when present; otherwise it calls the differently named `getInverseKinematics(posXYZ)`. No alias between that missing helper and `inverseKinematics_PD_vAF` is established.

## Coordinates and units

The candidate accepts time × XYZ × marker pose data. Its first 15 marker roles are author digits 1–4 terminal tips, digits 1–4 PIP landmarks, digits 1–4 MCP landmarks, wrist (13), elbow (14) and shoulder (15). The paper identifies the shoulder landmark as the proximal tip of the right humeral lesser tubercle. Preserve the author's digit numbering; a complete identity map for all 25 native pose markers remains unverified. The paper alternates fingertip and DIP terminology for the terminal segment, so these should not silently become interchangeable anatomical landmarks.

Angles in the candidate are **degrees**, supported by `atan2d`/`acosd` and the [Rodrigues helper's degree default](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/rodriguesRot.m#L5-L14). Computation successively neutralizes the pose; formulas are not all measurements of the initial global coordinates. The removal order matters and differs from the output-column order. Numerical X/Y/Z axes alone do not supply the physical camera-to-world transform.

The paper describes two-camera stereo calibration, but these text sources do not establish per-session numeric intrinsics, extrinsics, world origin/handedness, neutral-pose offsets or the calibration identity used for the stored arrays. See [versioned paper methods](https://doi.org/10.7554/eLife.106270.3), sections s4-6 through s4-8.

## Source-declared column map

Indices below are one-based. All units and coordinate stages describe the candidate geometry; none is a certification of native-array anatomy. “MC” means metacarpal. MCP denotes the metacarpophalangeal joint.

| Column | Loader label | Candidate meaning | Coordinate stage |
| --- | --- | --- | --- |
| 1 | `SHDRf` | Shoulder flexion/extension | after shoulder ab/adduction |
| 2 | `SHDRa` | Shoulder abduction/adduction | first shoulder operation |
| 3 | `SHDRr` | Shoulder internal/external rotation | after shoulder ab/adduction and flexion |
| 4 | `ELBOf` | Elbow flexion | after shoulder neutralization |
| 5 | `WRSTf` | Wrist flexion/extension | after wrist deviation |
| 6 | `WRSTd` | Wrist radial/ulnar deviation, called abd/add by candidate | first wrist operation, after elbow |
| 7 | `WRSTr` | Wrist rotation / forearm pronation-supination intent | after wrist deviation and flexion |
| 8 | `MCP1f` | Digit 1 MCP flexion/extension | after digit MCP ab/adduction; temporary MC splay removal |
| 9 | `MCP2f` | Digit 2 MCP flexion/extension | after digit MCP ab/adduction; temporary MC splay removal |
| 10 | `MCP3f` | Digit 3 MCP flexion/extension | after digit MCP ab/adduction; temporary MC splay removal |
| 11 | `MCP4f` | Digit 4 MCP flexion/extension | after digit MCP ab/adduction; temporary MC splay removal |
| 12 | `MCP1a` | Digit 1 MCP abduction/adduction | after proximal joints and opposition; temporary MC splay removal |
| 13 | `MCP2a` | Digit 2 MCP abduction/adduction | after proximal joints and opposition; temporary MC splay removal |
| 14 | `MCP3a` | Digit 3 MCP abduction/adduction | after proximal joints and opposition; temporary MC splay removal |
| 15 | `MCP4a` | Digit 4 MCP abduction/adduction | after proximal joints and opposition; temporary MC splay removal |
| 16 | `MCP1o` | Metacarpal 1 opposition | after wrist, before MCP |
| 17 | `MCP4o` | Metacarpal 4 opposition | after wrist and MC1 opposition, before MCP |
| 18 | `P1P2` | Adjacent metacarpal 1-2 splay: unsigned three-dimensional angle | after MCP; computed before cumulative splay neutralization |
| 19 | `P2P3` | Adjacent metacarpal 2-3 splay: unsigned three-dimensional angle | after MCP; computed before cumulative splay neutralization |
| 20 | `P3P4` | Adjacent metacarpal 3-4 splay: unsigned three-dimensional angle | after MCP; computed before cumulative splay neutralization |
| 21 | `PIP1f` | Digit 1 PIP flexion proxy: unsigned three-dimensional turning angle | after proximal, MCP and splay neutralization |
| 22 | `PIP2f` | Digit 2 PIP flexion proxy: unsigned three-dimensional turning angle | after proximal, MCP and splay neutralization |
| 23 | `PIP3f` | Digit 3 PIP flexion proxy: unsigned three-dimensional turning angle | after proximal, MCP and splay neutralization |
| 24 | `PIP4f` | Digit 4 PIP flexion proxy: unsigned three-dimensional turning angle | after proximal, MCP and splay neutralization |

The operation order is shoulder ab/adduction → shoulder flexion → shoulder rotation → elbow flexion → wrist deviation → wrist flexion → wrist rotation → MC1/MC4 opposition → MCP ab/adduction → MCP flexion → adjacent-MC splay → PIP proxies. All three splay angles are calculated before their cumulative neutralization. The MCP calculations temporarily remove and restore each digit's metacarpal splay.

## Unresolved conventions and native lineage

- `MCP1o`/`MCP4o` describe **metacarpal opposition**, and `P1P2`/`P2P3`/`P3P4` describe **adjacent-metacarpal splay**. Their compact names do not imply additional hinge-flexion targets.
- Candidate splay and PIP measurements use unsigned three-dimensional `acosd` angles. The PIP implementation explicitly treats its measure as an approximation to planar finger flexion; it does not recover a signed hyperextension measure.
- Paper s4-8 paragraph 3 describes splay around Z into XY, while the candidate neutralizes splay around X. The paper also narrates splay before MCP extraction, whereas candidate lines 86–95 compute MCP before splay at lines 106–117. Preserve both discrepancies; numerical impact and equivalence have not been established.
- Candidate line 182 documents a shoulder-rotation sign change dated `231216`. The stored-array generating version is unknown, so a shared channel name cannot certify the sign convention.
- The complete, nontruncated 148-entry tree at the pinned commit contains no path named `getInverseKinematics`, `mergeDLC3R` or `addPosXYZ`. This is a bounded release-tree observation, not proof that those functions never existed in history or on an author's MATLAB path. No exact missing-helper source URL is known.
- Matching label count/order does not establish MATLAB/toolbox numerical parity, upstream calcium preprocessing validity or coverage of all five mice and ten sessions. The current paired route covers one authenticated session with 416 records, 372 retained trials and 44 source exclusions; this note does not expand that coverage or report a model score.

To establish native anatomical identity, obtain the exact generating script/helper version and parameters, marker and column dictionaries, units/sign convention, and calibration/frame identity bound to each source file. Resolve the splay and terminal-landmark wording with that provenance. Do not regenerate or relabel stored targets by assuming the separate Figure 5 function is the missing helper.

## Public source identities

SHA-256 values below identify the inspected source bodies, not executable equivalence or native generation provenance.

| Source at the pinned revision | SHA-256 |
| --- | --- |
| [Loader](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/utils/loadData.m) | `8c99275968fdb287a768e7d2b9a7bdcbf0c0f3720b3494a674f08df97be11260` |
| [Inverse geometry](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/inverseKinematics_PD_vAF.m) | `325cd4789c3d36003f1df9fa14b7c069fbf7fe17791c3ee91b02bd1f9ddf16eb` |
| [Forward reconstruction](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/forwardKinematics_PD_vAF.m) | `0930bade0828d7752db31cf37b033700d9bdb9912fb5e0cd1271e09e6c9025af` |
| [Event-locking branch](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/eventLockKinematics.m) | `d1a2ae135ac812734000b1f83311568547bb3e4c32ac81cfa9865ea428548aa9` |
| [Rodrigues units](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/rodriguesRot.m) | `dbe7ed50ccccbdb14acc9a28839cb15dc85f73b812da1f738a45f030a12e52af` |
| [Displayed coordinate axes](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig3/plots/plotSkeletonEulerAngles.m) | `e35d6fa44ea2b81bd5f421346a661bf253d03adadad6c4fdee655e4acc96961c` |

Primary paper: Grier, Salimian and Kaufman, *Mouse sensorimotor cortex reflects complex kinematic details during reaching and grasping*, version of record, 2026-02-09, DOI [10.7554/eLife.106270.3](https://doi.org/10.7554/eLife.106270.3). The [publisher XML](https://cdn.elifesciences.org/articles/106270/elife-106270-v1.xml) body inspected for these methods has SHA-256 `b1af6eaac2017c1ed85c06cfa65aac6f9492a8d1b2198dbe380fb256183f6175`; its filename is not the article-version identifier.
