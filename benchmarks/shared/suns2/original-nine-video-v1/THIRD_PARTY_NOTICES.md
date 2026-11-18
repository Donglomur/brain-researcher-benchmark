# Source provenance and retained notices

`suns2_benchmark/literal_assignment.py` is a Python control-flow translation of the released `ANE/eval_func/Hungarian.m`. The upstream file credits **Alex Melin, 30 June 2006**. It belongs to the [SUNS2-ANE paper reproduction repository](https://github.com/YijunBao/SUNS2_ANE_paper_reproduction).

The exact author notice in the source header is:

> Written by: Alex Melin 30 June 2006

The qualified translation remains byte-identical: `suns2_benchmark/literal_assignment.py`, 7,216 bytes, SHA256 `58c028e7621f17c6284872315a6b8639ff2b4b0aa571186195499745e6ef16d6`. The accepted saved-author control used that identity; this provenance addition changes no implementation.

The selected official-code revision is `128eb4738e026b89a341a6013e7bd7b6dc7c3216` (v1.2.0). Its [Hungarian.m source](https://github.com/YijunBao/SUNS2_ANE_paper_reproduction/blob/128eb4738e026b89a341a6013e7bd7b6dc7c3216/ANE/eval_func/Hungarian.m) has Git blob identity `c67edcd4091f00c70f7dbf84959bffc960c16fb0`, 9,049 bytes and SHA256 `1d83ec20881144f6ad3839ccc0ea00bcd4a805eae3d67c0a18713e37fa516241`. The retained v1.1 file has the same blob identity. Keep the version distinction for the rest of the method and its execution wrappers.

The upstream repository's root license is the GNU General Public License, version 2, June 1991. Its text is retained verbatim in [LICENSES/SUNS2-upstream-GPL-2.0.txt](LICENSES/SUNS2-upstream-GPL-2.0.txt): Git blob `15f75cf7d51a7f1de0d816c0d80153f92b429009`, 18,072 bytes, SHA256 `b90ed8150a6d371c84b7dbaa680cd0e9893ef7c2558765e1e00930513efcfe3b`. Preserve this source attribution and license material when integrating the translated component.

The translation preserves the inspected assignment control flow, including its ordering behavior; the separate order-invariant audit is a declared benchmark extension. Qualified saved-author output agreement does not establish native MATLAB equivalence or retraining reproduction.

The official method-code bank is a separately pinned material collection with its own source/license allowlist. Third-party numerical libraries, data and paper artifacts retain their respective provenance and terms; this notice records the translated component's source and does not relicense those materials.

For repository integration, list this translated component explicitly in the root attribution/license exceptions. Preserve its upstream GPL version 2 material and notices; do not apply a generic MIT label to this derivative or infer an “or later” grant from the generic GPL text. This records the scoped source materials without relicensing unrelated code.
