"""Task-local shape adapter to the unchanged qualified candidate boundary."""
from files import need


def runtime(unit):
    return {'public_destinations': tuple(x['mount_destination'] for x in unit['public_inputs']),
            'output_name': unit['output_filename'], 'max_output_bytes': unit['max_output_bytes']}
