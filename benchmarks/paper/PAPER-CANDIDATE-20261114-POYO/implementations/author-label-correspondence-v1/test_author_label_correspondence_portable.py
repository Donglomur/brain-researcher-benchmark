"""Portable generated-input controls; original author fixtures remain private.

These three method bodies were already exercised within the saved five-method
source campaign. This extracted standalone harness was not separately run.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("poyo_author_label_correspondence", Path(__file__).with_name("author_label_correspondence.py"))
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


class LabelCorrespondenceControls(unittest.TestCase):
    def test_literal_extraction_rejects_ambiguous_or_executable_values(self):
        invalid = [
            "monkey_dict={'Chewie':0,'Chewie':1}",
            "monkey_dict={'Chewie':True}",
            "monkey_dict={'Chewie':1,'Mihili':0}",
            "monkey_dict={'Chewie':0,'Mihili':2}",
            "monkey_dict=dict(Chewie=0)",
            "monkey_dict={'Chewie':int('0')}",
            "monkey_dict={'Chewie':0}\nmonkey_dict={'Mihili':0}",
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(binding.BindingError):
                binding._literal_rows(source)
        self.assertEqual(binding._literal_rows("monkey_dict={'Chewie':0}\nraise RuntimeError('must not execute')"), [("Chewie", 0)])

    def test_order_types_and_correspondence_are_not_inferred_from_counts(self):
        rows = [("Chewie_session", 0), ("indy_session_RT", 1)]
        valid = {"names": ["Chewie_session", "indy_session"], "types": ["C", "I"]}
        self.assertEqual(binding._join(rows, valid)[1]["source_terminal_suffix"], "_RT")
        invalid = [
            {"names": ["indy_session", "Chewie_session"], "types": ["I", "C"]},
            {"names": ["Chewie_session", "indy_session"], "types": ["I", "C"]},
            {"names": ["Chewie_session", "indy_other"], "types": ["C", "I"]},
            {"names": ["Chewie_session", "Chewie_session"], "types": ["C", "I"]},
            {"names": ["Chewie_session", "indy_session"], "types": ["C", "I"], "training": True},
        ]
        for metadata in invalid:
            with self.subTest(metadata=metadata), self.assertRaises(binding.BindingError):
                binding._join(rows, metadata)

    def test_duplicate_metadata_keys_are_not_silently_overwritten(self):
        with self.assertRaises(binding.BindingError):
            json.loads('{"names":[],"names":[],"types":[]}', object_pairs_hook=binding._unique_object)


if __name__ == "__main__":
    unittest.main(verbosity=2)
