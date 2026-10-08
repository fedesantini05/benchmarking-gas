"""Run isolated suites, so old and new adapters cannot shadow each other."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    suites = [(ROOT, ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
              (ROOT / "legacy", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
              (ROOT / "sgc", ["-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"])]
    failures = 0
    for directory, command in suites:
        print(f"Pruebas: {directory.name}", flush=True)
        failures += subprocess.run([sys.executable, *command], cwd=directory).returncode != 0
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
