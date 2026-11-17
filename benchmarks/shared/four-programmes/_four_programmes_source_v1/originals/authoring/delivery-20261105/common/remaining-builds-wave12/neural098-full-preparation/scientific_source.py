"""Extract only pinned preparation/structural functions, never model code.

This loader is source-only until a selected driver explicitly calls a returned
function. The original modules' top level and reference/model functions are
never executed by this loader.
"""
import ast
import copy
import hashlib
import math
import os
from pathlib import Path

from custody import need


PINS = {
    'prepare': (10785, 'ca9c3439316576986b3e78e74a3805cf032ac53014d65e321e88295784e07cc3'),
    'protocol': (6451, 'f08e50cf68f421ef43aa83391e30e5c51101673cb7f248289af30062ca1961fe'),
    'reference': (5516, '29e7c3d8530e9705cc35e96846b301a0cb660311aa4b339ad85e62e2a1ca386d'),
}
CONSTANTS = {'CHANNELS', 'WINDOWS', 'BASELINE', 'DURATIONS', 'RELEVANCE',
             'ORIENTATIONS', 'AVAILABLE'}
FUNCTIONS = {
    'prepare': {'bool_response', 'validate_binding', 'windows_from_epochs', 'prepare'},
    'protocol': {'image_fold', 'validate_rows'},
    'reference': {'validate_features'},
}


def checked(raw, role):
    need(type(raw) is bytes and (len(raw), hashlib.sha256(raw).hexdigest()) == PINS[role],
         'exact canonical ' + role + ' source')
    return ast.parse(raw)


