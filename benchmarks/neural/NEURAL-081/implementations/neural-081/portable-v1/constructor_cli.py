"""Literal isolated source-constructor and metadata-stage command interface."""

def main(argv=None):
    parser = argparse.ArgumentParser(description='Construct exact NEURAL081 source and bind separately issued metadata; never run science.')
    parser.add_argument('stage', choices=('build', *WRITE_DOMAINS))
    for name in ('read-cap', 'write-cap', 'live-cap'):
        parser.add_argument('--' + name, required=True, type=int)
    parser.add_argument('--deadline', required=True, type=float)
    for name in ('release', 'release-sha256', 'public-root', 'root', 'profile', 'profile-sha256', 'input', 'input-sha256'):
        parser.add_argument('--' + name)
    for name in ('release-bytes', 'profile-bytes', 'input-bytes'):
        parser.add_argument('--' + name, type=int)
    args = parser.parse_args(argv)
    budget = Budget(args.read_cap, args.write_cap, args.live_cap, args.deadline)
    # Explicit source demand is separate from subsequent content authentication.
    own = ordinary_ancestors(str(Path(__file__).absolute()))
    info = own.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ordinary constructor entry')
    budget.charge('read_bytes', info.st_size)
    context = None
    root_ownership = CreatedRoot()
    try:
        if args.stage == 'build':
            need(all(getattr(args, k) is None for k in ('input', 'input_bytes', 'input_sha256')), 'build has no stage-input alias')
            need(all(getattr(args, k) is not None for k in ('release', 'release_bytes', 'release_sha256', 'public_root', 'root', 'profile', 'profile_bytes', 'profile_sha256')), 'explicit complete build arguments')
            release = descriptor({'path': args.release, 'bytes': args.release_bytes, 'sha256': args.release_sha256})
            profile = descriptor({'path': args.profile, 'bytes': args.profile_bytes, 'sha256': args.profile_sha256})
            result = build_instance(release, args.public_root, args.root, profile, budget,
                                    root_ownership=root_ownership)
        else:
            need(all(getattr(args, k) is None for k in ('release', 'release_bytes', 'release_sha256', 'public_root', 'root', 'profile', 'profile_bytes', 'profile_sha256')), 'metadata stage has only pinned input')
            document = descriptor({'path': args.input, 'bytes': args.input_bytes, 'sha256': args.input_sha256})
            inp = capture_json(document, budget)
            exact(inp, ('schema', 'stage', 'instance', 'run', 'payload'))
            need(inp['schema'] == 'neural081_portable_stage_input_v1' and inp['stage'] == args.stage, 'exact stage dispatch')
            context = Context(inp['instance'], inp['run'], args.stage, budget)
            # The single initially supplied control record is metadata, but must
            # also lie in the selected operator namespace before its payload is
            # admitted. No nested pointer has been followed at this boundary.
            context._deny(document['path'])
            need(any(canonical(document['path']).is_relative_to(canonical(p)) for p in context.roots['operator']), 'stage control record in protected operator domain')
            context._remember(document)
            result = STAGES[args.stage](context, inp['payload'])
            context.recheck()
            result = {'schema': 'neural081_portable_metadata_stage_result_v1', 'stage': args.stage,
                      'input': document, 'instance': inp['instance'], 'result': result,
                      'scientific_execution': False, 'original_runtime_exit_observed': False,
                      'budget': budget.snapshot()}
        raw = encode(result)
        need(len(raw) <= 65536, 'bounded constructor terminal report')
        budget.charge('write_bytes', len(raw))
        budget.check()
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        budget.check()
        return 0
    except BaseException as error:
        failure = {'schema': 'neural081_portable_construction_failure_v1', 'stage': args.stage,
                   'exception_type': type(error).__name__, 'automatic_retry': False,
                   'published_prefix_may_remain': True, 'completion_not_established': True,
                   'scientific_execution': False, 'budget': budget.snapshot()}
        # Preserve a new independent failure record when the selected budget and
        # exact writer domain still permit it; never overwrite or roll back.
        try:
            if context is not None:
                domain = 'P' if context.run_root is not None and 'P' in WRITE_DOMAINS[args.stage] else (
                    'V' if 'V' in WRITE_DOMAINS[args.stage] else 'R')
                token = pin(encode(failure))['sha256']
                context.write(domain, 'constructor-failure-' + token + '.json', failure)
            elif root_ownership.fd is not None:
                root_ownership.publish_failure(failure, budget)
        except BaseException:
            pass
        # Original error remains the propagated cause; no success or operating
        # qualification is synthesized by an attempted failure publication.
        raise
    finally:
        original_error = sys.exc_info()[0] is not None
        try:
            root_ownership.close()
        except BaseException:
            if not original_error:
                raise


if __name__ == '__main__':
    raise SystemExit(main())
