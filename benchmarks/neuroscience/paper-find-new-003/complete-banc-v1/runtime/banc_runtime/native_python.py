"""Concrete captured Python native worker, never imported by inspect/construct.

No callback is a substitute for InfluenceCalculator. Running this worker
requires a separately qualified native process, complete admitted tables,
isolated writable work directory, and authenticated source bytes. None of
those authentic/native operations is selected by source construction.
"""
import sqlite3
from pathlib import Path
from .codec import need, pin, finite_number

PY_SOURCE='source/native-source/DrugowitschLab_ConnectomeInfluenceCalculator/InfluenceCalculator/InfluenceCalculator.py'
PY_SHA='cdfefac56797355d2ff8aeec8d587ee5841d87904a12321618c613bd9697121d'
PY_BYTES=14594


def sql_identifier(value):
    need(type(value) is str and value and '\0' not in value, 'SQL column identifier')
    return '"'+value.replace('"','""')+'"'


def write_original_sqlite(path, raw_metadata, raw_edges, selected_edge_indices, *, max_sqlite_bytes, meter):
    """Preserve all columns and input order; never alter id/root_id or norms."""
    path=Path(path)
    need(not path.exists() and not path.is_symlink(), 'fresh native SQLite path')
    need(type(max_sqlite_bytes) is int and max_sqlite_bytes>=3*4096,
         'explicit native SQLite extent ceiling')
    meter.reserve_output(max_sqlite_bytes)
    meter.admit_rows(len(raw_metadata.rows)+len(selected_edge_indices))
    need(len(set(raw_metadata.columns))==len(raw_metadata.columns) and
         len(set(raw_edges.columns))==len(raw_edges.columns), 'unique original columns')
    need({'pre','post','count','norm'}<=set(raw_edges.columns), 'original edge columns')
    # SQLite's type adapters can silently turn bools to ints; raw schema is
    # admitted upstream and preserved here. Identity columns must be strings.
    ids={name:raw_metadata.columns.index(name) for name in ('root_id','id')
         if name in raw_metadata.columns}
    for row in raw_metadata.rows:
        need(len(row)==len(raw_metadata.columns), 'metadata row width')
        need(all(row[i] is None or type(row[i]) is str for i in ids.values()),
             'native string ID convention must already be established')
    meter.check_deadline('before_sqlite')
    # Physical SQLite extent is NOT bounded by logical output reservations.
    # The external runner must impose disk/process limits; gate G14 remains.
    conn=sqlite3.connect(path)
    primary=None
    try:
        conn.execute('PRAGMA page_size=4096')
        conn.execute('PRAGMA max_page_count='+str(max_sqlite_bytes//4096))
        for name,table,indices in [('meta',raw_metadata,range(len(raw_metadata.rows))),
                                    ('edgelist_simple',raw_edges,selected_edge_indices)]:
            columns=','.join(sql_identifier(c) for c in table.columns)
            conn.execute('CREATE TABLE '+name+' ('+columns+')')
            placeholders=','.join('?' for _ in table.columns)
            for i in indices:
                row=table.rows[i]
                need(len(row)==len(table.columns), 'original row width')
                need(all(v is None or type(v) in (str,int,float,bool,bytes) for v in row),
                     'ordinary SQLite supported original cells')
                need(all(type(v) is not float or finite_number(v) for v in row), 'no nonfinite SQLite coercion')
                conn.execute('INSERT INTO '+name+' VALUES ('+placeholders+')',row)
        conn.commit()
        meter.check_deadline('after_sqlite')
    except BaseException as error:
        primary=error
        raise
    finally:
        try: conn.close()
        except BaseException as error:
            if primary is None: raise
            primary.add_note('SQLite cleanup uncertainty: '+type(error).__name__)
    extent=path.stat().st_size
    need(extent<=max_sqlite_bytes, 'SQLite output extent refused')
    meter.complete_output(extent)
    return path


def run_python_literal(request, *, raw_source, sqlite_path, max_sqlite_bytes, seed_requests, meter):
    """Actual original constructor and complete solve calls, with no fallback.

    Source is compiled from authenticated captured bytes, not from sys.path.
    PETSc/SLEPc numerical convergence and an independent residual reference
    are still required before these responses can be qualified.
    """
    need(pin(raw_source)=={'bytes':PY_BYTES,'sha256':PY_SHA}, 'exact native Python source')
    need(request.operator_branch in ('captured_Python_unsigned_literal',
         'captured_Python_signed_literal'), 'literal direct Python branch; wrapper runs through R')
    need(not request.graph_variant.endswith('/parallel_rebuild_default_global') or
         request.parameters.count_thresh==5, 'literal parallel-source threshold is5')
    need(request.raw_metadata is not None and request.raw_edges is not None,
         'full original native tables, not compact projections')
    need(type(seed_requests) is tuple and seed_requests, 'complete declared seed request list')
    need(all(type(r) is tuple and len(r)==3 and type(r[0]) is str and
             type(r[1]) is tuple and type(r[2]) is tuple for r in seed_requests),
         'immutable named native seed/silencing requests')
    need(len({r[0] for r in seed_requests})==len(seed_requests), 'unique named native requests')
    need(set(x for _,ids,_ in seed_requests for x in ids)==set(request.source_ids),
         'native request list covers all declared source IDs')
    need(set(x for _,_,ids in seed_requests for x in ids)<=set(request.silenced_ids),
         'silencing remains within declared operator request')
    # Refuse a whole request whose complete output cannot fit the logical row
    # budget before entering a solver or creating its input database.
    meter.admit_rows(len(seed_requests)*len(request.ordered_node_ids))
    # Constructor parameters are taken from the helper's validated immutable
    # request; wrapper omission is retained rather than patched here.
    kwargs=dict(request.constructor_kwargs)
    kwargs['filename']=str(sqlite_path)
    meter.start_job()
    # Never accept an independently supplied database as if it belonged to
    # this prepared request. Materialize exact original records here, before
    # the original constructor filters rows at its own threshold.
    write_original_sqlite(sqlite_path,request.raw_metadata,request.raw_edges,
                          request.selected_edge_indices,max_sqlite_bytes=max_sqlite_bytes,meter=meter)
    namespace={'__name__':'_banc_exact_native_influence','__file__':PY_SOURCE}
    exec(compile(raw_source,PY_SOURCE,'exec'),namespace)
    calculator=namespace['InfluenceCalculator'](**kwargs)
    results=[]
    for name,seed_ids,silenced_ids in seed_requests:
        meter.start_job()
        response=calculator.calculate_influence(list(seed_ids),silenced_neurons=list(silenced_ids))
        rows=tuple(response.to_dict(orient='records'))
        need(len(rows)==len(request.ordered_node_ids), 'complete native response extent')
        results.append((name,rows))
        meter.check_deadline('after_native_seed')
    return {'branch':request.operator_branch,'responses':tuple(results),
            'source_sha256':PY_SHA,'literal_constructor_kwargs':kwargs,
            'native_executed':True,'residual_qualified':False,
            'historical_reference_qualified':False,'scientific_qualification':False}
