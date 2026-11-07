"""Complete identity-bound original pool and exact A/B case views."""
import os
from pathlib import Path
from common import need,parse,descriptor,capture,canonical,pin,ordinary,relative,save,mkdirs,sync_dir
from transport import View,tree

FAMILIES=('context','random_token','ngram1','ngram3','ngram5','ngram7','ngram10','sem_syn','word2vec','syn')

def sessions(bindings):return {x['id']:x for x in bindings['protocol']['sessions']}
def episodes(bindings):return [s+'_f'+str(f) for s in sessions(bindings) for f in range(5)]

def originals(selection,bindings,budget):
    need(type(selection)is dict and set(selection)=={'root','files'} and set(selection['files'])=={'data_processed.zip','DNN.zip','transcription.zip'},'complete original archive selection')
    root=ordinary(selection['root']);known={x['key']:x for x in bindings['acquisition']['whole_archives']}
    for name,d in selection['files'].items():
        descriptor(d,1000000000);need(d['bytes']==known[name]['size'],'exact original archive extent')
        capture(root/name,d,1000000000,budget,retain=False)
    return root


def verify_generated(root,files,budget,cap=268435456):
    observed,_=tree(root);need(set(observed)==set(files),'exact complete generated output set')
    for name,d in files.items():capture(root/relative(name),d,cap,budget,retain=False)


def prepared(root,report,bindings,budget):
    ss=sessions(bindings);want={s+'.'+f+'.npy'for s in ss for f in ('fr','speaker','timing','qid',*FAMILIES)}|{'DESIGN.json'}
    need(set(report['prepared'])==want and len(want)==197,'all196 full prepared arrays plus design')
    verify_generated(root,report['prepared'],budget,100000000)
    d=parse(capture(root/'DESIGN.json',report['prepared']['DESIGN.json'],500000,budget))
    need(d['schema']=='language_design_v1' and d['protocol_sha256']==bindings['protocol_sha256'] and list(d['sessions'])==list(ss),'full original design protocol/session order')
    for s,g in ss.items():
        row=d['sessions'][s];need(row['geometry']==g and set(row['files'])=={'fr','speaker','timing','qid',*FAMILIES},'exact complete session fields')
        for key,v in row['files'].items():
            name=s+'.'+key+'.npy';need(v['path']==name and descriptor(v,100000000)==report['prepared'][name],'generated complete prepared identity')
    return d,report['prepared']['DESIGN.json']


def episode(root,report,expected,design_pin,bindings,budget):
    want={'candidate/training.npz','candidate/query.npz','candidate/case.json','operator/target.npz','operator/binding.json'}
    need(report['episode']==expected and set(report['files'])==want,'exact complete episode output')
    verify_generated(root,report['files'],budget)
    c=parse(capture(root/'candidate/case.json',report['files']['candidate/case.json'],2000000,budget),2000000)
    b=parse(capture(root/'operator/binding.json',report['files']['operator/binding.json'],2000000,budget),2000000)
    s,f=expected.rsplit('_f',1);g=sessions(bindings)[s]
    need(c['schema']=='language_episode_v1' and c['id']==expected and c['session']==s and c['fold']==int(f) and c['design_sha256']==design_pin['sha256'] and c['protocol_sha256']==bindings['protocol_sha256'],'exact full source-staged episode')
    need(type(c['rows'])is int and 2<=c['rows']<=g['time_bins'] and c['units']==g['units'],'full episode geometry')
    need(b['case']==c and descriptor(b['target'],268435456)==report['files']['operator/target.npz'],'same private source target identity')
    for k in ('training','query'):need(c[k]['path']==k+'.npz' and descriptor(c[k],268435456)==report['files']['candidate/'+k+'.npz'],'same original public source packet')
    rows=b['source_rows'];need(type(rows)is list and len(rows)==c['rows'] and rows==sorted(set(rows)) and all(type(x)is int and 11<=x<g['time_bins'] for x in rows),'complete source-derived target row identity')
    need(len(c['query_ids'])==c['rows'] and len(set(c['query_ids']))==c['rows'],'complete opaque query identities')
    return c,b


def materialize(root,repo,bindings,bodies,context,prepared_root,prepared_files,case_root,case_report,metadata,budget):
    rows=[];role=context['role'];arm=context['arm']
    if arm is not None:
        for r in bindings['materials']['common']+(bindings['materials']['author_code']if arm=='B'else[]):
            rows.append({'source':ordinary(repo)/r['source'],'target':r['target'],**descriptor(r,100000000,allow_empty=True)})
    if context['mode']=='native':
        rows.extend({'source':prepared_root/name,'target':'prepared/'+name,**d}for name,d in prepared_files.items())
    else:
        for n in ('training.npz','query.npz','case.json'):
            rows.append({'source':case_root/'candidate'/n,'target':n,**case_report['files']['candidate/'+n]})
    return View(root,rows,metadata,budget)


def retire_owned(root,files,budget,credit,closed):
    need(closed is True,'owned generating process closed before retirement')
    verify_generated(root,files,budget)
    observed,dirs=tree(root);failures=[]
    for name in sorted(observed):
        try:(root/name).unlink()
        except BaseException as e:failures.append((name,type(e).__name__))
    for name in sorted(dirs,key=lambda n:n.count('/'),reverse=True):
        try:(root/name).rmdir()
        except BaseException as e:failures.append((name,type(e).__name__))
    try:root.rmdir()
    except BaseException as e:failures.append(('.',type(e).__name__))
    need(not failures,'owned retirement incomplete: '+repr(failures));sync_dir(root.parent,budget)
    need(not root.exists(),'owned tree absent after durable retirement');budget.release_retired(credit)
