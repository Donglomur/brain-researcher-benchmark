"""Exact role-view/artifact custody. Private operands are excluded before opens."""
from pathlib import Path
import os
import stat
from core import canonical, disjoint, relative, need, capture, descriptor, parse, pin, encoded, publish, fresh


class Artifacts:
    def __init__(self, budget, public_roots, private_root, forbidden_roots=()):
        self.gallery=None;self.budget=budget;self.roots=tuple(canonical(x) for x in public_roots);self.private=canonical(private_root)
        self.forbidden=(self.private,*(canonical(x) for x in forbidden_roots))
        need(all(disjoint(r,s) for r in self.roots for s in self.forbidden),'public/private and credential lexical root separation')
    def allowed(self,path):
        path=canonical(path)
        need(all(path!=root and root not in path.parents for root in self.forbidden),'protected target/credential root alias before open')
        need(any(path!=root and root in path.parents for root in self.roots),'operand inside admitted public root')
        return path
    def capture(self,path,expected,cap,retain=True):
        path=self.allowed(path);shared=self.gallery is not None and self.gallery.contains(path)
        if shared:self.gallery.verify(path,expected)
        body=capture(path,expected,cap,self.budget,retain=retain,readonly=True)[0]
        if shared:self.gallery.verify(path,expected)
        return body
    def json(self,path,expected,cap=1<<20):
        return parse(self.capture(path,expected,cap))
    def descriptor(self,path,cap):
        """Post-native output only; requires independently admitted closure first."""
        from core import describe_sealed
        path=self.allowed(path)
        need(self.gallery is None or not self.gallery.contains(path),'shared store is an input, never a newly described producer output')
        return describe_sealed(path,cap,self.budget)

    def gallery_record(self,row=None,*,remeasure=False):
        need(self.gallery is not None,'actual qualified immutable gallery attached before operational operands')
        actual=self.gallery.record(remeasure=remeasure)
        if row is not None:
            need(type(row)is dict and set(row)==set(actual),'exact gallery lifecycle receipt')
            need(all(row[k]==v for k,v in actual.items()if k!='successful_blob_measurements'),
                 'same full qualified store, selected aliases and retained lifecycle')
            count=row['successful_blob_measurements']
            need(type(count)is int and count>=actual['selected_unique_blobs'],'observed bounded kernel measurement count')
        return actual



def mount_files(view_root, manifest, destination, artifacts):
    """Manifest is operator-held; every mounted file is explicitly admitted.

    No manifest exposing original identities, complete packet root, selector-only
    array or neighbouring directory is mounted. A directory is never a bind.
    """
    root=canonical(view_root)
    need(type(manifest) is dict and type(manifest.get('files')) is dict,'explicit view file inventory')
    result=[]
    for name,desc in sorted(manifest['files'].items()):
        rel=relative(name);path=root/rel
        descriptor(desc)
        artifacts.capture(path,desc,desc['bytes'],retain=False)
        result.append({'source':str(path),'destination':destination+'/'+name,'pin':desc,'bytes_cap':desc['bytes']})
    need(result,'nonempty role view')
    return result


def publish_request(root,name,value,budget):
    path=canonical(root)/relative(name);raw=encoded(value)
    return {'path':str(path),'pin':publish(path,raw,budget,readonly=True)}


def worker_mount(path,desc,destination):
    return {'source':str(canonical(path)),'destination':destination,'pin':descriptor(desc),'bytes_cap':desc['bytes']}
