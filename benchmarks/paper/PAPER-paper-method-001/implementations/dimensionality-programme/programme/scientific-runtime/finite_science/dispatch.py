"""In-memory scientific operation dispatch. No science is invoked on import."""
from .common import ScientificGate,result,require

def execute(operation: str, payload: dict) -> dict:
    try:
        require(isinstance(payload,dict) and set(payload)=={'arrays','protocol','request','lineage'},'exact payload envelope')
        require(all(isinstance(payload[k],dict) for k in payload),'mapping envelope fields')
        if operation=='moments.direct':
            from .direct import compute
            return compute(payload)
        if operation=='moments.optimized':
            from .lattice import compute
            return compute(payload)
        if operation=='finite.population':
            from .geometry import population
            return population(payload)
        if operation=='local.select':
            from .geometry import local
            return local(payload)
        if operation=='reference.bundle':
            from .bundle import execute as bundle
            return bundle(payload)
        if operation=='reference.fit':
            from .fitting import fit
            return fit(payload)
        if operation=='uncertainty.residual_fit':
            from .fitting import residual_fit
            return residual_fit(payload)
        if operation=='preparation.stringer_source':
            from .geometry import stringer_source
            return stringer_source(payload)
        if operation=='reference.point':
            from .references import point
            return point(payload)
        if operation=='reference.literal':
            from .literal import execute as literal
            return literal(payload)
        if operation=='uncertainty.sets':
            from .uncertainty import sets
            return sets(payload)
        if operation=='uncertainty.resample':
            from .uncertainty import resample
            return resample(payload)
        if operation=='generator.world':
            from .generators import world
            return world(payload)
        if operation=='preparation.transform':
            from .geometry import transform
            return transform(payload)
        if operation=='score.uncertainty_quality':
            from .scoring import uncertainty_quality
            return uncertainty_quality(payload)
        if operation=='score.mandatory_pairwise':
            from .pairwise import execute as pairwise
            return pairwise(payload)
        if operation=='score.support':
            from .scoring import support_classification
            return support_classification(payload)
        if operation=='score.legacy76_validate':
            from .legacy import candidate
            return candidate(payload)
        if operation=='score.legacy76':
            from .legacy import score
            return score(payload)
        if operation=='score.point':
            from .scoring import point
            return point(payload)
        if operation=='score.interval':
            from .scoring import interval
            return interval(payload)
        if operation=='score.select_participant':
            from .participant_selection import select
            return select(payload)
        if operation=='score.select_point':
            from .scoring import select_point
            return select_point(payload)
        if operation=='score.select_uncertainty':
            from .scoring import select_uncertainty
            return select_uncertainty(payload)
        if operation=='score.paired':
            from .scoring import paired
            return paired(payload)
        if operation=='score.access_effect':
            from .scoring import access_effect
            return access_effect(payload)
        if operation=='score.reproduction':
            from .scoring import reproduction
            return reproduction(payload)
        if operation=='aggregate.transfer':
            from .scoring import transfer
            return transfer(payload)
        if operation=='aggregate.majaj_curves':
            from .majaj import aggregate
            return aggregate(payload)
        if operation=='aggregate.curves':
            from .scoring import curves
            return curves(payload)
        raise ScientificGate('invalid_protocol','unknown scientific operation')
    except ScientificGate as error:
        return result(status=error.status,support=error.support,diagnostics={'reason':str(error)})
    # Unexpected implementation/dependency failures propagate to actual worker;
    # they are not converted into a scientific success or erased by retry.
