"""One persistent trusted keyless issuer; a concrete typed source-owned loop."""
import os,socket
import common as c
import fd_protocol as f
import projection_engine as projection
import issuer_sandbox

def serve(fd,config,source,*,initial_read_bytes=0):
    c.exact(config,('schema','source','origin','limits','sandbox','request_roster','maximum_requests'))
    c.need(config['schema']=='neural081_projection_issuer_v1'and c.typed_equal(config['source'],source),'exact captured trusted issuer source')
    c.need(type(config['maximum_requests'])is int and config['maximum_requests']==len(config['request_roster']),'complete selected12N issuer identities')
    budget=c.Budget(config['origin'],config['limits']);budget.charge('read_bytes',initial_read_bytes)
    # Import all numerical support while still in the selected source namespace;
    # no authentic operand FD has been received. No candidate code is imported.
    import numpy as np
    np.lib.format.write_array_header_2_0;np.lib.format.write_array;np.load
    channel=socket.socket(fileno=fd);c.need(channel.type==socket.SOCK_SEQPACKET,'bounded local descriptor packets')
    restriction=issuer_sandbox.restrict(config['sandbox'])
    f.send(channel,{'kind':'ready','source':source,'restriction':restriction,'original_endpoint':budget.end},deadline=budget.end,budget=budget)
    previous=None
    try:
        for ordinal,expected in enumerate(config['request_roster']):
            message,unexpected=f.receive(channel,deadline=budget.end,budget=budget)
            if unexpected is not None:os.close(unexpected);c.need(False,'no unselected descriptor with request')
            c.exact(message,('kind','ordinal','context','role','source','generation','limits','original_endpoint','case_endpoint'))
            c.need(type(message['ordinal'])is int and message['ordinal']==ordinal and c.typed_equal({k:message[k]for k in expected},expected),'exact complete monotone current-context request')
            reply=projection.project(channel,message,budget,np);reply['previous_reply']=previous
            previous=c.pin(c.encoded(reply));f.send(channel,{'kind':'projection','reply':reply},deadline=budget.end,budget=budget)
            # No next context until source-owned parent confirms exact cleanup.
            cleanup,extra=f.receive(channel,deadline=budget.end,budget=budget)
            if extra is not None:os.close(extra);c.need(False,'no cleanup descriptor')
            c.exact(cleanup,('kind','ordinal','reply','cleanup'))
            c.need(cleanup['kind']=='cleaned'and type(cleanup['ordinal'])is int and cleanup['ordinal']==ordinal and c.typed_equal(cleanup['reply'],previous),'matching prior projection cleanup')
            c.exact(cleanup['cleanup'],('files_absent','directory_absent','parent_directory_synced','candidate_closed'))
            c.need(all(v is True for v in cleanup['cleanup'].values()),'complete closed current context before next issuer role')
            del message,reply,cleanup
        close,extra=f.receive(channel,deadline=budget.end,budget=budget)
        if extra is not None:os.close(extra);c.need(False,'no final descriptor')
        c.exact(close,('kind','completed'));c.need(close['kind']=='finish'and type(close['completed'])is int and close['completed']==config['maximum_requests'],'all12N projections before issuer termination')
        budget.check_clock();f.send(channel,{'kind':'finished','completed':config['maximum_requests'],'last_reply':previous,'budget':budget.snapshot()},deadline=budget.end,budget=budget)
    finally:channel.close()
    budget.check_clock()
