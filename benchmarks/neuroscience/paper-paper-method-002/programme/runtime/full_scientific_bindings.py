"""Resolve future scientific inputs from actual completed local captures.

These objects are never serialized as ownership. Only the controller that owns
the original launches/collections can insert a capture into this registry.
"""
import copy
from .strict import require, canonical_bytes, digest

class Captures:
    def __init__(self):self._rows={}
    def add(self,job,value):
        key=job['job_id'];require(key not in self._rows,'capture reuse')
        c=value['collection']
        require(key==job['condition']+'-'+job['group']+'-complete-family','source-owned family capture key')
        require(c['complete']is True and c['job_id']==key and c['condition']==job['condition']and c['group']==job['group'],'actual completed collection')
        self._rows[key]=(job,value)
    def resolve(self,template):
        job=copy.deepcopy(template);parents={};edges=[];generated=[]
        by={i['logical']:i for i in job['native_inputs']}
        for link in job['predecessor_inputs']:
            key=job['condition']+'-'+link['parent_group']+'-complete-family'
            require(key in self._rows,'actual predecessor not completed')
            parent,owner=self._rows[key];parents[key]=owner
            require(parent['condition']==job['condition']and parent['source_tree_sha256']==job['source_tree_sha256'],'condition/source parent isolation')
            matches=[r for r in owner['collection']['artifacts']if r['artifact_id']==link['artifact_id']]
            require(len(matches)==1,'captured artifact absent/ambiguous');artifact=matches[0]
            target=by[link['logical']]
            require(target['origin']=='actual_predecessor'and artifact['bytes']<=target['max_bytes'],'whole captured extent not admitted')
            for field in('format','dtype','shape'):require(target[field]==artifact[field],'captured format/shape changed')
            target.update(bytes=artifact['bytes'],sha256=artifact['sha256'])
            for path in link['config_sha256_paths']:
                node=job['config']
                for part in path[:-1]:node=node[part]
                require(node[path[-1]]=={'actual_parent_sha256':link['logical']},'parent configuration already substituted')
                node[path[-1]]=artifact['sha256']
            edges.append({'from_stage':key,'artifact_id':artifact['artifact_id'],'to_path':target['path']})
        for target in job['native_inputs']:
            if target['origin']!='actual_parent_observations':continue
            rows=[]
            for group in target['parent_groups']:
                key=job['condition']+'-'+group+'-complete-family'
                require(key in self._rows,'actual observation predecessor absent')
                parent,owner=self._rows[key];parents[key]=owner;c=owner['collection']
                require(parent['condition']==job['condition']and parent['source_tree_sha256']==job['source_tree_sha256'],'observation parent source/condition')
                rows.append({'schema':'jaxley_original_family_capture_v1','group':group,
                    'condition':job['condition'],'job_id':key,'source_tree_sha256':parent['source_tree_sha256'],
                    'receipt_pin':c['receipt_pin'],'original_native_observation':owner['original_native_observation'],
                    'method_operations':c['method_operations'],'artifacts':c['artifacts']})
            body=canonical_bytes(rows);require(len(body)<=target['max_bytes'],'full native observation envelope bound')
            target.update(bytes=len(body),sha256=digest(body));generated.append((target['path'],body))
            if job['group']=='J35' and target['logical']=='whole_family_observations':
                require(job['config']['selected_captures']=={'actual_parent_captures':'whole_family_observations'},'future capture identities cannot be predeclared')
                job['config']['selected_captures']={r['group']:{k:r[k]for k in('job_id','source_tree_sha256','receipt_pin')}for r in rows}
        if job['group']=='J36':
            require(job['config']['selected_upstream_jobs']=={'actual_parent_captures':'all_required_note_products'},'note provenance must come from original captures')
            job['config']['selected_upstream_jobs']=list(parents)
        require(all('bytes'in r and 'sha256'in r for r in job['native_inputs']),'unresolved input identity')
        job['actual_parent_capture_ids']=list(parents)
        job['unresolved_template_sha256']=digest(canonical_bytes(template))
        return job,parents,edges,generated
    def summary(self):return {k:v[1]['collection']for k,v in self._rows.items()}

class Failures:
    """Retain original errors before all independent cleanup/report attempts."""
    def __init__(self):self.errors=[];self.resources=[]
    def catch(self,error):self.errors.append(error)
    def own(self,value):self.resources.append(value);return value
    def attempt(self,operation,*args,**kwargs):
        try:return operation(*args,**kwargs)
        except BaseException as error:self.catch(error)
    def close_all(self):
        while self.resources:
            value=self.resources.pop();self.attempt(value.close)
    def raise_first(self):
        if self.errors:raise self.errors[0]
