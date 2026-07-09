from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m research_intel.run_server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    import uvicorn

    if sys.platform == "win32":
        policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        if not args.reload:
            loop = policy.new_event_loop()
            asyncio.set_event_loop(loop)
            config = uvicorn.Config(
                "research_intel.main:app",
                host=args.host,
                port=args.port,
                http="h11",
                loop="asyncio",
            )
            server = uvicorn.Server(config)
            loop.run_until_complete(server.serve())
            loop.close()
            return 0

    uvicorn.run(
        "research_intel.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        http="h11",
        loop="asyncio",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
