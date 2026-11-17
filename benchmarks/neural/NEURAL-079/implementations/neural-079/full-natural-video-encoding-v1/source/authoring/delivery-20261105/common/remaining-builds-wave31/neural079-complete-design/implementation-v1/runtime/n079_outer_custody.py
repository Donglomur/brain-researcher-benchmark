"""Independent reads of the actual protected outer FileAuthority exchange.

The separately admitted external issuer is a deployment trust boundary. This
reader does not mint approvals: it reads the exact original protected request,
independently owned response, installed release, and installed configuration.
"""
import os
import stat
from pathlib import PurePosixPath
from ach_resource_common import bounded_decode
from n079_common import require, fields, identity, pin, close_all
from n079_observer import open_directory
from n079_composition import release_sequence, validate_observations


class CustodyMetadataIO:
    def __init__(self, context):
        self.context = context; self.encoding = context.encoding_limits

    def read(self, path, expected=None, phase='scientific', maximum=None, owner=None):
        limit = self.context.profile['reader_limits']['file_bytes'] if maximum is None else maximum
        path = PurePosixPath(path); require(path.is_absolute() and '..' not in path.parts, 'canonical protected metadata path')
        parent = None; fd = None; first = None
        try:
            parent = open_directory(str(path.parent)); fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                    'bounded ordinary single-link protected metadata')
            if owner is not None:
                require(before.st_uid == owner and before.st_mode & 0o022 == 0, 'independently owned protected receipt')
            self.context.ledger.charge('custody-issuer', {'source_read_bytes': before.st_size + 1}, 'full protected outer metadata read', phase)
            raw = bytearray()
            while len(raw) <= before.st_size:
                self.context.tick(phase); block = os.read(fd, min(65536, before.st_size - len(raw) + 1))
                if not block:
                    break
                raw.extend(block)
            after = os.fstat(fd)
            signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            raw = bytes(raw)
            require(signature(before) == signature(after) and len(raw) == before.st_size, 'complete stable protected metadata including EOF')
            require(expected is None or pin(raw) == expected, 'exact protected metadata body pin')
            return raw
        except BaseException as error:
            first = error; raise
        finally:
            close_all(([] if fd is None else [('protected metadata file', lambda: os.close(fd))]) +
                      ([] if parent is None else [('protected metadata directory', lambda: os.close(parent))]), first)


class OuterReleaseReader:
    def __init__(self, context, selected):
        fields(selected, ('request_root', 'response_root', 'response_owner_uid', 'issuer_pin', 'nonce',
                          'operand_roots', 'output_roots', 'material_root'))
        self.context, self.selected = context, selected; self.io = CustodyMetadataIO(context)
        self.encoding = context.encoding_limits; self.records = {}

    def release(self, role, actual_peer):
        require(role in ('controller', 'grader'), 'only actual pre-candidate and target-last graph release')
        sequence = release_sequence(role); name = self.selected['nonce'] + '-%04d.json' % sequence
        roots = []; first = None
        try:
            for which in ('request_root', 'response_root'):
                root = self.selected[which]; fields(root, ('path', 'identity'))
                fd = open_directory(root['path']); roots.append((which, fd)); st = os.fstat(fd)
                require({'device': st.st_dev, 'inode': st.st_ino} == root['identity'] and st.st_mode & 0o022 == 0,
                        'same protected authority namespace')
            response_raw = self.io.read(self.selected['response_root']['path'] + '/' + name,
                                       owner=self.selected['response_owner_uid'])
            response = bounded_decode(response_raw, self.encoding)
            fields(response, ('schema', 'kind', 'sequence', 'nonce', 'request_pin', 'source_pin', 'issuer_pin',
                              'clocks', 'decision', 'admitted'))
            require(response['schema'] == 'n079_outer_authority_response_v1' and response['kind'] == 'release_role' and
                    response['sequence'] == sequence and response['nonce'] == self.selected['nonce'] and
                    response['source_pin'] == self.context.source_pin and response['issuer_pin'] == self.selected['issuer_pin'] and
                    response['clocks'] == {k: getattr(self.context.clock, k) for k in ('origin', 'scientific', 'closeout', 'outer')} and
                    response['decision'] == 'independently_approved_exact_request', 'actual same outer issuer/source/clock/sequence')
            request_raw = self.io.read(self.selected['request_root']['path'] + '/' + name, response['request_pin'])
            request = bounded_decode(request_raw, self.encoding)
            fields(request, ('schema', 'kind', 'sequence', 'nonce', 'source_pin', 'issuer_pin', 'clocks', 'payload'))
            require(request['schema'] == 'n079_outer_authority_request_v1' and
                    all(request[k] == response[k] for k in ('kind', 'sequence', 'nonce', 'source_pin', 'issuer_pin', 'clocks')),
                    'exact independently authenticated actual outer request')
            payload = request['payload']; fields(payload, ('role', 'blocked', 'previous_observations', 'baseline',
                                                          'metadata_proposal', 'metadata_proposal_body'))
            require(payload['role'] == role and all(payload['blocked']['initial_identity'][k] == actual_peer[k]
                    for k in ('pid', 'uid', 'gid')), 'actual already-blocked caller identity joined to outer release')
            observed = payload['previous_observations']; validate_observations(observed, self.context.source_pin, self.encoding)
            proposal = payload['metadata_proposal']; fields(proposal, ('path', 'pin'))
            require(bounded_decode(self.io.read(proposal['path'], proposal['pin']), self.encoding) == payload['metadata_proposal_body'],
                    'fresh exact full metadata proposal')
            body = payload['metadata_proposal_body']
            require(body['role'] == role and body['source_pin'] == self.context.source_pin and
                    body['observations_pin'] == identity(observed, self.encoding) and
                    body['blocked_identity_pin'] == identity(payload['blocked']['initial_identity'], self.encoding),
                    'complete original producer graph and exact proposed role')
            admitted = response['admitted']; fields(admitted, ('path', 'pin'))
            require(any(PurePosixPath(r) in PurePosixPath(admitted['path']).parents for r in self.selected['operand_roots']),
                    'actual installed release within independently admitted protected operands')
            release = bounded_decode(self.io.read(admitted['path'], admitted['pin']), self.encoding)
            require(release['schema'] == 'ach_typed_role_release_v1' and release['role'] == role and
                    release['initial_identity'] == payload['blocked']['initial_identity'] and release['source_pin'] == self.context.source_pin and
                    release['origin_ns'] == self.context.clock.origin and release['scientific_ns'] == self.context.clock.scientific,
                    'actual independently installed release before the same original cutoff')
            installed = bounded_decode(self.io.read(release['configuration_path'], release['configuration_pin']), self.encoding)
            from n079_roles import configuration_projection
            require(configuration_projection(installed, self.encoding) == configuration_projection(body['configuration'], self.encoding),
                    'exact immutable scientific payload/catalog and independently selected installed admission')
            record = {'request_pin': pin(request_raw), 'response_pin': pin(response_raw), 'release': admitted,
                      'configuration_pin': release['configuration_pin'], 'observations': observed, 'configuration': installed}
            self.context.journal.append('actual_outer_custody_graph', record)
            self.records[role] = record; return record
        except BaseException as error:
            first = error; raise
        finally:
            close_all([(which + ' authority directory', lambda fd=fd: os.close(fd)) for which, fd in reversed(roots)], first)
