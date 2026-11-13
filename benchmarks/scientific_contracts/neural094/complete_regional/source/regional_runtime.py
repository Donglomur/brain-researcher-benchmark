"""Explicit source-to-mounted-runtime and fixed capsule construction.

This copies authenticated ordinary source, never imports candidate code or
starts a worker. Its output still requires independent native/source admission.
Destination roots must be fresh; a failed partial staging tree is retained and
must not be reused. The caller authenticates this module before loading it.
"""
from pathlib import Path
import os
from regional_custody import need, pin, parsed, read, write, check_pin
from regional_sources import NUMERICAL, TRANSPORT


TOP = ('frozen_program_entry', 'investigator_policy', 'reference_entry',
       'regional_arithmetic', 'regional_controller', 'regional_custody',
       'regional_grading', 'regional_mode_contrasts', 'regional_native',
       'regional_policy', 'regional_preparation', 'regional_runtime',
       'regional_scope', 'regional_sources', 'subset_reference')


def source_map():
    """Fixed complete layout: container flat bootstrap plus sealed host group."""
    mapping = {name + '.py': name + '.py' for name in TOP}
    mapping.update({'numerics/' + name + '.py': 'numerics/' + name + '.py'
                    for name in NUMERICAL})
    mapping['numerics/SOURCE_MANIFEST.json'] = 'numerics/SOURCE_MANIFEST.json'
    for name in TRANSPORT:
        mapping[name + '.py'] = 'transport/' + name + '.py'
        mapping['host_transport/' + name + '.py'] = 'transport/' + name + '.py'
    mapping['host_transport/SOURCE_MANIFEST.json'] = 'transport/SOURCE_MANIFEST.json'
    return mapping


def validate_mounted(inventory, transport_pin):
    mapping = source_map()
    need(type(inventory) is dict and set(inventory) == set(mapping),
         'Complete fixed mounted runtime, including flat bootstrap and sealed host group')
    for row in inventory.values():
        check_pin(row)
        need(row['bytes'] <= 1048576, 'Bounded source member')
    need(inventory['host_transport/SOURCE_MANIFEST.json'] == transport_pin,
         'Host loader manifest is inside the exact admitted mounted inventory')
    for name in TRANSPORT:
        need(inventory[name + '.py'] == inventory['host_transport/' + name + '.py'],
             'Container and trusted host transport copies are byte-identical')
    return mapping


