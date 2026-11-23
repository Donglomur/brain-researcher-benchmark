# Current construction guidance

A neural task can preserve its original definition while describing source that
has since been implemented. An optional `current_guidance` field in its
`understanding.v1.json` updates existing hold descriptions in the current task.
Each replacement names exactly one existing hold and cites authenticated local
source or review evidence already present in that contract.

```json
{
  "current_guidance": {
    "holds": [
      {
        "id": "scorer",
        "requirement": "Qualify the existing scorer on authenticated complete inputs; participant performance remains untested.",
        "evidence_ids": ["existing-scorer-source"]
      }
    ]
  }
}
```

With this field selected, the current construction action list comes from the
contract's `implementation.missing`. The generator preserves every hold and its
state, all historical bytes, scientific targets, and false admission flags. It
rejects unknown or ambiguous hold IDs and unbound evidence. Contracts without
this optional field retain their existing projection.

The source review must establish that the replacement accurately describes the
available component and remaining work. Validation authenticates the cited bytes;
it cannot establish that the prose is scientifically true, that the component has
run on authentic inputs, or that an AI has succeeded.
