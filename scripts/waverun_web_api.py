"""Run the read-only WAVERUN web API.

    python scripts/waverun_web_api.py --port 8787

Set WAVERUN_ROOT to point at the repository that owns the live runtime/ directory
if the API is started from a worktree or another checkout.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="WAVERUN read-only web API (execution DISABLED)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", type=Path, default=None, help="repository root that owns runtime/")
    args = parser.parse_args()

    if args.root is not None:
        os.environ["WAVERUN_ROOT"] = str(args.root.resolve())

    import uvicorn

    from bitcoin_cycle_analyzer.short_term.web_api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
