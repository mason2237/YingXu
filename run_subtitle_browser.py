"""Optional subtitle website prototype; run.py remains the offline workspace."""
import sys


def main():
    try:
        from yingxu.web_ui.subtitle_browser import main as start
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print("请使用 .venv-web 环境，先安装 requirements.txt。", file=sys.stderr)
            return 2
        raise
    return start()


if __name__ == "__main__":
    sys.exit(main())
