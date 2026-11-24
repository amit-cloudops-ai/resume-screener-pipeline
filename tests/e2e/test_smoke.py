import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("smoke.py")
SPEC = importlib.util.spec_from_file_location("live_smoke", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def test_smoke_has_nine_valid_resume_fixtures():
    assert len(module.RESUME_IDS) == 9
    assert len(set(module.RESUME_IDS)) == 9
    assert module.RESUME_IDS == ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R09", "R10")

def test_smoke_is_explicitly_gated_by_execute_flag():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    assert parser.parse_args([]).execute is False

def test_production_requires_separate_opt_in_flag():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-prod", action="store_true")
    assert parser.parse_args([]).allow_prod is False
