"""Focused maintained refresh/catalog branches for the fixed ROOT004 correction."""
import ast
import copy
from pathlib import Path
import posixpath
import types
from urllib.parse import quote
import unittest

ROOT = globals().get("_REPOSITORY", Path(__file__).resolve().parents[2])


class Root004ConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core = globals().get("_CORE")
        if core is None:
            file = Path(__file__).with_name("test_root004_manuscript_scope.py")
            core = types.ModuleType("_root004_core")
            core.__file__ = str(file)
            exec(compile(file.read_bytes(), str(file), "exec"), core.__dict__)
        cls.core = core
        if not hasattr(core.Root004ManuscriptScopeTests, "documents"):
            core.Root004ManuscriptScopeTests.setUpClass()
        cls.case = core.Root004ManuscriptScopeTests()
        cls.binding = cls.case.binding
        cls.caller = ast.parse(globals().get("_CALLER_SOURCE") or
            (ROOT / "scripts/maintenance/bind_paper_outcomes.py").read_text())
        cls.catalog = ast.parse(globals().get("_CATALOG_SOURCE") or
            (ROOT / "src/neurobench/catalog.py").read_text())

    def test_refresh_preserves_authenticated_task_and_rejects_changed_current_bytes(self):
        build = next(n for n in self.caller.body if isinstance(n, ast.FunctionDef) and n.name == "build_outputs")
        loop = next(n for n in build.body if isinstance(n, ast.For) and ast.unparse(n.target) == "row")
        branch = next(n for n in loop.body if isinstance(n, ast.If) and ast.unparse(n.test) == "already_bound")
        # Execute the exact maintained branch including real context() before its
        # preservation continue; a fall-through to legacy projection must fail.
        wrapper = ast.Module(body=[ast.For(target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.List(elts=[ast.Constant(1)], ctx=ast.Load()),
            body=[copy.deepcopy(branch), ast.Raise(exc=ast.Call(func=ast.Name(id="AssertionError", ctx=ast.Load()),
                args=[ast.Constant("ROOT004 fell through to stale projection")], keywords=[]), cause=None)],
            orelse=[])], type_ignores=[])
        code = compile(ast.fix_missing_locations(wrapper), "<maintained ROOT004 refresh branch>", "exec")
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                row, previous = self.case.row_and_prior()
                def raw(reader, path):
                    body = self.core.read_file(path)
                    if corrupt and path == self.case.pins["task"]["path"]: body += b" "
                    return body, self.binding.pin(path, body)
                env = dict(binding=self.binding, row=row, identifier=row["id"], home=self.core.HOME,
                    previous=previous, read_pin=self.case.read_pin, improvement=self.case.documents["retained_improvement"],
                    already_bound=True, adopt_language_figure3b=False, contexts={}, outputs={}, reader=None, raw=raw)
                if corrupt:
                    with self.assertRaises(ValueError): exec(code, env)
                else:
                    exec(code, env)
                    self.assertEqual(env["outputs"][row["specification"]["path"]], self.core.read_file(row["specification"]["path"]))
                    self.assertEqual(env["contexts"][row["id"]]["primary_policy_revision"], self.case.pins["descriptor"])
                    self.assertEqual(len(env["outputs"]), 2)

    def test_catalog_selects_only_exact_root004_source_identity(self):
        joins = [n for n in ast.walk(self.catalog) if isinstance(n, ast.AugAssign)
                 and isinstance(n.target, ast.Name) and n.target.id == "successor_ids"
                 and "has_root004_scope" in ast.unparse(n)]
        self.assertEqual(len(joins), 1)
        row, _ = self.case.row_and_prior()
        other = copy.deepcopy(row); other["id"] = "PAPER-ROOT-ADD-005"
        altered = copy.deepcopy(row); altered["specification"]["sha256"] = "0" * 64
        env = dict(module=self.binding, successor_ids=set(),
                   source_by_id={"selected":row, "other":other, "altered":altered})
        exec(compile(ast.fix_missing_locations(ast.Module(body=joins, type_ignores=[])), "<catalog selection>", "exec"), env)
        self.assertEqual(env["successor_ids"], {"selected"})

    def test_catalog_renders_temporal_scope_and_retains_unresolved_limits(self):
        branches = [n for n in ast.walk(self.catalog) if isinstance(n, ast.If)
                    and ast.unparse(n.test) == "row['id'] == 'PAPER-ROOT-ADD-004'"]
        self.assertEqual(len(branches), 1)
        helpers = [n for n in self.catalog.body if isinstance(n, ast.FunctionDef)
                   and n.name in ("markdown_link", "markdown_text")]
        row, _ = self.case.row_and_prior()
        summary = self.binding.public_summary(row, self.case.run_context())
        env = dict(row=row, outcomes=summary, task=self.core.HOME, text="",
                   posixpath=posixpath, quote=quote, OUTPUT="benchmarks/catalog")
        nodes = helpers + copy.deepcopy(branches[0].body)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<catalog rendering>", "exec"), env)
        self.assertIn("temporal-generalization category-AUC surfaces", env["text"])
        self.assertIn("remain unqualified", env["text"])
        self.assertIn("improvement.manuscript-scope.v1.json", env["text"])
        self.assertIn("figure3-manuscript-scope.v1.json", env["text"])
        self.assertIn("Incomplete full-panel representation", env["text"])


if __name__ == "__main__":
    unittest.main()
