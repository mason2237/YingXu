"""Launch the Electron workspace; --preview retains the read-only comparison mode."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    runtime = ROOT / 'work' / 'tools' / 'electron-45.0.0' / 'electron.exe'
    if not runtime.is_file():
        print('请先使用 .venv-web Python 运行 scripts/setup_electron.py。', file=sys.stderr)
        return 2
    env = {**os.environ, 'YINGXU_PYTHON': sys.executable}
    env.pop('ELECTRON_RUN_AS_NODE', None)
    return subprocess.call([str(runtime), str(ROOT / 'desktop' / 'electron'), *sys.argv[1:]],
                           cwd=ROOT, env=env)


if __name__ == '__main__':
    sys.exit(main())
