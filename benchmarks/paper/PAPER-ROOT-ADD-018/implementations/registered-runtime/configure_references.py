"""Write owner-local unqualified reference declarations; no provisioning or execution."""
import argparse
import json
from pathlib import Path


def configure(output):
    package = Path(__file__).resolve().parent
    output = Path(output)
    if output.exists():
        raise ValueError('fresh reference declaration directory required')
    templates = json.loads((package / 'REFERENCE_PROGRAM_TEMPLATES.json').read_text())
    output.mkdir()
    for template in templates['templates']:
        manifest = template['manifest']
        manifest['source_root'] = str(package)
        path = output / (template['kind'] + '.json')
        with path.open('x') as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')
    return {'declarations': len(templates['templates']), 'qualified': False,
            'author_dependencies_provisioned': False, 'execution_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(configure(args.output), sort_keys=True))


if __name__ == '__main__':
    main()
