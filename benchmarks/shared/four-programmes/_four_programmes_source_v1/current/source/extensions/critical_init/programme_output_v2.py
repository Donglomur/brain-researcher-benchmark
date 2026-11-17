"""Full output-V2 serialized inverse; this consumer never creates owners."""
import os
import stat
from pathlib import Path
from .custody import read_pin, parse, encode, pin
from .programme_links_v3 import require_canonical_v3
from four_programmes.common import need, descriptor
from four_programmes.precommit_records import CONDITIONS


def read_output_v2(root, *, seals, policy, execution, census, census_pin, public_interface,
                   cap, budget, meter):
    cache={}
    def read(expected,kind):
        descriptor(expected);key=(expected['path'],expected['bytes'],expected['sha256'])
        if key not in cache:
            need(expected['bytes']<=cap,'same original complete metadata cap')
            meter.charge('retained_bytes',16*expected['bytes']+4096)
            meter.charge('work_units',64*expected['bytes']+4096)
            body=parse(read_pin(root,expected,cap,budget))
            if kind=='ScientificTemplate':
                need(pin(encode(body))=={k:expected[k] for k in ('bytes','sha256')},'original template encoding')
            else:require_canonical_v3(body,expected,kind)
            cache[key]=(kind,body)
        need(cache[key][0]==kind,'one exact nominal role per captured identity')
        return cache[key][1]
    assembly=read(execution['assembler_receipt'],'ProgrammeAssemblyReceipt')
    need(assembly['final_census']==census_pin==execution['final_census']==policy['census'] and
         assembly['seals']==execution['seals']==policy['programme_seals'] and
         assembly['agent_policy']==execution['agent_policy']==policy['same_agent_policy'] and
         assembly['early_selection']==execution['early_selection'] and
         assembly['scientific_template']==execution['scientific_template'] and
         assembly['dispatcher_argv']==execution['dispatcher_argv'] and
         assembly['dispatcher_source']==execution['dispatcher_source'] and
         assembly['public_ABI']==execution['public_ABI']==policy['report_ABI'] and
         assembly['public_interface']==execution['public_interface'],
         'full original assembly-to-execution/policy inverse')
    abi=read(assembly['ABI'],'ProgrammeCaptureABI');agent=read(assembly['agent_policy'],'AgentPolicy')
    need(agent['programme_capture_ABI']==assembly['ABI'] and abi['assembler_source']==assembly['assembler_source'] and
         abi['dispatcher_argv']==assembly['dispatcher_argv'] and abi['dispatcher_source']==assembly['dispatcher_source'] and
         all(p in agent['source_closure'] for p in [abi['source_capture'],abi['assembler_source']]+abi['dispatcher_source']),
         'same earlier fixed output ABI and whole qualified producer source closure')
    template=read(execution['scientific_template'],'ScientificTemplate')
    need(template['schema']=='ci_scientifictemplate_v1' and template['canonical_id']=='PAPER-FIND-050',
         'exact original complete scientific template')
    projected=parse(encode(census))
    for job in projected['jobs']:
        if job['operation']=='candidate':
            need(job.pop('command')==abi['dispatcher_argv'] and job.pop('command_source_pins')==abi['dispatcher_source'],
                 'only exact selected candidate dispatch fields')
    need(encode(projected)==encode(template['census_body']) and
         pin(encode(projected))['sha256']==assembly['projected_template_census_sha256'],
         'all original scientific/unknown fields retained')
    meter.charge('retained_bytes',16*policy['paired_view_manifest']['bytes']+4096)
    paired=parse(read_pin(root,policy['paired_view_manifest'],cap,budget))
    ids=[row['job_id'] for row in public_interface['jobs']];all_files={};receipt_times=[]
    for condition in CONDITIONS:
        seal=seals[condition];source=read(seal['source_manifest'],'CapturedProgrammeSourceManifest')
        receipt=read(seal['capture_receipt'],'ProgrammeCaptureReceipt')
        manifest=read(source['original_manifest'],'ProgrammeOutputManifest')
        need(assembly['source_manifests'][condition]==seal['source_manifest']==receipt['source_manifest'] and
             assembly['capture_receipts'][condition]==seal['capture_receipt'] and
             source['condition']==receipt['condition']==manifest['condition']==seal['condition']==condition and
             source['ABI']==receipt['ABI']==assembly['ABI'] and
             source['agent_policy']==seal['agent_policy']==assembly['agent_policy'] and
             source['development']==receipt['development']==seal['development'] and
             source['pair_closure']==receipt['pair_closure']==seal['pair_closure'] and
             source['source_capture']==receipt['source_capture']==abi['source_capture'] and
             source['development_contract']==receipt['development_contract']==assembly['development_contract'] and
             source['original_attempt']==receipt['original_attempt'] and
             source['original_manifest']==receipt['original_manifest'] and source['workspace']==receipt['workspace'] and
             receipt['owner_binding']==assembly['owner_binding'],'full original per-arm capture ancestry')
        need(source['public_ABI']==manifest['public_ABI']==assembly['public_ABI'] and
             source['public_interface']==manifest['public_interface']==assembly['public_interface'] and
             source['jobs']==seal['jobs'] and source['source_closure']==seal['source_closure']==receipt['captured_files'] and
             [r['declared'] for r in source['files']]==manifest['sources'] and
             [r['job_id'] for r in manifest['jobs']]==[r['job_id'] for r in source['jobs']]==ids,
             'whole original source/job/public roster')
        receipt_times.append(receipt['finished_ns'])
        view=read(source['inherited_view_inventory'],'WorkspaceInventory')
        need(view['condition']==condition,'same earlier workspace inventory')
        members=paired['common']+(paired['author_code'] if condition==CONDITIONS[1] else [])
        for declared,job in zip(manifest['jobs'],source['jobs']):
            need(job['report_producer']==source['files'][declared['report_source_ordinal']]['captured'] and
                 len(job['argv'])==len(declared['argv']),'complete actual per-job source projection')
            for arg,value in zip(declared['argv'],job['argv']):
                if arg['schema']=='ci_programme_source_argument_v1':
                    need(value==source['files'][arg['source_ordinal']]['captured']['path'],'exact captured source relocation')
                elif arg['schema']=='ci_programme_literal_argument_v1':need(value==arg['value'],'exact literal')
                elif arg['schema']=='ci_programme_tool_argument_v1':
                    need(arg['tool'] in agent['tool_closure'],'same original selected tool identity')
                    from four_programmes.common import DependencyUnavailable
                    raise DependencyUnavailable('qualified programme tool command inverse',
                        'The actual earlier qualified command binding is required; output Store location is not command authority.')
                else:
                    need(arg['schema']=='ci_programme_inherited_argument_v1' and
                         arg['view_member_ordinal']<len(members) and value==members[arg['view_member_ordinal']]['destination'],
                         'exact earlier inherited-view ordinal')
        for row in source['files']:
            d=row['captured'];key=(d['path'],d['bytes'],d['sha256'])
            need(key not in all_files,'distinct actual per-arm captured file publications');all_files[key]=row
    need(all(max(receipt_times)<=seals[c]['sealed_ns']<=assembly['started_ns'] for c in CONDITIONS),
         'both receipts before either seal before assembly')
    for row in all_files.values():
        d=row['captured'];i=row['captured_identity'];path=Path(root)/d['path']
        meter.charge('work_units',8192+4*d['bytes']);meter.charge('retained_bytes',d['bytes']+1)
        before=os.stat(path,follow_symlinks=False)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and
             (before.st_dev,before.st_ino,before.st_uid,stat.S_IMODE(before.st_mode))==
             (i['device'],i['inode'],i['uid'],row['captured_mode']), 'actual immutable captured file identity')
        raw=read_pin(root,d,cap,budget);after=os.stat(path,follow_symlinks=False)
        need(all(getattr(before,k)==getattr(after,k) for k in
             ('st_dev','st_ino','st_uid','st_mode','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),
             'same original captured source object through complete read')
        raw.decode('utf8',errors='strict');need(b'\0' not in raw,'ordinary source without normalization')
    return None
