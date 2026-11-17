"""Future owner-only projection of original operands; no reference input."""
import math
import os
from pathlib import Path
import struct
import sys
from common import need, pin, encode, write, signature, admit_pin

SHAPE = (4,62,2,7,28,15)
CONDITIONS = ('NT.pin.all','NT.pout.all','T.pin.all','T.pout.all')
FREQUENCIES = tuple(range(8,15))
TIMES = (tuple(range(53,81)),tuple(range(119,147)))
BYTES = 11665920
SOURCE_PIN = {'bytes':298290277,'sha256':'536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95'}
METADATA_RESERVATION = 16*1024*1024-128*1024
MAX_LOGICAL_SOURCE_READ = 298290277 + 16*1024*1024 + 315456000 + 2*11665920

def project_original(input_path, *, runtime, identity_body, output, budget, selection):
    """Called only by a selected trusted constructor, never a candidate protocol.

    Runtime is the exact authenticated existing reader/identity closure. No
    certificate, support ledger, target category, descriptor or score is read.
    """
    need(type(selection) is dict and set(selection)=={'schema','source','operation','private_delivery_selected'},'projection_selection')
    admit_pin(selection['source'],298290277)
    need(selection['schema']=='tms_original_operand_projection_selection_v1' and
         selection['source']==SOURCE_PIN and selection['operation']=='copy_original_selected_raw_values' and
         selection['private_delivery_selected'] is True,'explicit_original_input_selection')
    need(set(runtime)=={'identity','OwnedDerivative','TransferBudget'},'exact_projection_runtime')
    meta=runtime['identity'](identity_body)
    need(meta['source']==SOURCE_PIN and tuple(meta['conditions'])==CONDITIONS,'original_input_identity')
    transfer=runtime['TransferBudget'](1073741824,33554432,1)
    transfer.deadline=budget.deadline
    # Reserve the complete selected logical upper bound before source access.
    # This is a managed allowance, not an OS/HDF5 physical-I/O measurement.
    budget.charge_read(MAX_LOGICAL_SOURCE_READ)
    owner=runtime['OwnedDerivative'](input_path,meta,transfer,metadata_read_reservation=METADATA_RESERVATION)
    payload=bytearray(BYTES)
    offset=0
    with owner as source:
        start_signature=signature(os.fstat(source.fd))
        need(source.slab.loads==0 and source.slab.returned_vectors==0,'fresh_original_reader')
        for condition in CONDITIONS:
            for channel in range(62):
                for times in TIMES:
                    for frequency in FREQUENCIES:
                        for time_index in times:
                            budget.check()
                            values=source.stored_position_values(condition,channel,frequency,time_index)
                            need(len(values)==15 and all(type(v) is float and
                                 (math.isnan(v) or (math.isfinite(v) and abs(v)<=1000)) for v in values),
                                 'whole_input_finite_domain_no_clipping')
                            array=source.slab.data[:,time_index,frequency]
                            need(array.shape==(15,) and array.dtype.kind=='f' and array.dtype.itemsize==8,
                                 'raw_source_vector_geometry')
                            transfer.charge(read=120)
                            raw=array.tobytes(order='C')
                            order=array.dtype.byteorder
                            need(order in ('<','>','='),'binary64_source_byte_order')
                            big=(order=='>' or (order=='=' and sys.byteorder=='big'))
                            if big:
                                raw=b''.join(raw[i:i+8][::-1] for i in range(0,120,8))
                            # Conversion is byte-order reversal only. This also
                            # preserves NaN payload/sign bits rather than
                            # regenerating NaNs from a category or mask.
                            need(len(raw)==120,'complete_original_vector_bytes')
                            decoded=struct.unpack('<15d',raw)
                            need(all((math.isnan(a) and math.isnan(b)) or a==b
                                     for a,b in zip(decoded,values)),'same_source_operand_values')
                            payload[offset:offset+120]=raw
                            offset+=120
        need(offset==BYTES and source.slab.loads==248 and source.slab.returned_vectors==97216,
             'complete_original_projection')
        need(start_signature==signature(os.fstat(source.fd)),'original_source_stable')
        observed={'channel_slabs':248,'stored_vectors':97216,
                  'raw_values':1458240,'logical_reader_bytes':transfer.reads,
                  'extra_raw_slice_copy_bytes':11665920}
    need(owner.closed_cleanly,'original_reader_complete_closure')
    budget.check()
    # Actual reader traffic includes the full input hash, HDF5 reservation and
    # unchanged slab/vector charges, plus the explicit raw-byte copy above.
    need(transfer.reads<=MAX_LOGICAL_SOURCE_READ,'reserved_original_read_bound')
    root=Path(output)
    root.mkdir(mode=0o700)
    input_root=root/'input'
    input_root.mkdir(mode=0o700)
    value_body=bytes(payload)
    value_entry=write(input_root/'values.f64',value_body,budget)
    manifest={'schema':'tms_original_input_projection_v1','profile':'original_scientific_operands',
              'dtype':'little-endian-binary64','shape':list(SHAPE),
              'axis_order':['condition','channel','window','frequency','time','stored_position'],
              'conditions':list(CONDITIONS),'labels':meta['labels'],
              'source_frequency_indices':list(FREQUENCIES),
              'source_time_indices':[list(v) for v in TIMES],
              'frequency_coordinates':[meta['frequency'][i] for i in FREQUENCIES],
              'time_coordinates':[[meta['time'][i] for i in row] for row in TIMES],
              'stored_positions':list(range(15)),'physical_person_mapping_claimed':False,
              'original_source':SOURCE_PIN,'values':pin(value_body),
              'contains_reference_or_derived_target_fields':False}
    manifest_entry=write(input_root/'INPUT.json',encode(manifest),budget)
    receipt={'schema':'tms_original_projection_owner_receipt_v1','selection':selection,
             'identity':pin(identity_body),'manifest':manifest_entry,'values':value_entry,
             'source_closed':True,'source_cleanup':owner.cleanup,'observed':observed,
             'input_origin':'original_source_only','reference_reads':0,
             'scientific_qualification':False,'rights_redistribution_admitted':False}
    receipt_entry=write(root/'PROJECTION_RECEIPT.private.json',encode(receipt),budget)
    os.chmod(input_root,0o500)
    os.chmod(root,0o500)
    budget.check()
    return receipt_entry

