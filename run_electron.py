"""Launch the Electron workspace and the Qt-free Python service."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    runtime = ROOT / 'work' / 'tools' / 'electron-45.0.0' / 'electron.exe'
    if not runtime.is_file():
        print('请先在 Python 环境运行 scripts/setup_electron.py，详见 docs/DEVELOPMENT.md。', file=sys.stderr)
        return 2
    python = sys.executable
    env = {**os.environ, 'YINGXU_PYTHON': python}
    env.pop('ELECTRON_RUN_AS_NODE', None)
    return subprocess.call([str(runtime), str(ROOT / 'desktop' / 'electron'), *sys.argv[1:]],
                           cwd=ROOT, env=env)


if __name__ == '__main__':
    sys.exit(main())
