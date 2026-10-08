import unittest
from pathlib import Path
from run_company import resolve_config


class ConfigurationTests(unittest.TestCase):
    def test_relative_paths_are_project_relative(self):
        root = Path.cwd()
        config = resolve_config({"template": "data/template.xlsx", "reports": {"2023": "data/2023.pdf"},
                                 "output_dir": "outputs/test"}, root)
        self.assertEqual(config["template"], str((root / "data/template.xlsx").resolve()))
        self.assertEqual(config["reports"]["2023"], str((root / "data/2023.pdf").resolve()))

    def test_input_configuration_is_not_mutated(self):
        original = {"template": "data/template.xlsx", "reports": {"2023": "data/2023.pdf"}}
        resolve_config(original)
        self.assertEqual(original["template"], "data/template.xlsx")
        self.assertEqual(original["reports"]["2023"], "data/2023.pdf")
