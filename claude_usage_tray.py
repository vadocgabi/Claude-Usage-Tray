"""Claude Usage Tray - launcher (PyInstaller entry point). The code lives in the `claude_usage` package."""
import sys

from claude_usage.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
