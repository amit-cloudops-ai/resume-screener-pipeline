import subprocess, sys, pathlib

def test_contracts_validate():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    r = subprocess.run([sys.executable, str(root / "scripts" / "validate_contracts.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
