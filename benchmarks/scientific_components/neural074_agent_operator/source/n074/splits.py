"""Complete declared coverage with global person and task-family exclusions."""
from dataclasses import dataclass
from .contracts import require


@dataclass(frozen=True)
class Fold:
    held_person: str
    held_family: str
    training_people: tuple
    training_endpoints: tuple
    query_endpoints: tuple
    missing_training_cases: tuple
    missing_query_cases: tuple

    @property
    def eligible(self):
        return not self.missing_training_cases and not self.missing_query_cases


def make_fold(population, held_person, held_family, people=None, endpoint_ids=None):
    """A nested fold can only shrink its parent's support, never recover excluded cases."""
    population.validate()
    permitted_people = tuple(population.people if people is None else people)
    permitted_ids = tuple(e.identity for e in population.endpoints) if endpoint_ids is None else tuple(endpoint_ids)
    require(len(set(permitted_people)) == len(permitted_people), 'Duplicate permitted person')
    require(len(set(permitted_ids)) == len(permitted_ids), 'Duplicate permitted endpoint')
    require(set(permitted_people) <= set(population.people), 'Unknown permitted person')
    lookup = {e.identity: e for e in population.endpoints}
    require(set(permitted_ids) <= set(lookup), 'Unknown permitted endpoint')
    require(held_person in permitted_people, 'Held person is outside parent support')
    query = tuple(i for i in permitted_ids if lookup[i].family == held_family)
    require(bool(query), 'Held family is outside parent support')
    train_ids = tuple(i for i in permitted_ids if lookup[i].family != held_family)
    train_people = tuple(p for p in permitted_people if p != held_person)
    require(bool(train_ids) and bool(train_people), 'Empty training support')
    cases = {(c.person, c.endpoint): c for c in population.cases}
    missing_train = tuple((p, i, cases[p, i].status) for p in train_people for i in train_ids if cases[p, i].status != 'present')
    missing_query = tuple((held_person, i, cases[held_person, i].status) for i in query if cases[held_person, i].status != 'present')
    return Fold(held_person, held_family, train_people, train_ids, query, missing_train, missing_query)


def outer_folds(population):
    population.validate()
    families = tuple(dict.fromkeys(e.family for e in population.endpoints))
    return tuple(make_fold(population, p, f) for p in population.people for f in families)


def inner_folds(population, outer):
    lookup = {e.identity: e for e in population.endpoints}
    families = tuple(dict.fromkeys(lookup[i].family for i in outer.training_endpoints))
    require(len(families) >= 2 and len(outer.training_people) >= 2, 'Insufficient grouped support for nested selection')
    return tuple(make_fold(population, p, f, outer.training_people, outer.training_endpoints)
                 for p in outer.training_people for f in families)


def fit_schedule(population, protocol):
    """Describe every selected reference fit before any outcome-dependent work."""
    protocol.validate()
    rows = []
    for outer in outer_folds(population):
        key = (outer.held_person, outer.held_family)
        if not outer.eligible:
            rows.append({'outer': key, 'status': 'ineligible_support', 'fold': outer, 'inner': (), 'fits': 0})
            continue
        inner = inner_folds(population, outer)
        if not all(f.eligible for f in inner):
            rows.append({'outer': key, 'status': 'ineligible_inner_support', 'fold': outer, 'inner': inner, 'fits': 0})
            continue
        # Three separately tuned arms, then one final fit per arm.
        fits = 3 * (len(protocol.configurations) * len(inner) + 1)
        rows.append({'outer': key, 'status': 'planned', 'fold': outer, 'inner': inner, 'fits': fits})
    require(sum(r['fits'] for r in rows) <= protocol.max_fits, 'Complete nested fit programme exceeds the selected bound')
    return tuple(rows)
