"""Real local Web workspace; diagnostic and legacy Qt entries remain available."""
import sys


def main():
    try:
        from yingxu.web_ui.window import main as start
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print("请使用 .venv-web 环境，并先安装 requirements-web.txt。", file=sys.stderr)
            return 2
        raise
    return start(workspace=True)


if __name__ == "__main__":
    sys.exit(main())
