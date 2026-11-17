# DANDI version-notice supplement

Both exact versioned DANDI metadata endpoints returned HTTP 200 on 15 November 2026 and declare open access with license `spdx:CC-BY-4.0`. This supplies the previously missing primary version-level notice observations for the existing 99-recording provenance chain. The main provisioning source package and its earlier review remain unchanged.

| Dandiset/version | Dataset title | Declared access/license | Metadata summary |
|---|---|---|---|
| [000473 / 0.230417.1502](https://api.dandiarchive.org/api/dandisets/000473/versions/0.230417.1502/) | Esr1+ hypothalamic-habenula neurons shape aversive states. | OpenAccess / CC-BY-4.0 | 25 files; 25 subjects |
| [001260 / 0.250911.0744](https://api.dandiarchive.org/api/dandisets/001260/versions/0.250911.0744/) | A Prefrontal Cortex Map based on Single Neuron Activity | OpenAccess / CC-BY-4.0 | 74 files; 43 subjects |

The file totals agree with the already accepted 25+74 recording-metadata provenance split. These aggregate metadata observations do not independently redo the individual recording/animal joins or establish cross-dataset uniqueness. No NWB, asset-content URL, manifest URL or scientific payload was fetched.

Retain the publisher-supplied version citations with an authorized release:

- Calvigioni, Daniela; Fuzik, Janos; Le Merre, Pierre; Slashcheva, Marina; Jung, Felix; Ortiz, Cantin; Lentini, Antonio; Csillag, Veronika; Graziano, Marta; Nikolakopoulou, Ifigeneia; Weglage, Moritz; Lazaridis, Iakovos; Kim, Hoseok; Lenzi, Irene; Park, Hyunsoo; Reinius, Björn; Carlén, Marie; Meletis, Konstantinos (2023) Esr1+ hypothalamic-habenula neurons shape aversive states (Version 0.230417.1502) [Data set]. DANDI archive. https://doi.org/10.48324/dandi.000473/0.230417.1502

- Le Merre, Pierre; Heining, Katharina; Slashcheva, Marina; Jung, Felix; Moysiadou, Eleni; Guyon, Nicolas; Yahya, Ram; Park, Hyunsoo; Wernstal, Fredrik; Carlén, Marie (2025) A Prefrontal Cortex Map based on Single Neuron Activity (Version 0.250911.0744) [Data set]. DANDI Archive. https://doi.org/10.48324/dandi.001260/0.250911.0744

The source code keeps its separate full BSD-2 notice and the paper its own CC BY 4.0 notice. The DANDI declarations are direct record-level observations; they are not a blanket legal assurance for every derived artifact or container image. No author contact, license reinterpretation, public upload or new execution selection occurred.

Exactly two GETs were attempted, one per selected endpoint, without redirects or retries. Each had a 20-second whole-request deadline and a 128 KiB combined observed-header/body limit. The two complete bodies total 13,221 bytes; their captures with serialized observed headers total 15,315 bytes. Header serialization is explicitly not original TLS/wire-byte accounting. Complete bodies were subsequently parsed with duplicate-key/nonfinite refusal and checked against their retained hashes, exact version identities and declared license/access fields.

The exact body/header captures, complete observation record and original tool request/result remain external. Contributor emails and unrelated metadata are not copied into this authored supplement. This supplement adds attribution facts only; it neither audits nor releases the authentic participant packet, and it changes no benchmark count.
