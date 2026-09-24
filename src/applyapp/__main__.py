"""Allow `python -m applyapp` to invoke the CLI the same way as the `applyapp` script."""

from applyapp.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
