"""Build into a separate stage directory, preserving the previous executable."""
import subprocess
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("1", "2", "3", "4"), default="1")
    parser.add_argument("--variant", choices=("refs",))
    args = parser.parse_args()
    stage = args.stage
    output_name = f"stage{stage}" + (f"-{args.variant}" if args.variant else "")
    root = Path(__file__).resolve().parents[1]
    icon = root / "outputs" / "subtitle_organizer.ico"
    build = root / "work" / f"{output_name}-build"
    entry = root / ("run.py" if stage == "1" else "run_preview.py")
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", "YingXuSubtitleOrganizer",
        "--icon", str(icon), "--add-data", f"{icon};.",
        "--paths", str(root), "--distpath", str(root / "outputs" / output_name),
        "--workpath", str(build), "--specpath", str(build), str(entry),
    ]
    subprocess.run(command, cwd=root, check=True)


if __name__ == "__main__":
    main()
