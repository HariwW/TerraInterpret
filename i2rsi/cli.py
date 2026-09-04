from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TerraInterpret GeoAI workbench")
    parser.add_argument("--host", default=os.environ.get("I2RSI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("I2RSI_PORT", "8080")))
    parser.add_argument("--reload", action="store_true", help="Reload on source changes")
    args = parser.parse_args()
    uvicorn.run(
        "i2rsi.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=True,
    )


if __name__ == "__main__":
    main()
