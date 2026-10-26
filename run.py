"""Start the current PySide6 desktop workspace; --widgets selects the SDR compatibility host."""
import sys


def main():
    if sys.argv[1:] == ['--read-embedded-subtitles']:
        from yingxu.embedded_subtitles import probe_main
        try:
            return probe_main()
        except (OSError, ValueError):
            return 2
    try:
        if '--widgets' in sys.argv:
            sys.argv.remove('--widgets')
            from yingxu.web_ui.window import main as start
            return start()
        from yingxu.web_ui.native_window import main as start
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print("请使用 .venv-web 环境，并先安装 requirements.txt。", file=sys.stderr)
            return 2
        raise
    return start()


if __name__ == "__main__":
    sys.exit(main())
