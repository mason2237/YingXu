"""Dependency-direction and GUI-free runtime import guards."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAYERS = {
    "domain": {"domain"},
    "application": {"application", "domain", "ports"},
    "ports": {"ports", "domain"},
    "adapters": {"adapters", "domain", "ports"},
}
GUI_MODULES = {"PySide6", "PyQt5", "PyQt6", "qtpy", "tkinter", "wx", "kivy"}


def dependencies(module, source):
    package = module.split(".")[:-1]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - node.level + 1]
                target = ".".join([*base, *node.module.split(".")]) if node.module else ".".join(base)
            else:
                target = node.module or ""
            if node.module is None or target == "yingxu":
                for alias in node.names:
                    yield node.lineno, target + "." + alias.name
            else:
                yield node.lineno, target


def violations(layer, module, source):
    found = []
    for line, dependency in dependencies(module, source):
        parts = dependency.split(".")
        top = parts[0]
        if top in GUI_MODULES:
            found.append((line, dependency))
        elif top == "yingxu":
            if len(parts) < 2 or parts[1] not in LAYERS[layer]:
                found.append((line, dependency))
        elif layer != "adapters" and top not in sys.stdlib_module_names and top != "__future__":
            found.append((line, dependency))
    return found


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_current_repository_has_no_gui_runtime_imports(self):
        failures=[]
        files=[ROOT/'run.py',ROOT/'run_electron.py']
        for directory in ('yingxu','scripts','tests'):
            files.extend((ROOT/directory).rglob('*.py'))
        for file in files:
            for node in ast.walk(ast.parse(file.read_text(encoding='utf-8-sig'))):
                names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                for name in names:
                    if name.split('.')[0] in GUI_MODULES: failures.append(f'{file.relative_to(ROOT)}:{node.lineno}: {name}')
        self.assertEqual(failures,[])

    def test_new_layers_obey_dependency_rules(self):
        problems = []
        for layer in LAYERS:
            directory = ROOT / "yingxu" / layer
            self.assertTrue(directory.is_dir(), f"Missing new layer: {layer}")
            for file in directory.rglob("*.py"):
                module = ".".join(file.relative_to(ROOT).with_suffix("").parts)
                for line, dependency in violations(layer, module, file.read_text(encoding="utf-8-sig")):
                    problems.append(f"{file.relative_to(ROOT)}:{line}: {dependency}")
        self.assertEqual(problems, [], "New-layer import violations:\n" + "\n".join(problems))

    def test_guard_rejects_gui_transport_and_old_layer_imports(self):
        for source in ("from PySide6.QtCore import QObject", "import tkinter", "from ..web_ui import protocol",
                       "from ..desktop.protocol import decode_command", "from yingxu import core",
                       "from ..adapters.local_filesystem import FileSystem", "import third_party"):
            with self.subTest(source=source):
                self.assertTrue(violations("domain", "yingxu.domain.models", source))
        self.assertTrue(violations("application", "yingxu.application.subtitles", "from ..adapters.store import Store"))
        self.assertTrue(violations("ports", "yingxu.ports.state_store", "from ..application.subtitles import SubtitleWorkflow"))
        self.assertTrue(violations("adapters", "yingxu.adapters.store", "from ..application.subtitles import SubtitleWorkflow"))

    def test_guard_accepts_pure_and_port_based_dependencies(self):
        self.assertFalse(violations("domain", "yingxu.domain.models", "from dataclasses import dataclass\nfrom .policies import Rule"))
        self.assertFalse(violations("application", "yingxu.application.subtitles", "from ..domain.models import Task\nfrom ..ports.store import Store"))
        self.assertFalse(violations("ports", "yingxu.ports.store", "from ..domain.models import Task\nfrom typing import Protocol"))
        self.assertFalse(violations("adapters", "yingxu.adapters.store", "from ..ports.store import Store\nimport sqlite3"))


if __name__ == "__main__":
    unittest.main()
