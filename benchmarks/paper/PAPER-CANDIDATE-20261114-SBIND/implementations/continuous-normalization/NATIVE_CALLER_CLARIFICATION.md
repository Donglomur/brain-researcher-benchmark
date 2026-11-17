# Mandatory native-caller compatibility clarification

The new streams are an owner preparation interface, not direct inputs to the
unchanged upstream trainer. In the pinned `SBINDTrainer.predict`, the initial
sample batch is inspected as `sample_batch["z"].shape` to infer behavior output
width, although subsequent model calls receive only neural `y` and `x_init`.
Our validation/test participant streams omit behavior values and therefore do
not directly satisfy that trainer API. Do not restore compatibility by exposing
held labels.

A separately reviewed native adapter must derive output width from the admitted
complete channel metadata, or supply an explicitly non-target placeholder of the
required shape. It must still enforce per-trial recurrent resets, full frame and
remainder coverage, output identity joins, appropriate training/validation
visibility and the external owner/participant boundary. This source phase adds
neither that adapter nor an actual native call. The existing prediction API also
does not establish the unresolved SVD fit provenance, runtime or original-paper
fidelity. All earlier qualification holds remain.
