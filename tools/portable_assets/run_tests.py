import subprocess
import sys
from pathlib import Path

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    commands=[(root,['-m','unittest','discover','-s','tests','-p','test_*.py']),
              (root/'sgc',['-m','unittest','discover','-s','.','-p','test_*.py']),
              (root/'legacy',['-m','unittest','discover','-s','tests','-p','test_*.py'])]
    failures=[subprocess.run([sys.executable,*command],cwd=folder).returncode for folder,command in commands]
    raise SystemExit(1 if any(failures) else 0)
