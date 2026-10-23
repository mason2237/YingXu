"""Stage 6 explicit fixture workspace. No user filesystem access or execution."""
import sys
from yingxu.web_ui.window import main


if __name__ == "__main__":
    sys.exit(main(preview=True))
