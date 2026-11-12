"""Trusted O04 caller for the released Majaj diagnostic; no automatic activation.

This companion runs only when selected by a future qualified controller. The S3
BUILD_ONLY entry and its complete scientific qualification gates are unchanged.
"""
from .common import require, identity

GROUPS = (("Tito", "V4"), ("Tito", "IT"), ("Chabo", "V4"), ("Chabo", "IT"))


def preparation_jobs(*, input_id, coordinates, provenance, protocol, original_source_sha256,
                     complete_support_sha256, source_qualification_id):
    """All four source-replay groups; no replacement of the final-paper cohort map."""
    require(type(input_id) is str and input_id, "MAJAJ_INPUT_ID")
    require(all(type(x) is str and x for x in
            (original_source_sha256, complete_support_sha256, source_qualification_id)), "MAJAJ_TRUSTED_SOURCE_OPERANDS")
    jobs = []
    for animal, region in GROUPS:
        ident = f"Majaj/released/{animal}/{region}"
        jobs.append({"id": ident, "operator": "O04", "branch": "Majaj",
            "complete_original_support": True, "original_source_sha256": original_source_sha256,
            "complete_support_sha256": complete_support_sha256,
            "source_qualification_id": source_qualification_id, "transform_kind": "identity_alignment",
            "operation": "preparation.transform", "inputs": {"responses": input_id},
            "protocol": {**protocol, "coordinate_mapping_sha256": identity(coordinates),
                         "assembly_provenance_sha256": identity(provenance)},
            "parameters": {"operation": "majaj_producer", "coordinates": coordinates,
                           "provenance": provenance, "group": [animal, region]},
            "output_bindings": {"result/outputs/" + k: ident + "/" + k
                                for k in ("trials", "stimulus_ids", "presentation_indices")}})
    return jobs


class ReleasedMajaj:
    """Actual Preparation.run -> Science.invoke -> trusted aggregate composition.

    The only supplied plan is fixed metadata from the source compiler, checked
    again by every numerical draw/aggregate. Predictions do not select this plan.
    No generated record is silently omitted after a non-ok numerical disposition.
    """
    def __init__(self, preparation, *, jobs, seed):
        require(len(jobs) == 4 and [j["parameters"]["group"] for j in jobs] == [list(g) for g in GROUPS],
                "COMPLETE_MAJAJ_FOUR_GROUPS")
        require(type(seed) is int and 0 <= seed < 2**64, "MAJAJ_EXPLICIT_PROSPECTIVE_SEED")
        self.preparation, self.jobs, self.seed = preparation, jobs, seed
        self.plans, self.original_draws, self.original_aggregates = {}, {}, {}
        self.failed_calls = {}

    def _invoke_retained(self, owner, key, operation, **kwargs):
        # A thrown host/transport error is still an attempted slot, not permission
        # to silently replace a failed draw. Preserve the original exception object.
        owner[key] = {"attempted": True, "returned": False}
        try:
            rec = self.preparation.science.invoke(operation, **kwargs)
        except BaseException as error:
            self.failed_calls[key] = error
            owner[key]["error_type"] = type(error).__name__
            owner[key]["error_message"] = str(error)
            raise
        owner[key] = rec
        return rec

    def prepare(self):
        # Exact existing O04/P02 admission, registry ownership and original receipt
        # custody execute unchanged. This is not a substitute preparation mock.
        self.preparation.run(self.jobs, phase="P02", all_I_sealed=False)
        from finite_science.majaj_core import axis_plan
        for job in self.jobs:
            desc = self.preparation.registry[job["output_bindings"]["result/outputs/trials"]]
            shape = desc["shape"]
            require(len(shape) == 3 and shape[0] == 28, "MAJAJ_PREPARED_TRIAL_GEOMETRY")
            for axis in ("Q", "P"):
                self.plans[job["id"], axis] = axis_plan(shape[1], shape[2], job["parameters"]["group"], axis, self.seed)
        return self.plans

    def one_draw(self, group_index, axis, grid_ordinal, draw_ordinal):
        require(type(group_index) is int and 0 <= group_index < 4, "MAJAJ_GROUP_INDEX")
        job = self.jobs[group_index]
        key = (job["id"], axis, grid_ordinal, draw_ordinal)
        require((job["id"], axis) in self.plans and key not in self.original_draws, "MAJAJ_UNPLANNED_OR_REPEATED_DRAW")
        protocol = {**job["protocol"], "source_qualification_id": job["source_qualification_id"]}
        rec = self._invoke_retained(self.original_draws, key, "reference.literal",
            arrays={"trials": self.preparation.registry[job["output_bindings"]["result/outputs/trials"]]},
            protocol=protocol, parameters={"literal_version": "majaj_numpy_released_draw_v1",
                "plan": self.plans[job["id"], axis], "grid_ordinal": grid_ordinal, "draw_ordinal": draw_ordinal},
            lineage={"preparation_id": job["id"], "original_preparation_product": self.preparation.products[job["id"]]["product_sha256"],
                     "axis": axis, "grid_ordinal": grid_ordinal, "draw_ordinal": draw_ordinal},
            namespace="independent_reference")
        # Retain the original failure as well as success; never retry into success.
        self.original_draws[key] = rec
        require(rec["response"]["result"]["status"] == "ok", "MAJAJ_DRAW_CALL_FAILED")
        return rec

    def aggregate(self, group_index, axis):
        require(type(group_index) is int and 0 <= group_index < 4, "MAJAJ_GROUP_INDEX")
        job = self.jobs[group_index]
        key = (job["id"], axis)
        require(key in self.plans and key not in self.original_aggregates, "MAJAJ_AGGREGATE_ALREADY_USED_OR_UNPLANNED")
        expected = [(job["id"], axis, g, d) for g in range(10) for d in range(1000)]
        require(all(k in self.original_draws for k in expected), "MAJAJ_COMPLETE_DRAW_DENOMINATOR")
        originals = [self.original_draws[k] for k in expected]
        require(all("response" in r and r["response"]["result"]["status"] == "ok" for r in originals), "MAJAJ_FAILED_CALL_NOT_DROPPED")
        records = [r["response"]["result"]["outputs"]["draw"] for r in originals]
        rec = self._invoke_retained(self.original_aggregates, key, "aggregate.majaj_curves", arrays={},
            protocol={**job["protocol"], "source_qualification_id": job["source_qualification_id"]},
            parameters={"plan": self.plans[key], "records": records},
            lineage={"preparation_id": job["id"], "axis": axis,
                     "original_draw_products_sha256": identity([r["product_sha256"] for r in originals])},
            namespace="trusted_collection")
        self.original_aggregates[key] = rec
        require(rec["response"]["result"]["status"] == "ok", "MAJAJ_AGGREGATE_FAILED")
        return rec

    def run_released_sweeps(self):
        """Future explicit execution: 4 groups x2 axes x10 ordinals x1000 draws.

        Never invoked during source construction or its tiny engineering controls.
        Shared sampling of a paired draw is inside the fixed numerical source.
        """
        self.prepare()
        for group_index in range(4):
            for axis in ("Q", "P"):
                for g in range(10):
                    for d in range(1000):
                        self.one_draw(group_index, axis, g, d)
                self.aggregate(group_index, axis)
        return self.original_aggregates
