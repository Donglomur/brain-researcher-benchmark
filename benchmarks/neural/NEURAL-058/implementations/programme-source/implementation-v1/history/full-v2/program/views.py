"""Operator-side exact immutable file mounts; no canonical store directory mount."""
from pathlib import Path
from core import need, fresh, relative
from arrays import read_json,write_json
from corpus import projected_document


class Views:
    def __init__(self,root,complete,output,budget,limits):
        self.root=Path(root);self.budget=budget;self.limits=limits;self.rows={};self.documents={};self.sources={}
        top=read_json(root,complete,budget,limits['metadata_bytes'])
        need(top.get('schema')=='neural058_full_prepared_corpus_v1' and top.get('task')=='NEURAL-058'
             and top.get('conditional_history') is False,'exact full primary packet')
        need(len(top['source'])==423 and len(top['evaluation'])==29,'full prepared session counts')
        from contracts import COHORT_PIN
        need(top['cohort']==COHORT_PIN,'exact original biological roster binding')
        self.complete=complete;self.top=top;self.directory=fresh(output,budget)
        for role in ('C','J'):fresh(self.directory/role,budget)
        for corpus in ('source','evaluation'):
            for item in top[corpus]:
                doc=read_json(root,item,budget,limits['metadata_bytes']);sid=doc['session']
                need(sid not in self.rows and doc['role']==corpus,'unique full packet session role')
                self.rows[sid]={'eid':sid,'animal':doc['animal'],'role':corpus,'fold':doc['fold'],
                                'session_ordinal':doc['session_ordinal'],'animal_ordinal':doc['animal_ordinal']}
                self.documents[sid]=doc
                for role in ('C','J'):
                    directory=fresh(self.directory/role/sid,budget)
                    projected=projected_document(doc,role,corpus=='source')
                    written=write_json(directory,'VIEW.json',projected,budget,limits['metadata_bytes'])
                    self.sources[(role,sid)]={'path':str(directory/'VIEW.json'),'pin':written['pin'],
                                              'projected':projected,'prepared_source':item}
        from ordering import roster as ordered_roster
        self.roster=ordered_roster(self.rows)
        need(self.roster['source_order']==top['source_order'] and self.roster['evaluation_order']==top['evaluation_order']
             and self.roster['source_animals']==top['source_animal_order'] and self.roster['eval_animals']==top['evaluation_animal_order'],
             'exact stable original-source ordering, opaque labels only')

    def input_rows(self,role,session_ids):
        return [{'session':s,'animal':self.rows[s]['animal'],
                 'view':{'path':s+'/VIEW.json','pin':self.sources[(role,s)]['pin']}} for s in session_ids]

    def mounts(self,role,session_ids):
        need(len(session_ids)==len(set(session_ids)),'unique complete authorized sessions')
        result=[]
        for sid in session_ids:
            source=self.sources[(role,sid)];doc=source['projected']
            result.append({'source':source['path'],'destination':'/inputs/corpus/'+sid+'/VIEW.json',
                           'pin':source['pin'],'bytes_cap':self.limits['metadata_bytes']})
            for row in doc['arrays'].values():
                name=relative(row['path']);need(len(name.parts)==1,'prepared primitive member basename')
                result.append({'source':str(self.root/sid/name),'destination':'/inputs/corpus/'+sid+'/'+str(name),
                               'pin':row['pin'],'bytes_cap':self.limits['array_bytes']})
        return result

    def animal_sessions(self,animal):
        from ordering import sessions
        return sessions(self.roster,'evaluation',animal)

    def lineage(self,role,session_ids):
        return [{'session':s,'animal':self.rows[s]['animal'],'role':role,
                 'prepared':self.sources[(role,s)]['prepared_source'],
                 'projected':self.sources[(role,s)]['pin']} for s in session_ids]
