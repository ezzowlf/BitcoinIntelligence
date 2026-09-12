"""Minimal static file server for the WAVERUN frontend build, with a
production-correct caching split:

* /assets/* -- Vite content-hashes these filenames, so the same URL never
  changes content. Cache aggressively and immutably.
* everything else (notably / and /index.html, the entry document) -- must
  always be revalidated so a new deploy's new asset hashes are picked up on
  the very next load. No-cache, not no-store: a 304 round-trip is still cheap.

This replaces a plain `python -m http.server`, which sends no Cache-Control
header at all and left asset freshness to each browser's own heuristics -
the most likely explanation for a client occasionally rendering a stale
build after a deploy. No application/signal logic lives here; this is a
static file server only.
"""
from __future__ import annotations

import argparse
import functools
import http.server


class CachingHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        if self.path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()

    handler = functools.partial(CachingHandler, directory=args.directory)
    with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print(f"Serving {args.directory} on http://{args.bind}:{args.port} (asset cache: immutable, HTML: no-cache)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
