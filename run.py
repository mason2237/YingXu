"""Start the Electron desktop and its Qt-free Python service."""
import sys

def main():
    if sys.argv[1:]==['--read-embedded-subtitles']:
        from yingxu.adapters.mediainfo import probe_main
        return probe_main()
    from run_electron import main as start
    return start()

if __name__=='__main__':
    raise SystemExit(main())
