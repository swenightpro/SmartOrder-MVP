"""
Conftest globale: assegna automaticamente i marker pytest in base alla directory.
- tests/unit/       → @pytest.mark.unit
- tests/integration/ → @pytest.mark.integration
- tests/system/     → @pytest.mark.system
"""
import pathlib


def pytest_collection_modifyitems(config, items):
    for item in items:
        test_path = pathlib.Path(item.fspath)
        parts = test_path.parts

        if "unit" in parts:
            item.add_marker("unit")
        elif "integration" in parts:
            item.add_marker("integration")
        elif "system" in parts:
            item.add_marker("system")