def load(*, prepare_raw, protocol_raw, reference_raw, terminal_generator,
         profile, io_hooks, native_proxy):
    """Return exact selected functions, with explicit operator custody/I/O hooks.

    io_hooks supplies source_pin, read_json and write_json. Binding JSON may use
    the reviewed32MB operator-only input domain; public output remains4MB.
    """
    need(type(io_hooks) is dict and set(io_hooks) == {'source_pin', 'read_json', 'write_json', 'checkpoint'}
         and all(callable(v) for v in io_hooks.values()), 'exact preparation I/O hooks')
    trees = {'prepare': checked(prepare_raw, 'prepare'),
             'protocol': checked(protocol_raw, 'protocol'),
             'reference': checked(reference_raw, 'reference')}
    need(profile in ('strict_existing_v1', 'nullable_next_v2'), 'explicit binding ABI')
    if profile == 'nullable_next_v2':
        trees['prepare'] = ast.parse(terminal_generator.adapt_preparer_source(prepare_raw))
    selected = []
    names = set()
    for node in trees['protocol'].body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in CONSTANTS:
                selected.append(node); names.add(name)
    need(names == CONSTANTS, 'exact canonical preparation constants')
    removed = 0
    native_imports = 0
    removed_tail = None
    prepare_prefix = None
    for role in ('protocol', 'reference', 'prepare'):
        found = {n.name: n for n in trees[role].body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS[role]}
        need(set(found) == FUNCTIONS[role], 'exact preparation-only function closure')
        for node in found.values():
            unchanged = copy.deepcopy(node)
            validator_index = native_index = None
            tail_nodes = None
            if node.name == 'windows_from_epochs':
                updated = []
                for statement_index, statement in enumerate(node.body):
                    if isinstance(statement, ast.ImportFrom) and statement.module == 'reference_program':
                        need(statement.level == 0 and len(statement.names) == 1
                             and statement.names[0].name == 'validate_features'
                             and statement.names[0].asname is None, 'exact pure validation import removal')
                        removed += 1
                        validator_index = statement_index
                    else:
                        updated.append(statement)
                node.body = updated
            if node.name == 'prepare':
                # Exact original tail starts after full validate_rows. Preserve
                # all scientific statements and the fixed cohort loop verbatim.
                original = ast.dump(node, include_attributes=False)
                positions = [i for i, st in enumerate(node.body) if isinstance(st, ast.Expr)
                             and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Attribute)
                             and isinstance(st.value.func.value, ast.Name)
                             and st.value.func.value.id == 'output' and st.value.func.attr == 'mkdir']
                need(len(positions) == 1, 'one canonical publication tail')
                tail = positions[0]
                tail_nodes = copy.deepcopy(node.body[tail:])
                need(len(node.body[tail:]) == 5, 'exact five-statement canonical publication tail')
                removed_tail = ast.dump(ast.Module(body=node.body[tail:], type_ignores=[]), include_attributes=False)
                prefix = node.body[:tail]
                prepare_prefix = ast.dump(ast.Module(body=prefix, type_ignores=[]), include_attributes=False)
                kept = []
                for prefix_index, st in enumerate(prefix):
                    if isinstance(st, ast.Import) and len(st.names) == 1 and st.names[0].name == 'mne' and st.names[0].asname is None:
                        native_imports += 1
                        native_index = prefix_index
                    else: kept.append(st)
                checkpoints = 0
                for loop in kept:
                    if not isinstance(loop, ast.For): continue
                    revised = []
                    for st in loop.body:
                        revised.append(st)
                        if (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                            and isinstance(st.value.func, ast.Attribute) and isinstance(st.value.func.value, ast.Name)
                            and st.value.func.value.id == 'blocks' and st.value.func.attr == 'append'):
                            revised.append(ast.Expr(value=ast.Call(func=ast.Name(id='checkpoint', ctx=ast.Load()),
                                args=[ast.Name(id=n, ctx=ast.Load()) for n in ('person', 'rows', 'block')], keywords=[])))
                            checkpoints += 1
                    loop.body = revised
                need(checkpoints == 1, 'one private completed-person checkpoint seam')
                node.body = kept + [ast.Return(value=ast.Tuple(elts=[ast.Name(id=n, ctx=ast.Load())
                    for n in ('all_rows', 'blocks', 'provenance')], ctx=ast.Load()))]
            reverse = copy.deepcopy(node)
            if node.name == 'windows_from_epochs':
                reverse.body.insert(validator_index, copy.deepcopy(unchanged.body[validator_index]))
            if node.name == 'prepare':
                need(isinstance(reverse.body[-1], ast.Return), 'one return seam')
                reverse.body = reverse.body[:-1]
                for loop in reverse.body:
                    if isinstance(loop, ast.For):
                        loop.body = [st for st in loop.body if not (isinstance(st, ast.Expr)
                            and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name)
                            and st.value.func.id == 'checkpoint')]
                reverse.body.insert(native_index, copy.deepcopy(unchanged.body[native_index]))
                reverse.body.extend(tail_nodes)
            need(ast.dump(reverse, include_attributes=False) == ast.dump(unchanged, include_attributes=False),
                 'exact reversible preparation-only AST adaptation')
            selected.append(node)
    need(native_imports == 1 and removed_tail is not None, 'exact guarded native and publication seams')
    need(removed == 1, 'one isolated feature validator dependency')
    tree = ast.Module(body=selected, type_ignores=[])
    namespace = {'math': math, 'hashlib': hashlib, 'os': os, 'Path': Path, 'mne': native_proxy, **io_hooks}
    exec(compile(ast.fix_missing_locations(tree), '<pinned preparation-only closure>', 'exec'), namespace)
    need('predict_all' not in namespace and 'aggregate' not in namespace and 'contrasts' not in namespace,
         'reference/model/scoring functions absent')
    namespace['source_derivation'] = {
        'canonical_prepare_sha256': PINS['prepare'][1],
        'canonical_protocol_sha256': PINS['protocol'][1],
        'validator_source_sha256': PINS['reference'][1],
        'profile': profile,
        'reference_module_imported': False,
        'classifier_or_scoring_function_loaded': False,
        'only_reference_function': 'validate_features',
        'removed_imports': removed,
        'native_imports_removed': native_imports,
        'pre_publication_ast_sha256': hashlib.sha256(prepare_prefix.encode()).hexdigest(),
        'removed_publication_ast_sha256': hashlib.sha256(removed_tail.encode()).hexdigest(),
        'reversible_ast_equality': True,
        'publication_return': ['all_rows', 'blocks', 'provenance'],
        'operator_io_hooks': sorted(io_hooks),
    }
    return namespace
