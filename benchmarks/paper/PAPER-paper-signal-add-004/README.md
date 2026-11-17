# osl-dynamics, a toolbox for modeling fast dynamic brain activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-004`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19762 bytes; SHA-256 `d65de0882c3297ec0ae2479ded38cdb17ddc5e6ee8d7d72262bbbb1150772bdd`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Latent state programme](implementations/latent-state-programme) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Delivery](contracts/delivery) — Task contract.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/OHBA-analysis/osl-dynamics)
- [Paper](https://elifesciences.org/articles/91949)
- [Source](https://osf.io/download/7qv9r/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
