"""Put the plugin root on sys.path so `import core…` works under unittest discover."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_plugin_package():
    """Load the hyphenated plugin dir as a proper package (relative imports work)."""
    name = "word_miner_plugin"
    if name in sys.modules and hasattr(sys.modules[name], "register"):
        return sys.modules[name]
    init = ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        name, init, submodule_search_locations=[str(ROOT)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    mod.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    # Also expose submodules under the package name for `from word_miner_plugin.tools import`.
    return mod