def materialize(source_root, inventory_raw, inventory_pin, destination, budget):
    """Return explicit runtime root/files/map from an externally pinned inventory."""
    check_pin(inventory_pin)
    need(type(inventory_raw) is bytes and pin(inventory_raw) == inventory_pin,
         'Externally authenticated complete source inventory')
    budget.charge('read', len(inventory_raw))
    record = parsed(inventory_raw)
    need(type(record) is dict and set(record) == {'schema', 'files', 'bytes',
         'execution_authority', 'scientific_qualification'}
         and record['schema'] == 'neural094_complete_runtime_source_inventory_v1'
         and record['execution_authority'] is False and record['scientific_qualification'] is False,
         'Source-only runtime inventory')
    mapping = source_map()
    rows = record['files']
    need(type(rows) is list and all(type(r) is dict and set(r) == {'path','bytes','sha256'}
         and type(r['path']) is str and r['path'].startswith('source/') for r in rows),
         'Exact source inventory rows')
    by_source = {r['path'][7:]: {k:r[k] for k in ('bytes','sha256')} for r in rows}
    need(len(by_source) == len(rows) and set(by_source) == set(mapping.values())
         and len({n.casefold() for n in by_source}) == len(by_source), 'Exact complete source selection')
    for row in by_source.values():
        check_pin(row)
        need(row['bytes'] <= 1048576, 'Bounded source member')
    need(type(record['bytes']) is int and record['bytes'] == sum(r['bytes'] for r in by_source.values()),
         'Exact source extent')
    actual = []
    for folder, dirs, files in os.walk(source_root, followlinks=False):
        need(not any(Path(folder,d).is_symlink() for d in dirs), 'Unlinked source tree')
        actual.extend(str(Path(folder,f).relative_to(source_root)) for f in files)
    need(len(actual) == len(by_source) and set(actual) == set(by_source), 'No missing/extra source members')
    root = Path(destination)
    need(root.is_absolute() and root.is_dir() and not root.is_symlink() and not any(root.iterdir()),
         'Fresh absolute mounted runtime root')
    # Complete source authentication precedes writes. These are source bodies,
    # not model/data arrays; exact reads and each duplicate write are charged.
    bodies = {name: read(source_root,name,row,budget) for name,row in by_source.items()}
    for group, names in (('numerics',NUMERICAL), ('transport',TRANSPORT)):
        manifest = parsed(bodies[group + '/SOURCE_MANIFEST.json'])
        need(type(manifest) is dict and set(manifest) == set(names)
             and all(set(manifest[n]) == ({'path','bytes','sha256','original_path'} if group=='numerics' else {'path','bytes','sha256'})
                     and {k:manifest[n][k] for k in ('path','bytes','sha256')} ==
                         {'path':n+'.py',**by_source[group+'/'+n+'.py']}
                     and (group!='numerics' or type(manifest[n]['original_path']) is str) for n in names),
             'Captured group manifests join complete source inventory')
    output = {}
    for mounted, source in mapping.items():
        (root/mounted).parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        output[mounted] = write(root,mounted,bodies[source],budget)
    validate_mounted(output,output['host_transport/SOURCE_MANIFEST.json'])
    return {'root':str(root),'files':output,'source_inventory':inventory_pin,
            'mounted_to_source':mapping}


def materialize_capsules(runtime, destinations, *, program, training_recipe,
                         instructions, budget):
    """Copy fixed task wrappers and exact externally authored candidate bytes.

    The full resulting capsule inventories, including instructions and recipe,
    must bind the later policy/authoring receipts. This is not authorship proof.
    """
    need(type(runtime) is dict and set(runtime) == {'root','files','source_inventory','mounted_to_source'}
         and runtime['mounted_to_source'] == source_map(), 'Exact materialized runtime descriptor')
    validate_mounted(runtime['files'],runtime['files']['host_transport/SOURCE_MANIFEST.json'])
    need(type(destinations) is dict and set(destinations) == {'F','I','reference'}, 'Three fresh capsule roots')
    need(all(type(b) is bytes and 0 < len(b) <= 1048576 for b in (program,training_recipe,instructions)),
         'Explicit bounded authored programme/recipe/instructions')
    budget.charge('read',len(program)+len(training_recipe)+len(instructions))
    need(type(parsed(training_recipe)) is dict and type(parsed(instructions)) is dict,
         'Declared authored recipe and policy instruction objects')
    roots = [Path(v) for v in destinations.values()]
    need(all(r.is_absolute() and r.is_dir() and not r.is_symlink() and not any(r.iterdir()) for r in roots)
         and all(a != b and a not in b.parents and b not in a.parents
                 for i,a in enumerate(roots) for b in roots[i+1:]), 'Fresh disjoint capsule roots')
    need(all(r != Path(runtime['root']) and r not in Path(runtime['root']).parents
         and Path(runtime['root']) not in r.parents for r in roots), 'Capsules separate from runtime')
    fixed = {'F':'frozen_program_entry.py','I':'investigator_policy.py','reference':'reference_entry.py'}
    output = {}
    for role, entry in fixed.items():
        bodies = {entry:read(runtime['root'],entry,runtime['files'][entry],budget)}
        if role == 'F':
            bodies.update({'program.py':program,'TRAINING_RECIPE.json':training_recipe})
        if role == 'I':
            bodies['INSTRUCTIONS.json'] = instructions
        output[role] = {'root':str(destinations[role]),'entrypoint':entry,
            'files':{name:write(destinations[role],name,body,budget) for name,body in bodies.items()}}
    return output
