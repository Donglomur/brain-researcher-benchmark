"""Explicit entry points; plan is source metadata only, other commands need grants."""
import argparse
from pathlib import Path
import time
import sys
from .common import capture, decode, encoded, need, pin, publish, Meter


def source(root, expected):
    raw=capture(Path(root)/'SOURCE_MANIFEST.json',expected);manifest=decode(raw)
    need(manifest['schema']=='neural007_full153_source_v1','Exact complete runtime closure')
    for name,descriptor in manifest['files'].items():capture(Path(root)/name,descriptor)
    for name,descriptor in manifest['design'].items():capture(Path(root).parent/'design'/name,descriptor)
    capture(Path(root).parent/'LAUNCHER.json',manifest['launcher'])
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('plan','prepare','campaign','score'))
    p.add_argument('--roster',required=True);p.add_argument('--folds',required=True);p.add_argument('--output',required=True)
    p.add_argument('--profile',choices=('generic_current_person','training_only_reuse'),default='generic_current_person')
    p.add_argument('--grant');p.add_argument('--configuration');p.add_argument('--index');p.add_argument('--predictions');p.add_argument('--receipts');p.add_argument('--operands');p.add_argument('--presentations')
    a=p.parse_args();rb=capture(Path(a.roster).absolute());fb=capture(Path(a.folds).absolute())
    from .packet import roster,admit_index
    rows,folds=roster(rb,fb)
    if a.command=='plan':
        from .schedule import graph
        publish(Path(a.output).absolute(),encoded(graph(folds,rows,a.profile)));return
    need(a.grant is not None,'Authentic execution is not selected by construction; exact separate grant required')
    grant=decode(capture(Path(a.grant).absolute()))
    need(getattr(sys,'_neural007_captured_source',None)==grant['source'], 'Scientific entry requires authenticated captured-byte bootstrap')
    need(getattr(sys,'_neural007_launch_clock',None)==grant['clock'], 'Original launch/grant clock join')
    need(getattr(sys,'_neural007_dependency_roots',None)==grant['qualified_dependency_roots'], 'Exact qualified dependency inventory roots')
    root=Path(__file__).resolve().parent;manifest=source(root,grant['source'])
    need(grant['roster']==manifest['design']['ROSTER.json'] and grant['folds']==manifest['design']['FOLDS.json'], 'Immutable original full-cohort design, no caller-selected cohort')
    if a.command=='prepare':
        from .prepare import prepare
        result=prepare(grant,rb,fb,grant['source_root'],a.output,grant['source'])
        print(encoded(result).decode());return
    need(a.index is not None and a.configuration is not None,'Explicit whole input and qualified configuration')
    ib=capture(Path(a.index).absolute());configuration=decode(capture(Path(a.configuration).absolute()))
    if a.command=='campaign':
        from .study import Campaign
        need(configuration['root']==str(Path(a.output).absolute()),'Exact chosen campaign output')
        result=Campaign(configuration,grant,root,manifest,rb,fb,ib).execute()
        print(encoded(result).decode());return
    from .scorer import score
    from .schedule import graph
    need(a.predictions is not None and a.receipts is not None and a.operands is not None and a.presentations is not None,'Complete independently captured prediction/receipt panel')
    meter=Meter(grant['read_bytes'],grant['write_bytes'],grant['clock']['origin'],grant['clock']['deadline'])
    prepared=admit_index(decode(ib),rows,pin(rb),False,meter)
    need(grant['index']==pin(ib) and grant['roster']==pin(rb) and grant['folds']==pin(fb),'Exact private whole-input scoring binding')
    results=decode(capture(Path(a.predictions).absolute(),grant['predictions'],meter=meter))
    receipts=decode(capture(Path(a.receipts).absolute(),grant['receipts'],meter=meter))
    operands=decode(capture(Path(a.operands).absolute(),grant['operands'],meter=meter))
    presentations=decode(capture(Path(a.presentations).absolute(),grant['private_presentations'],meter=meter))
    output=score(results,graph(folds,rows,a.profile),prepared,receipts,grant,meter,operands,presentations,folds)
    publish(Path(a.output).absolute(),encoded(output),meter)


if __name__=='__main__':main()
