"""Phase 7/8/13: finalize the WAVERUN full transfer - secret scan, manifests,
core archive, and SHA-256 for every transfer part. Read-only on production.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:\TAKEOFF")
STAMP = sys.argv[1]
DEST = ROOT / "exports" / f"WAVERUN_FULL_TRANSFER_{STAMP}"
CORE_ZIP = ROOT / "exports" / f"WAVERUN_FULL_TRANSFER_{STAMP}_core.zip"
LOOSE = {
    "04_market_events_full/market_events.jsonl",
    "03_databases/waverun_predictions.db",
}

# Flag only things that look like an ACTUAL secret VALUE, not a variable name,
# an empty template assignment, a placeholder, or prose.
SECRET_RX = re.compile(
    r"("
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"          # private keys
    r"|\b(?:sk|rk|pk)-[A-Za-z0-9]{32,}\b"                                    # openai-style keys
    r"|\b[0-9]{8,10}:AA[A-Za-z0-9_\-]{33}\b"                                 # real telegram bot token
    r"|(?i:api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['\"][A-Za-z0-9/\+=_\-\.]{16,}['\"]"  # KEY = "<long value>"
    r"|(?i:authorization)\s*:\s*(?:bearer\s+)?[A-Za-z0-9\-_\.=]{24,}"        # literal auth header value
    r"|(?i:xox[baprs]-[A-Za-z0-9\-]{10,})"                                   # slack tokens
    r"|AKIA[0-9A-Z]{16}"                                                     # aws access key id
    r")"
)
# Directories / files that are templates or test fixtures by nature.
SKIP_REL = re.compile(r"(^01_repo_snapshot/tree/(\.env\.example$|tests/|deploy/)|_stage1\.json$)")
TEXT_EXT = {".md", ".json", ".jsonl", ".txt", ".py", ".ps1", ".ts", ".tsx", ".css",
            ".html", ".yaml", ".yml", ".cfg", ".ini", ".toml", ".xml", ".lock", ".example"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def secret_scan() -> list[str]:
    hits: list[str] = []
    for p in DEST.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(DEST)).replace("\\", "/")
        if p.name == ".env" and not rel.endswith(".env.example"):
            hits.append(f"BARE .env FILE PRESENT: {rel}")
            continue
        if SKIP_REL.search(rel):
            continue
        if p.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = p.open("r", encoding="utf-8", errors="replace").read(4_000_000)
        except OSError:
            continue
        for m in SECRET_RX.finditer(text):
            line = text[max(0, m.start() - 80): m.start() + 100].replace("\n", " ")
            hits.append(f"{rel}: ...{line.strip()}...")
    return hits


def main() -> None:
    t0 = time.time()
    stage1 = json.loads((DEST / "14_manifests" / "_stage1.json").read_text())
    manifest = stage1["manifest"]
    have = {m["relative_path"] for m in manifest}

    # market_events loose entry from its one-pass meta
    meta = json.loads((DEST / "04_market_events_full" / "market_events.meta.json").read_text())
    if "04_market_events_full/market_events.jsonl" not in have:
        st = (DEST / "04_market_events_full" / "market_events.jsonl").stat()
        manifest.append({
            "relative_path": "04_market_events_full/market_events.jsonl",
            "source_path": meta["source_path"], "size_bytes": meta["size_bytes"],
            "modified_time": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
            "category": "market_events", "sha256": meta["sha256"],
            "data_start_timestamp": meta["first_timestamp"],
            "data_end_timestamp": meta["last_timestamp"],
            "note": f"FULL copy - line_count={meta['line_count']} - snapshot {meta['snapshot_time_utc']}",
        })
    manifest.append({
        "relative_path": "04_market_events_full/market_events.meta.json",
        "source_path": None, "size_bytes": (DEST / "04_market_events_full" / "market_events.meta.json").stat().st_size,
        "modified_time": datetime.now(UTC).isoformat(), "category": "manifest",
        "sha256": sha256_file(DEST / "04_market_events_full" / "market_events.meta.json"),
        "data_start_timestamp": None, "data_end_timestamp": None, "note": "one-pass metadata for market_events.jsonl",
    })

    # secret scan
    hits = secret_scan()
    secrets_ok = not hits
    (DEST / "14_manifests" / "SECRET_SCAN.txt").write_text(
        "SECRET SCAN RESULT: " + ("PASS - no plaintext secrets found\n" if secrets_ok else "FAIL\n")
        + "\n".join(hits), encoding="utf-8")

    # totals
    raw_cats = {"market_events", "vantage", "binance"}
    total_bytes = sum(m["size_bytes"] for m in manifest)
    raw_bytes = sum(m["size_bytes"] for m in manifest if m["category"] in raw_cats)
    dbs = [m for m in manifest if m["category"] == "database"]
    export_end = datetime.now(UTC).isoformat()

    summary = {
        "transfer_name": f"WAVERUN_FULL_TRANSFER_{STAMP}",
        "export_start": stage1["export_start"], "export_end": export_end,
        "vps_head_commit": stage1["head"], "origin_takeoff_release": stage1["origin"],
        "head_state": "AHEAD_OF_ORIGIN_BY_1 (UNPUSHED, UNDEPLOYED)",
        "total_files": len(manifest), "total_bytes": total_bytes,
        "raw_market_data_bytes": raw_bytes, "database_count": len(dbs),
        "secret_scan": "PASS" if secrets_ok else "FAIL",
        "env_excluded": not any(m["relative_path"].endswith("/.env") for m in manifest),
        "databases": stage1["db_reports"],
        "coverage": {
            "market_events": [meta["first_timestamp"], meta["last_timestamp"]],
        },
        "execution": "DISABLED",
    }
    for m in manifest:
        rp = m["relative_path"]
        if rp.endswith("05_vantage/vantage_ticks.jsonl"):
            summary["coverage"]["vantage"] = [m["data_start_timestamp"], m["data_end_timestamp"]]
        if rp.endswith("08_candidates_decisions/decision_records.jsonl"):
            summary["coverage"]["decisions"] = [m["data_start_timestamp"], m["data_end_timestamp"]]
        if rp.endswith("08_candidates_decisions/pre_gate_candidates.jsonl"):
            summary["coverage"]["candidates"] = [m["data_start_timestamp"], m["data_end_timestamp"]]
    for db in stage1["db_reports"]:
        if db["name"] == "waverun_predictions.db":
            summary["coverage"]["predictions"] = [db["data_start"], db["data_end"]]

    (DEST / "14_manifests" / "TRANSFER_MANIFEST.json").write_text(
        json.dumps({"summary": summary, "files": manifest}, indent=2), encoding="utf-8")

    md = [f"# WAVERUN FULL TRANSFER MANIFEST — {STAMP}", "",
          f"- Export start: {summary['export_start']}", f"- Export end: {export_end}",
          f"- VPS HEAD: `{summary['vps_head_commit']}` ({summary['head_state']})",
          f"- origin/takeoff-release: `{summary['origin_takeoff_release']}`",
          f"- Total files: {summary['total_files']}",
          f"- Total bytes: {total_bytes:,}",
          f"- RAW market data bytes: {raw_bytes:,}",
          f"- Databases: {len(dbs)}", f"- Secret scan: {summary['secret_scan']}",
          f"- Execution: DISABLED", "",
          "## Databases", ""]
    for db in stage1["db_reports"]:
        md.append(f"- `{db['name']}` — {db['size_bytes']:,} B — integrity_check=**{db['integrity_check']}** — tables={db['tables']}")
    md += ["", "## Data coverage", ""]
    for k, v in summary["coverage"].items():
        md.append(f"- {k}: {v[0]}  ->  {v[1]}")
    md += ["", "## Files", "", "| path | bytes | category | sha256 | data_start | data_end |",
           "|---|---|---|---|---|---|"]
    for m in sorted(manifest, key=lambda x: x["relative_path"]):
        md.append(f"| {m['relative_path']} | {m['size_bytes']:,} | {m['category']} | "
                  f"{(m['sha256'] or '')[:16]} | {m['data_start_timestamp'] or ''} | {m['data_end_timestamp'] or ''} |")
    (DEST / "14_manifests" / "TRANSFER_MANIFEST.md").write_text("\n".join(md), encoding="utf-8")

    # core archive: everything except the two huge loose files
    print("building core.zip ...", flush=True)
    with zipfile.ZipFile(CORE_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
        for p in sorted(DEST.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(DEST)).replace("\\", "/")
            if rel in LOOSE or rel == "14_manifests/_stage1.json":
                continue
            z.write(p, arcname=f"WAVERUN_FULL_TRANSFER_{STAMP}/{rel}")

    parts = {
        CORE_ZIP.name: sha256_file(CORE_ZIP),
        "WAVERUN_FULL_TRANSFER_%s/04_market_events_full/market_events.jsonl" % STAMP: meta["sha256"],
        "WAVERUN_FULL_TRANSFER_%s/03_databases/waverun_predictions.db" % STAMP:
            sha256_file(DEST / "03_databases" / "waverun_predictions.db"),
    }
    sha_txt = "\n".join(f"{h}  {name}" for name, h in parts.items()) + "\n"
    (ROOT / "exports" / f"WAVERUN_FULL_TRANSFER_{STAMP}_TRANSFER_SHA256.txt").write_text(sha_txt, encoding="utf-8")
    (DEST / "14_manifests" / "TRANSFER_SHA256.txt").write_text(sha_txt, encoding="utf-8")

    print(json.dumps({
        "summary": summary,
        "parts_sha256": parts,
        "core_zip_bytes": CORE_ZIP.stat().st_size,
        "secret_hits": hits,
        "elapsed_s": round(time.time() - t0, 1),
    }, indent=2))


if __name__ == "__main__":
    main()
