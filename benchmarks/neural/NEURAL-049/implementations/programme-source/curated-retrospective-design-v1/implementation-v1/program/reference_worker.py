"""Concrete selected numerical worker; imports only its independently captured bank."""
def run(config):
    if config.get('qualified_execution') is not True:
        raise ValueError('inactive numerical worker')
    implementation = config['implementation']
    if implementation == 'r1':
        from references.r1 import worker_run
    elif implementation == 'r2':
        from references.r2 import worker_run
    else: raise ValueError('exact independent bank')
    return worker_run(config['request_path'], config['request_pin'], config['reference_source_identity'],
                      config['origin'], config['deadline'], config['reference_limits'], config['output']+'/result')
