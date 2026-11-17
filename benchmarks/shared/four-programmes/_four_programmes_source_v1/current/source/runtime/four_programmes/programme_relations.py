"""Closed output-V2 value invariants; these checks never create live owners."""
from .common import need, relative, same


def relations(name, body):
    if name == 'DeclaredProgrammeSource':
        relative(body['relative_path'])
        need(body['relative_path'] != 'neurobench_programme_manifest.json',
             'manifest is a separate control file, never a programme source')
        need(body['mode'] <= 0o777,
             'ordinary declared permission bits without setid, sticky or special bits')
    elif name == 'ProgrammeOutputManifest':
        paths = [row['relative_path'] for row in body['sources']]
        need(paths == sorted(paths, key=lambda value: value.encode('utf8')) and
             len(set(paths)) == len(paths), 'complete unique unsigned UTF8 source ordering')
        ids = [row['job_id'] for row in body['jobs']]
        need(len(set(ids)) == len(ids), 'unique declared programme jobs')
        for job in body['jobs']:
            need(job['report_source_ordinal'] < len(paths) and
                 job['report_argument_ordinal'] < len(job['argv']),
                 'report source and argument are actual admitted ordinals')
            arg = job['argv'][job['report_argument_ordinal']]
            need(arg['schema'] == 'ci_programme_source_argument_v1' and
                 arg['source_ordinal'] == job['report_source_ordinal'],
                 'report producer is exactly the named captured source argument')
            for arg in job['argv']:
                if arg['schema'] == 'ci_programme_source_argument_v1':
                    need(arg['source_ordinal'] < len(paths), 'source ordinal resolves in this manifest')
    elif name == 'CapturedProgrammeFile':
        mode = 0o400 | (body['declared']['mode'] & 0o100)
        need(body['captured_mode'] == body['captured_identity']['mode'] == mode,
             'actual captured mode follows exact root-adopted projection')
        need(body['captured_identity']['kind'] == 'regular_file' and
             body['captured_identity']['relative_path'] == body['captured']['path'],
             'captured identity names the actual captured ordinary file')
        for key in ('device', 'inode', 'uid', 'kind', 'mode', 'relative_path', 'parent_handle_ordinal'):
            need(same(body['before'][key], body['after'][key]), 'same complete original file identity')
        need(body['before']['kind'] == 'regular_file' and
             body['before']['relative_path'] == body['declared']['relative_path'] and
             body['before']['mode'] == body['declared']['mode'] and
             body['before']['observed_ns'] <= body['after']['observed_ns'],
             'original ordinary file mode, path and ordered observations')
        for key in ('bytes', 'sha256'):
            need(body['captured'][key] == body['declared'][key], 'lossless original source bytes')
    elif name == 'CapturedProgrammeSourceManifest':
        need([row['ordinal'] for row in body['files']] == list(range(len(body['files']))),
             'complete contiguous original source ordinals')
        need(body['source_closure'] == [row['captured'] for row in body['files']],
             'exact full captured source closure')
        need(len({row['job_id'] for row in body['jobs']}) == len(body['jobs']),
             'unique complete captured jobs')
        for job in body['jobs']:
            need(job['report_producer'] in body['source_closure'],
                 'actual report producer belongs to this captured source closure')
    elif name == 'HStreamSideV1':
        need(body['bytes'] == body['raw_bytes']['bytes'] and
             body['sha256'] == body['raw_bytes']['sha256'],
             'exact original raw stream extent and digest')
    elif name == 'HStreamCaptureV1':
        need(body['stdout']['name'] == 'stdout' and body['stderr']['name'] == 'stderr',
             'two distinct fixed original stream positions')
        need(body['stdout']['raw_bytes'] != body['stderr']['raw_bytes'],
             'independent actual raw stream publications, including empty streams')
        need(max(body['stdout']['closed_ns'], body['stderr']['closed_ns']) <= body['observed_ns'],
             'actual side closes precede manifest observation')
    elif name == 'DevelopmentWorkspaceClosure':
        need(body['retained_workspace_identity']['kind'] == 'directory' and
             body['retained_workspace_identity']['observed_ns'] <= body['observed_ns'],
             'retained actual workspace directory observed before closure')
    elif name in ('ProgrammeCaptureReceipt', 'ProgrammeAssemblyReceipt'):
        need(body['started_ns'] <= body['finished_ns'], 'original ordered capture interval')
        for key in ('cost_before', 'cost_before_receipt'):
            need(not body[key]['unknown_dimensions'] and
                 all(value is not None for value in body[key]['observed'].values()),
                 'unknown aggregate costs cannot qualify a complete receipt')
        if name == 'ProgrammeCaptureReceipt':
            identities = [(row['path'], row['bytes'], row['sha256']) for row in body['captured_files']]
            need(len(set(identities)) == len(identities), 'complete unique captured file identities')

