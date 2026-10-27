"""A process intentionally exits between filesystem effects and journal updates."""
import argparse
import os
from pathlib import Path

from tests.operation_fixtures import approve, noop
from yingxu.desktop.operation_runtime import build_execution


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('point')
    args = parser.parse_args()

    def checkpoint(point, run_id, index):
        if point == args.point:
            os._exit(97)  # Deliberately bypass finally, close and Python cleanup.

    execution = build_execution(args.profile, checkpoint=checkpoint)
    try:
        approve(execution, args.run_id)
        execution.execute(args.run_id, lambda: False, noop)
    finally:
        execution.journal.close()
    return 1  # A missing checkpoint is a test failure.


if __name__ == '__main__':
    raise SystemExit(main())
