# Owner CLI fragment, concatenated after the three exact helper fragments.
import argparse
import sys
import time


_PORTABLE_STAGE_ACTIONS = (
    'select-run','request-prepare','bind-prepare','request-bank','bind-bank',
    'request-execution','bind-execution','request-review','bind-request','bind-review',
    'admit-approved-review','bind-collection-completion','request-late-grade','bind-late-grade')


def _cli_descriptor(args, name):
    return descriptor({'path':getattr(args,name),
                       'pin':{'bytes':getattr(args,name+'_bytes'),
                              'sha256':getattr(args,name+'_sha256')}})


def _cli_parser():
    parser = argparse.ArgumentParser(description='NEURAL049 portable metadata constructor; no scientific workers')
    subs = parser.add_subparsers(dest='action',required=True)
    for name in ('build','bind-route','activate-route',*_PORTABLE_STAGE_ACTIONS):
        p = subs.add_parser(name)
        p.add_argument('--origin-monotonic',type=float,required=name!='build')
        for flag in ('deadline-monotonic',):
            p.add_argument('--'+flag,type=float,required=True)
        for flag in ('read-cap-bytes','write-cap-bytes','live-cap-bytes'):
            p.add_argument('--'+flag,type=int,required=True)
        if name == 'build':
            names = ('release','profile')
            p.add_argument('--public-root',required=True)
            p.add_argument('--root',required=True)
        else:
            names = ('instance','input')
        for item in names:
            p.add_argument('--'+item,required=True)
            p.add_argument('--'+item+'-bytes',type=int,required=True)
            p.add_argument('--'+item+'-sha256',required=True)
    return parser


def _cli_bound(value, depth=0):
    need(depth <= 16, 'CLI envelope depth')
    if type(value) is dict:
        size = 2
        for key, item in value.items():
            need(type(key) is str, 'CLI envelope key')
            size += _cli_bound(key, depth+1) + 1 + _cli_bound(item, depth+1) + 1
            need(size <= 65535, 'CLI envelope bound')
        return size
    if type(value) in (list, tuple):
        size = 2
        for item in value:
            size += _cli_bound(item, depth+1) + 1
            need(size <= 65535, 'CLI envelope bound')
        return size
    if type(value) is str:
        need(len(value) <= 5461, 'CLI envelope string')
        return 2 + 12 * len(value)
    if value is None or type(value) is bool:
        return 5
    if type(value) is int:
        need(value.bit_length() <= 128, 'CLI integer extent')
        return 41
    if type(value) is float:
        return 32
    raise Refusal('CLI envelope primitive')


def _cli_emit(value):
    need(_cli_bound(value) + 1 <= 65536, 'CLI envelope bound')
    raw = encode(value)
    need(len(raw) <= 65536, 'CLI envelope encoded extent')
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def portable_cli_main(argv=None):
    io = None
    try:
        args = _cli_parser().parse_args(argv)
        origin = time.monotonic() if args.origin_monotonic is None else args.origin_monotonic
        io = IO({'origin':origin,'deadline':args.deadline_monotonic,
                 'read_cap':args.read_cap_bytes,'write_cap':args.write_cap_bytes,
                 'live_cap':args.live_cap_bytes})
        if args.action == 'build':
            result = build_instance(io,_cli_descriptor(args,'release'),
                                    canonical_path(args.public_root),canonical_path(args.root),
                                    _cli_descriptor(args,'profile'))
            # The complete immutable BUILD_RESULT is retained at its descriptor;
            # do not replicate its entire source inventory into a PIPE result.
            result = {k:v for k,v in result.items() if k != 'result'}
        elif args.action == 'bind-route':
            result = bind_route(io,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        elif args.action == 'activate-route':
            result = activate_route(io,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        else:
            result = assemble_stage(io,args.action,_cli_descriptor(args,'instance'),_cli_descriptor(args,'input'))
        io.close();io.tick()
        _cli_emit({'schema':'neural049_portable_constructor_cli_v1','status':'returned',
                   'action':args.action,'result':result,'costs':io.record(),
                   'automatic_retry':False,'own_future_exit_not_self_certified':True,
                   'scientific_operation_performed':False})
        io.tick()
        return 0
    except SystemExit:
        if io is not None:
            try:io.close()
            except BaseException:pass
        raise
    except BaseException as error:
        later = []
        failure = {'error_type':type(error).__name__,'message':str(error)[:1024],
                   'costs':None,'automatic_retry':False,'durability':'unknown'}
        if io is not None:
            try:
                failure = io.failure(error)
            except BaseException as cleanup:
                later.append({'error_type':type(cleanup).__name__,'failure_publication':'unknown'})
            try:
                io.close()
            except BaseException as cleanup:
                later.append({'error_type':type(cleanup).__name__,'ownership_descriptor_closure':'unknown_or_failed'})
            try:
                failure['costs'] = io.record()
            except BaseException as accounting:
                later.append({'error_type':type(accounting).__name__,'accounting':'unknown'})
        try:
            _cli_emit({'schema':'neural049_portable_constructor_cli_v1','status':'failed',
                       'error_type':type(error).__name__,'failure':failure,'later_errors':later,
                       'costs':failure.get('costs'),'automatic_retry':False,
                       'own_future_exit_not_self_certified':True})
        except BaseException as output_error:
            # The primary record remains with the owned failure handler when it
            # was durably published. A stream failure cannot become success.
            try:
                _cli_emit({'status':'failed','error_type':type(error).__name__,
                           'output_error_type':type(output_error).__name__,
                           'costs_unexported':True,'automatic_retry':False})
            except BaseException:
                pass
        return 1


if __name__ == '__main__':
    raise SystemExit(portable_cli_main())
