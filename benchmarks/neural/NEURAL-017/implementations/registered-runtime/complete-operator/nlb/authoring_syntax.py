"""Source-only F-authoring checker; candidate code is never imported or executed.

This is a separate S01 worker role.  The existing worker runtime owns request
admission, original deadlines, bounded I/O and RESULT/TERMINAL publication.
"""

import ast
import platform

from nlb.contracts import canonical, closed, descriptor, need


POLICY = "NLB017_python_ast_parse_no_execution_v1"
SOURCE_CAP = 128 * 2**10
DIAGNOSTIC_CAP = 2**20


def execute(request, inputs, outputs, trace):
    """Produce an actual syntax diagnostic under an owned worker invocation."""
    need(request["role"] == "source_syntax" and request["stage"] == "S01",
         "only the selected pre-data source-syntax role")
    body = closed(request["body"], {"candidate_source", "syntax_policy"})
    candidate = descriptor(body["candidate_source"])
    need(candidate in request["declared_inputs"], "bound candidate source input")
    policy = closed(body["syntax_policy"], {"schema", "python_version"})
    need(policy["schema"] == POLICY and
         type(policy["python_version"]) is str and
         policy["python_version"] == platform.python_version(),
         "exact selected syntax-parser Python identity")
    raw = inputs.read(candidate, SOURCE_CAP)
    text = raw.decode("utf-8")
    failure = None
    try:
        tree = ast.parse(text, filename="captured_candidate.py", mode="exec")
    except SyntaxError as error:
        # A negative syntax result is a successfully observed check, not a lost
        # process.  Unexpected parser/resource failures propagate to custody.
        failure = {
            "type": "SyntaxError", "message": error.msg,
            "lineno": error.lineno, "offset": error.offset,
            "end_lineno": error.end_lineno, "end_offset": error.end_offset,
            "text": error.text,
        }
    else:
        del tree
    diagnostic = {
        "schema": "NLB017_source_syntax_diagnostic_v1",
        "candidate_source": candidate, "syntax_policy": policy,
        "valid": failure is None, "diagnostic": failure,
        "candidate_imported": False, "candidate_executed": False,
        "empirical_inputs_read": False,
    }
    pin = outputs.write("syntax_diagnostic.json", canonical(diagnostic),
                        DIAGNOSTIC_CAP)
    trace({"event": "source_syntax_observed", "candidate_source": candidate,
           "valid": diagnostic["valid"], "diagnostic": pin})
    return {"diagnostic": pin}


def main():
    from nlb.worker_runtime import main as worker_main
    return worker_main(execute)


def entry():
    try:
        return main()
    except BaseException as original:
        raise SystemExit(1) from original


if __name__ == "__main__":
    raise SystemExit(entry())
