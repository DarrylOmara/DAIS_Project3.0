import importlib

def test_core_modules_importable():
    # smoke-test that core modules import without executing heavy network calls
    mods = [
        'run_all',
        'src.src.data_fetcher',
        'src.src.daist_engine',
        'src.src.metrics',
    ]
    for m in mods:
        mod = importlib.import_module(m)
        assert mod is not None
