"""Inactive source inspection; authentic execution is deliberately not a CLI route."""
import argparse
import json
from contract import TASK_ID, SOURCE_COMMIT, GATES, scope
from controls import CONTROL_PLAN


def inspect():
    return {"id": TASK_ID, "source_commit": SOURCE_COMMIT, "scope": scope(),
            "controls": CONTROL_PLAN, "unmet_qualification_gates": list(GATES),
            "runnable": False, "research_qualified": False, "submission_ready": False,
            "authentic_payloads_inspected": False, "native_execution_performed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect",))
    parser.parse_args()
    print(json.dumps(inspect(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
