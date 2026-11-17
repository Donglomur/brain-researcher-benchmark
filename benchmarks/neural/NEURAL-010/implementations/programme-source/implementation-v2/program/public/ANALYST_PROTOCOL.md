# Complete seizure-monitoring numerical reconstruction

The normative public design documents accompany this protocol. They specify
the original event arithmetic, every required row and the two reports. This
protocol contains no realized detector configuration, authentic recording ID,
sample, annotation, prediction, metric or expected numerical answer.

Return a final JSON object with exactly `python_source`, whose value is a full
Python program. The program is invoked once with:

`python -I -B PROGRAM --request ABSOLUTE_REQUEST --output ABSOLUTE_OUTPUT`

The request has schema `neural010-complete-context-request-v1`, task_id
`NEURAL-010`, context, source, envelope, view_manifest, historical_packet,
matched_packet and output_contract. The context contains id, mode, replication,
view and fixed_author. Every descriptor contains path, bytes and sha256. Read
the exact referenced JSON bytes. All data and public code are readonly; only
the fresh `/work` directory is writable. The full-waveform view provides every
recording's signal descriptor in its view manifest. The waveform-withheld view
provides none. Historical packet signal descriptors still exist as provenance
in both views and do not override the permitted mount list.

Write one JSON submission with exactly:

- schema: `neural010-complete-context-submission-v1`
- task_id: `NEURAL-010`
- context, source, envelope, view_manifest: exact values from the request
- historical_submission: schema_version1, task_id, input_sha256 equal to the
  historical packet SHA, and the full original historical report
- matched_submission: schema_version1, task_id, historical_packet_sha256,
  input_sha256 equal to the matched packet SHA, and the full matched report

All 686 recordings, 23 biological people, every montage membership, undefined
metric and empty localization list remain represented. Use the public original
event arithmetic. The historical primary is maximum scaled numerical
reconstruction error; the matched diagnostic is separate. The required false
claims flags remain false. Numerical reconstruction accuracy does not establish
causality, neural waveform understanding, clinical utility or new detector
performance. No private expected report or grader is available.

Data-free fixed authoring receives only these source documents and public code.
Its source is frozen before any real study data is opened. The same source is
then executed independently under both views. Adaptive episodes may inspect
their one released view and run Python tools before returning their final
source. Only that source is carried into the fresh final execution; tool-created
files are not implicitly carried. Tool episodes may carry their own complete
ordinary workspace artifacts between calls. Other contexts, reference-fitting
state, expected reports and provider credentials are never mounted.

For each mode/view, the authoring and final execution limits are preselected
separately and held equal across compared conditions. Fixed author cost is
counted once per replication and allocated half to each view, alongside both
views' same permitted author ceiling. Identical requested seeds do not prove
deterministic provider behavior.
