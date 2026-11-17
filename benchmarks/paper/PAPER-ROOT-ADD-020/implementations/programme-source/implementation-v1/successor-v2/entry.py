#!/usr/bin/env python3
"""Source-installed operator entry. Authentic execution is disabled in this tree."""
import argparse
import json
from pathlib import Path
from lib.strict import decode, ContractError, need
from lib.programme import build_plan, require_authority

ROOT = Path(__file__).resolve().parent


def installed_metadata():
    # These two installed source metadata files contain no data/targets/keys.
    return (decode((ROOT/"contracts/programme.json").read_bytes(), 100_000),
            decode((ROOT/"contracts/qualification.json").read_bytes(), 20_000))


def run_installed(verify_operator, admitted_source_loader, runtime_factory, monitor_factory, profile, *, origin_ns):
    """Future trusted-operator API. Never pass these callbacks to candidates.

    Authority is checked before any callback that can touch data/model/provider
    operands. This source ships no authenticated provider or isolation adapter.
    Their independent installation/qualification remains a hard admission gate.
    """
    contract, qualification = installed_metadata()
    expected_admission = require_authority(qualification, contract, "full_study", verify_operator)
    from lib.admission import validate_admission
    admission = admitted_source_loader()
    proof = validate_admission(admission, contract)
    need(proof["admission_digest"] == expected_admission, "admission", "Installed source admission changed")
    # External factories supply only transport/isolated execution and physical
    # monitoring. This source owns the actual scientific dispatch composition.
    from lib.dispatcher import create_dispatcher
    dispatcher = create_dispatcher(contract,admission,runtime_factory(admission),monitor_factory(admission),
                                   implementation_digest=qualification["implementation_digest"])
    from lib.controller import run_study
    return run_study(contract, qualification, verify_operator, dispatcher, dispatcher.observe, profile, origin_ns=origin_ns)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("status", "plan", "run", "grade"))
    args = parser.parse_args(argv)
    contract, qualification = installed_metadata()
    if args.operation == "status":
        answer = {"task_id": contract["task_id"], "source_implemented": True,
                  "execution_enabled": qualification["execution_enabled"], "scientifically_qualified": False,
                  "new_canonical_ids": 0}
    elif args.operation == "plan":
        plan = build_plan(contract)
        answer = {"task_id": plan["task_id"], "programme_digest": plan["programme_digest"],
                  "counts": plan["counts"], "execution_enabled": False}
    else:
        # No candidate path, private source, target or provider argument exists.
        require_authority(qualification, contract, args.operation, None)
        raise ContractError("provider", "An independently installed trusted operator adapter is required")
    print(json.dumps(answer, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(json.dumps({"status": "refused", "code": error.code, "message": str(error)}, sort_keys=True))
        raise SystemExit(2)
