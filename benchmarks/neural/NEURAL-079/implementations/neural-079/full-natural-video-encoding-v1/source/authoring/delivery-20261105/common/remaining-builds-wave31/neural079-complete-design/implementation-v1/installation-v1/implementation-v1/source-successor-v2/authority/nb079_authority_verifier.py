"""Read-only verifier through the genuine metadata builder; no scientific run."""
from pathlib import PurePosixPath
from nb079_launch_contract import require,fields,canonical,pin,root_reference
from nb079_authority_io import descriptor,absolute,decode,bounded_encode
from n079_composition import MetadataBuilder, ROLE_ORDER, relative
from n079_role_binding import validate_identity_slots, role_map


class VerifierIO:
    """Concrete read-only adapter. No caller-supplied operations or callbacks."""
    def __init__(self,files,roots):
        self.files=files;self.encoding=files.encoding;self.clock=files.clock
        self.roots=[PurePosixPath(absolute(root)) for root in roots]
        self.observed=[]
    def read(self,path,expected=None,phase='scientific',maximum=None):
        p=PurePosixPath(absolute(path));require(any(root in p.parents for root in self.roots),'metadata read in actual selected producer/proposal namespace')
        require(expected is not None,'genuine builder metadata read requires exact source-derived pin')
        if maximum is not None:require(expected['bytes']<=maximum<=self.files.limits['file_bytes'],'same bounded metadata extent')
        item={'path':path,'pin':expected};raw=self.files.read(item,phase)
        self.observed.append(item);return raw


class Verifier(MetadataBuilder):
    """Only write is overridden: compare complete existing canonical artifacts.

    Construction, H derivation, exact metadata graph, grade/catalog/report input
    derivation and proposal order remain the genuine fixed builder source path.
    No bytes are written and no scientific fit, numeric array or result is run.
    """
    def write(self,name,value):
        root=self.cfg['proposal_root'];fields(root,('path','identity'))
        require('/' not in name and name not in ('','.','..'),'exact existing metadata leaf')
        raw=bounded_encode(value,self.io.encoding);require(len(raw)<=self.io.files.limits['file_bytes'],'complete expected metadata extent')
        # Its namespace identity is checked by actual directory FD, not a path flag.
        from nb079_authority_io import open_directory,ident,close_all
        import os
        fd=open_directory(root['path']);first=None
        try:require(ident(fd)==root['identity'],'same actual builder proposal directory')
        except BaseException as error:first=error;raise
        finally:close_all([('verifier proposal directory',lambda:os.close(fd))],first)
        path=root['path']+'/'+name
        require(self.io.read(path,pin(raw))==raw,'entire existing metadata body equals genuine source derivation')
        result={'path':'composition/'+name,**pin(raw)}
        self.catalog[result['path']]={'relative_path':relative(self.cfg['material_root'],path),
            'pin':pin(raw),'immutable_admission':pin(raw)}
        self.written.append({'descriptor':result,'absolute_path':path});return result


def verify_proposal(configuration,finalizer_admission,outer_bindings,role,observations,blocked,baseline,proposal,files):
    descriptor(proposal);roots=[configuration['proposal_root']['path']]
    roots.extend(root_reference(r)['path'] for r in outer_bindings['output_roots'].values())
    io=VerifierIO(files,roots)
    verifier=Verifier(configuration,io,finalizer_admission,outer_bindings=outer_bindings)
    verifier.serial=ROLE_ORDER.index(role)
    actual=verifier.propose(role,observations,blocked,baseline)
    require(actual==proposal,'genuine source-derived proposal descriptor matches actual published request')
    body=decode(files.read(proposal),files.encoding)
    H=role_map(finalizer_admission,blocked)
    validate_identity_slots(role,body['configuration'],configuration['role_templates'],outer_bindings['budget_transport'],H)
    return {'proposal':actual,'body':body,'H':H,'read_metadata':io.observed,'derived_files':verifier.written}
