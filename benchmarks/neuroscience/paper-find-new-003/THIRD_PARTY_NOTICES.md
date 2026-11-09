# BANC source attribution and licence notices

This supplement accompanies the complete BANC benchmark source for `PAPER-FIND-NEW-003`. It identifies the terms and provenance of copied material and source-derived helpers. It does not replace upstream terms with the repository's MIT licence, grant rights owned by others, imply author endorsement, or certify scientific or runtime readiness.

[SOURCE_ATTRIBUTIONS.json](SOURCE_ATTRIBUTIONS.json) maps every one of the 131 original public paths to its exact bytes, source relationship and relevant component. All original files, headers, notices and path names are unchanged. The 128 operative bodies, the two source-binding files and canonical manifest remain exact. Licence documents are siblings of `complete-banc-v1`, so the scientific source manifests, loader membership and dependency guards retain their original meaning.

## BANC-project — CC BY 4.0 declaration

Source: [htem/BANC-project at 2e78ce38e946ab80e120a42f504a019b3a567fef](https://github.com/htem/BANC-project/tree/2e78ce38e946ab80e120a42f504a019b3a567fef), accompanying *Distributed control circuits across a brain-and-cord connectome*. The exact [retained README](complete-banc-v1/runtime/source/primary-source/README.md) states that the code is released under CC BY 4.0. Its linked `LICENSE` at that pinned commit returned HTTP 404 in the captured GitHub API request. That observation is distinct from earlier TLS failures and cache misses, which established neither an HTTP status nor the licence contents.

The complete [Attribution 4.0 International legal text](LICENSES/CC-BY-4.0-creativecommons.txt) is an exact copy from [Creative Commons' canonical legalcode.txt](https://creativecommons.org/licenses/by/4.0/legalcode.txt). It is supplied as the terms named by the README; it is **not** labelled as a recovered BANC repository `LICENSE` file.

The README credits first authors Alexander S. Bates, Jasper S. Phelps, Minsu Kim and Helen H. Yang; corresponding authors Mala Murthy, Jan Drugowitsch, Rachel I. Wilson and Wei-Chung Allen Lee. It states that Alexander Shakeel Bates led the codebase in Rachel Wilson's lab, working with Wei-Chung Allen Lee, with help from Helen Yang, Jasper Phelps, Mo Osman and Tatsuo Okubo. Its artwork credits to Amy Sterling and Tyler Sloan are preserved in the exact README; the linked artwork image bodies are not included in this source selection. The full author list and acknowledgements remain linked from the upstream README and paper.

The forty selected files under `complete-banc-v1/runtime/source/primary-source/` are exact upstream copies. Two additional exact duplicates are:

- `complete-banc-v1/runtime/legacy/banc_composition/_primary/banc-functions.R`, from `R/startup/banc-functions.R`.
- `complete-banc-v1/runtime/legacy/banc_composition/_primary/panels_cns_network_analyses.R`, from `R/figures/panels_cns_network_analyses.R`.

`complete-banc-v1/runtime/source/captured-functions/calculate_influence_norms.R` extracts the complete function at original lines 224–307 of `R/startup/banc-functions.R`. Its 3,342 bytes match the original contiguous source block exactly. The change is the extraction and standalone location; the function's internal bytes are unchanged. Separately identified Python ports, consumers and adapters are benchmark-authored adaptations of the cited source, not unmodified upstream files. Their changes and scientific source ranges are listed per file in the attribution map. No new copyright owner or year is invented for BANC material.

## ConnectomeInfluenceCalculator — BSD 3-Clause

Source: [DrugowitschLab/ConnectomeInfluenceCalculator at 6b70294094ebcd97166ab646c5322eed957f8936](https://github.com/DrugowitschLab/ConnectomeInfluenceCalculator/tree/6b70294094ebcd97166ab646c5322eed957f8936).

**Copyright (c) 2025, Drugowitsch Lab.** The original package metadata names Zaki AJABI and Jan DRUGOWITSCH as authors. The full original copyright, conditions and disclaimer are retained without whitespace changes in [ConnectomeInfluenceCalculator-BSD-3-Clause.txt](LICENSES/ConnectomeInfluenceCalculator-BSD-3-Clause.txt), recovered from the pinned upstream `LICENSE.txt`, Git blob `86ef909b7aef073bac3f94dee22ff01aeb6710dc`.

This notice applies to the three exact selected files under `complete-banc-v1/runtime/source/native-source/DrugowitschLab_ConnectomeInfluenceCalculator/`: `InfluenceCalculator/InfluenceCalculator.py`, `README.md` and `pyproject.toml`. They are unchanged. Benchmark execution wrappers are distinct from these original bodies. The original non-endorsement and warranty terms are retained in full.

## influencer — GNU General Public License version 3

Source: [natverse/influencer at 2519c57b8389481e72bc52e93a9e45e770cd674a](https://github.com/natverse/influencer/tree/2519c57b8389481e72bc52e93a9e45e770cd674a). Its [exact DESCRIPTION](complete-banc-v1/runtime/source/native-source/natverse_influencer/DESCRIPTION) names Alexander Bates as author and maintainer and declares `License: GPL-3`.

The full original upstream `LICENSE.md` is preserved exactly as [influencer-GPL-3.0.md](LICENSES/influencer-GPL-3.0.md), Git blob `175443ce8855883fcbf0122a6bfba12ac4cfb49d`. The Free Software Foundation copyright statement inside that document concerns the licence text; it is not substituted for the package author's identity.

The four exact selected files are `DESCRIPTION`, `R/influence-calculator-r.R`, `R/python-wrapper.R` and `R/utils.R` beneath `complete-banc-v1/runtime/source/native-source/natverse_influencer/`. All bodies and existing notices are unchanged. `DESCRIPTION` restores the original filename from an exact text transport alias; that restoration does not modify its contents. The selected source files are distributed as source, with the full upstream repository linked for its remaining package and dependency context. This package does not claim that all upstream dependencies or a complete installed R/PETSc/SLEPc environment are bundled.

## Older bancpipeline-derived helpers — separate provenance

The six older helper paths identified in the attribution map derive from [htem/bancpipeline at 65adfc22458b6084830c71f40e8c71c26414609e](https://github.com/htem/bancpipeline/tree/65adfc22458b6084830c71f40e8c71c26414609e). Its exact [pinned README licence section](https://github.com/htem/bancpipeline/blob/65adfc22458b6084830c71f40e8c71c26414609e/README.md#license) declares GPL-3 and links `LICENSE`. The complete original [bancpipeline GPLv3 LICENSE](LICENSES/bancpipeline-GPL-3.0.txt) is included byte-for-byte, with Git blob `94a9ed024d3859793618152ea559a168bbcbb5e2`. The independently recovered README has Git blob `e85c74f645fe6102a713ddea3da39bbac65d9b87`; it is grant/context evidence, not itself a licence text. Both exact source requests returned HTTP 200. The original capture's generic `decoded_verified_licence` label and `.licence.txt` filename for the README are preserved in the private capture but corrected in this source-role description.

The README states that Alexander Shakeel Bates led the codebase in Rachel Wilson's lab, working with Wei-Chung Allen Lee; the BANC consortium developed it under the Wilson Lab (HMS) and Lee Lab (Princeton/htem), with contributions from the FlyWire and CAVE teams. Existing acknowledgements remain linked from that exact README. The GPL text's Free Software Foundation notice refers to the licence document, not an invented program copyright owner.

**Modified source notice, issued 2026-11-09:** the six paths are adaptations or a duplicate of an adaptation, not unmodified upstream source. They comprise graph preparation, affinity preparation, Python community, R community and portable centrality, including the exact centrality duplicate under `runtime/banc_graph_core/`. The per-file attribution map names every path and original source range. The R helper wraps literal clustering and naming blocks in a caller-input function, removes startup/SeaTable/file/publication operations, and adds explicit source/runtime/shape/label guards. The Python helpers expose typed preparation and source-specific algorithm/consumer interfaces with explicit failure and resource boundaries. These source-derived helpers retain the applicable GPL-3 terms; original benchmark MIT terms do not replace those terms. This is the date of the additive change notice; the exact dates of earlier adaptations are not reconstructed here, and this supplement changes none of their source bytes.

Retained [Zenodo metadata](https://zenodo.org/records/20350572) associates the older source with `v2.0.5` and declares `gpl-3.0`. Its archive-to-tree byte equivalence remains unverified. The new exact pinned README and LICENSE evidence resolves the source-grant prerequisite without claiming that archive equivalence. Neither the current BANC-project CC declaration nor the natverse GPL file is substituted for the older project's own grant.

## Original benchmark material and dependency boundary

[Brain-Researcher-MIT.txt](LICENSES/Brain-Researcher-MIT.txt) preserves the repository's exact MIT notice, **Copyright (c) 2026 Brain Researcher**, for original benchmark contributions. It does not supersede the terms or notices of copied or derived third-party expression. The per-file map distinguishes original contracts, control and execution adapters, ports, exact upstream files, duplicates and the extracted function. Scientific use of an algorithm, a public formula or an external package name is described as provenance; this notice makes no blanket relicensing determination about a mixed work.

This is a scoped source-notice package, not a legal guarantee. All original runtime and scientific gates remain open. Nothing here asserts reproduction, numerical parity, model performance, novel results, an installed interface or permission to publish private build history. See [SOURCE_PUBLICATION.md](SOURCE_PUBLICATION.md) and the unchanged [operator documentation](complete-banc-v1/OPERATOR.md).
