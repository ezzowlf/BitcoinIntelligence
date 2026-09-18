"""WAVERUN FULL VPS -> Windows production data export builder (read-only).

Creates C:\\TAKEOFF\\exports\\WAVERUN_FULL_TRANSFER_<UTC>\\ with the 01..14
structure, snapshots every SQLite DB consistently, copies the full
market_events.jsonl (no sampling), builds a repo snapshot + git bundle, writes
SECRET_REQUIREMENTS.md (names only) and the transfer manifests, and computes a
SHA-256 for every file. It never modifies production data.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:\TAKEOFF")
STAMP = sys.argv[1] if len(sys.argv) > 1 else datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
DEST = ROOT / "exports" / f"WAVERUN_FULL_TRANSFER_{STAMP}"
EXPORT_START = datetime.now(UTC).isoformat()

DIRS = [
    "01_repo_snapshot", "02_runtime", "03_databases", "04_market_events_full",
    "05_vantage", "06_binance", "07_predictions", "08_candidates_decisions",
    "09_signals_outcomes", "10_soak", "11_logs", "12_reports", "13_service_config",
    "14_manifests",
]

MANIFEST: list[dict] = []


def sha256_file(path: Path, bufsize: int = 8 << 20) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def jsonl_bounds(path: Path, max_tail: int = 262144) -> tuple[int | None, str | None, str | None]:
    """(line_count, first_ts, last_ts) in a single forward pass + one small tail read."""
    if not path.exists():
        return None, None, None
    first_ts = None
    lines = 0
    with path.open("rb") as f:
        for i, raw in enumerate(f):
            lines += 1
            if i == 0:
                try:
                    row = json.loads(raw)
                    first_ts = str(row.get("received_timestamp") or row.get("timestamp") or "")
                except Exception:
                    first_ts = None
    last_ts = None
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(0, size - max_tail))
            chunk = f.read()
        for raw in reversed(chunk.split(b"\n")):
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
                last_ts = str(row.get("received_timestamp") or row.get("timestamp") or "")
                break
            except Exception:
                continue
    except Exception:
        pass
    return lines, first_ts, last_ts


def record(dest_path: Path, source_path: Path | None, category: str,
           data_start: str | None = None, data_end: str | None = None,
           note: str | None = None, skip_hash: bool = False) -> None:
    st = dest_path.stat()
    digest = None if skip_hash else sha256_file(dest_path)[0]
    MANIFEST.append({
        "relative_path": str(dest_path.relative_to(DEST)).replace("\\", "/"),
        "source_path": None if source_path is None else str(source_path),
        "size_bytes": st.st_size,
        "modified_time": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        "category": category,
        "sha256": digest,
        "data_start_timestamp": data_start,
        "data_end_timestamp": data_end,
        "note": note,
    })
    print(f"  + {MANIFEST[-1]['relative_path']}  ({st.st_size:,} B)", flush=True)


def _already(src: Path, dst: Path) -> bool:
    return dst.exists() and dst.stat().st_size == src.stat().st_size


def copy_jsonl(src: Path, dst: Path, category: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not _already(src, dst):
        shutil.copy2(src, dst)
    lc, a, b = jsonl_bounds(dst)
    record(dst, src, category, a, b, note=f"lines={lc}")


def snapshot_db(src: Path, dst: Path) -> dict:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        d = sqlite3.connect(str(dst))
        ic = d.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {t: d.execute(f'select count(*) from "{t}"').fetchone()[0]
                  for (t,) in d.execute("select name from sqlite_master where type='table'")}
        tmin = tmax = None
        if "predictions" in tables:
            tmin, tmax = d.execute("select min(timestamp), max(timestamp) from predictions").fetchone()
        d.close()
        record(dst, src, "database", tmin, tmax, note=f"integrity_check={ic}; tables={tables}; (reused existing snapshot)")
        return {"name": dst.name, "integrity_check": ic, "tables": tables,
                "data_start": tmin, "data_end": tmax, "size_bytes": dst.stat().st_size}
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(str(dst))
    with d:
        s.backup(d)
    ic = d.execute("PRAGMA integrity_check").fetchone()[0]
    tables = {}
    tmin = tmax = None
    for (t,) in d.execute("select name from sqlite_master where type='table'"):
        try:
            tables[t] = d.execute(f'select count(*) from "{t}"').fetchone()[0]
        except sqlite3.Error:
            tables[t] = None
    if "predictions" in tables:
        try:
            tmin, tmax = d.execute("select min(timestamp), max(timestamp) from predictions").fetchone()
        except sqlite3.Error:
            pass
    d.close()
    s.close()
    record(dst, src, "database", tmin, tmax, note=f"integrity_check={ic}; tables={tables}")
    return {"name": dst.name, "integrity_check": ic, "tables": tables,
            "data_start": tmin, "data_end": tmax, "size_bytes": dst.stat().st_size}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, **kw)


def main() -> None:
    print(f"DEST = {DEST}", flush=True)
    DEST.mkdir(parents=True, exist_ok=True)
    for d in DIRS:
        (DEST / d).mkdir(exist_ok=True)

    # --- 01 repo snapshot (tracked tree, no secrets: .env is gitignored) ------
    tree = DEST / "01_repo_snapshot" / "tree"
    tree.mkdir(exist_ok=True)
    tar = DEST / "01_repo_snapshot" / "_repo_HEAD.tar"
    with tar.open("wb") as fh:
        p = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=str(ROOT), stdout=fh)
    assert p.returncode == 0, "git archive failed"
    subprocess.run(["tar", "-xf", str(tar), "-C", str(tree)], check=True)
    tar.unlink()
    subprocess.run(["git", "bundle", "create", str(DEST / "01_repo_snapshot" / "BitcoinIntelligence_full_history.bundle"), "--all"], cwd=str(ROOT), check=True)
    record(DEST / "01_repo_snapshot" / "BitcoinIntelligence_full_history.bundle", str(ROOT / ".git"), "repo")
    # untracked-but-production-relevant scripts
    ops_dst = DEST / "01_repo_snapshot" / "untracked_ops"
    ops_dst.mkdir(exist_ok=True)
    for f in ROOT.glob("ops/*.ps1"):
        shutil.copy2(f, ops_dst / f.name)
        record(ops_dst / f.name, str(f), "repo", note="UNTRACKED production-adjacent script")
    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    origin = run(["git", "rev-parse", "origin/takeoff-release"]).stdout.strip()
    status = run(["git", "status", "--porcelain"]).stdout
    log = run(["git", "log", "--oneline", "-5"]).stdout
    repo_state = f"""# Repository state (VPS, read-only)

remote: {run(["git", "remote", "-v"]).stdout.strip()}
branch: {run(["git", "branch", "--show-current"]).stdout.strip()}
HEAD:   {head}
origin/takeoff-release: {origin}

## AHEAD OF ORIGIN BY 1 COMMIT - NOT PUSHED, NOT DEPLOYED

Commit `{head[:12]}` ("Fix Binance connect hang and add production resilience
layer") is committed locally on the VPS but has **not** been pushed to origin and
the running services were **not** restarted onto it. The live collector/API/web
processes are still executing the previous release (fd0319e-era code, collector
started 2026-09-02 16:14 UTC). Treat `{head[:12]}` as an
**UNPUSHED / UNDEPLOYED PRODUCTION-INTENDED CHANGE**. Do not push or deploy from
this export; it is provided for analysis continuity only.

## git status --porcelain
{status or "(clean apart from untracked exports/ logs/ ops/)"}

## git log --oneline -5
{log}
"""
    (DEST / "14_manifests" / "REPO_STATE.md").write_text(repo_state, encoding="utf-8")
    record(DEST / "14_manifests" / "REPO_STATE.md", None, "manifest")

    # --- 02 runtime (small state/health/incident files) ---------------------
    rt = ROOT / "runtime"
    for rel in ["waverun/latest.json", "waverun/incidents.jsonl", "waverun/alerts.jsonl",
                "waverun/health.json", "waverun/feed_health.json",
                "waverun_v5_3_fast_v2_forward/status.json", "drawings/BTCUSD.json"]:
        src = rt / rel
        if src.exists():
            dst = DEST / "02_runtime" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            record(dst, src, "runtime")

    # --- 03 databases (consistent snapshots) -------------------------------
    db_reports = []
    for src in sorted((ROOT / "database").glob("*.db")):
        db_reports.append(snapshot_db(src, DEST / "03_databases" / src.name))
    usage = rt / "ai_cache" / "usage.db"
    if usage.exists():
        db_reports.append(snapshot_db(usage, DEST / "03_databases" / "ai_cache_usage.db"))

    # --- 07 predictions pointer (snapshot lives in 03) --------------------
    (DEST / "07_predictions" / "README.md").write_text(
        "waverun_predictions.db (multi-horizon predictions + realized return/MFE/MAE)\n"
        "is the consistent snapshot at ../03_databases/waverun_predictions.db\n"
        "(not duplicated). See 14_manifests/TRANSFER_MANIFEST.json.\n", encoding="utf-8")
    record(DEST / "07_predictions" / "README.md", None, "predictions")

    # --- 06 binance pointer --------------------------------------------
    (DEST / "06_binance" / "README.md").write_text(
        "Binance Spot + Futures raw feed events are the normalized records in\n"
        "../04_market_events_full/market_events.jsonl (event_type/exchange/payload).\n"
        "There is no separate binance-only file on the VPS. L2/orderbook is the\n"
        "@depth stream inside the same file.\n", encoding="utf-8")
    record(DEST / "06_binance" / "README.md", None, "binance")

    # --- 05 vantage / 08 candidates+decisions -------------------------
    copy_jsonl(rt / "waverun/vantage_ticks.jsonl", DEST / "05_vantage/vantage_ticks.jsonl", "vantage")
    for name in ("pre_gate_candidates.jsonl", "decision_records.jsonl", "latency_records.jsonl"):
        copy_jsonl(rt / "waverun" / name, DEST / "08_candidates_decisions" / name, "candidates_decisions")

    # --- 09 signals / outcomes / research corpora ---------------------
    v53 = rt / "waverun_v5_3_fast_v2_forward"
    for f in v53.glob("*"):
        if f.is_file():
            shutil.copy2(f, DEST / "09_signals_outcomes" / f.name)
            record(DEST / "09_signals_outcomes" / f.name, str(f), "signals_outcomes")
    for sub in ("frozen", "challengers"):
        d = ROOT / sub
        if d.is_dir():
            out = DEST / "09_signals_outcomes" / sub
            out.mkdir(parents=True, exist_ok=True)
            for f in d.glob("*"):
                if f.is_file():
                    shutil.copy2(f, out / f.name)
                    record(out / f.name, str(f), "signals_outcomes", note="frozen hypothesis / challenger definition")
    rep = ROOT / "data" / "reports"
    if rep.is_dir():
        for f in rep.rglob("*"):
            if f.is_file() and f.stat().st_size < 25_000_000:
                out = DEST / "09_signals_outcomes" / "research_reports" / f.relative_to(rep)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out)
                record(out, str(f), "signals_outcomes", note="research artefact (FAST_EXPANSION / missed / false-warning corpora)")

    # --- 10 soak ------------------------------------------------------
    for f in (ROOT / "ops" / "soak").glob("*"):
        if f.is_file():
            shutil.copy2(f, DEST / "10_soak" / f.name)
            record(DEST / "10_soak" / f.name, str(f), "soak")
    (DEST / "10_soak" / "PRIOR_CODEX_EXPORT_REFERENCE.md").write_text(
        "The earlier partial export is NOT re-copied here to avoid duplication:\n\n"
        "  path : C:\\TAKEOFF\\exports\\WAVERUN_CODEX_ANALYSIS_20260906_110800.zip\n"
        "  sha256: abcfc83daf66ab2086f5855bdc9ee8c2fee90b3f60246f5f742b4e25088570f6\n"
        "  size : 177243070 bytes\n"
        "  dir  : C:\\TAKEOFF\\exports\\codex_analysis_20260906_110800\\\n\n"
        "It contained head/tail SAMPLES of market_events only. THIS transfer\n"
        "contains the FULL market_events.jsonl in 04_market_events_full/.\n", encoding="utf-8")
    record(DEST / "10_soak" / "PRIOR_CODEX_EXPORT_REFERENCE.md", None, "soak")

    # --- 11 logs ----------------------------------------------------
    for f in list((ROOT / "logs").glob("*.log")) + list((ROOT / "ops").glob("*.log")):
        shutil.copy2(f, DEST / "11_logs" / f.name)
        record(DEST / "11_logs" / f.name, str(f), "logs")

    # --- 12 reports pointer (tracked *.md are in 01_repo_snapshot/tree) ---
    (DEST / "12_reports" / "README.md").write_text(
        "All tracked WAVERUN_*.md / *_REPORT.md production reports are in\n"
        "../01_repo_snapshot/tree/ (they are version-controlled). The soak\n"
        "acceptance + analysis notes are in ../10_soak/.\n", encoding="utf-8")
    record(DEST / "12_reports" / "README.md", None, "reports")

    # --- 13 service config ---------------------------------------
    sc = DEST / "13_service_config"
    ps = r"""
$out = @()
foreach ($s in 'TAKEOFF-Collector','TAKEOFF-API','TAKEOFF-Web') {
  $w = Get-CimInstance Win32_Service -Filter "Name='$s'"
  $out += [pscustomobject]@{ Name=$s; State=$w.State; StartMode=$w.StartMode; PathName=$w.PathName; StartName=$w.StartName; ProcessId=$w.ProcessId }
}
$out | ConvertTo-Json -Depth 4
""".strip()
    def _run_to(cmd, path: Path, note=None, to=20):
        try:
            rr = subprocess.run(cmd, capture_output=True, text=True, timeout=to)
            out = rr.stdout or rr.stderr or ""
        except Exception as exc:  # noqa: BLE001
            out = f"(command failed: {type(exc).__name__})"
        path.write_text(out, encoding="utf-8")
        record(path, None, "service_config", note=note)

    _run_to(["powershell", "-NoProfile", "-Command", ps], sc / "services.json")
    nssm = r"C:\Users\Administrator\Documents\POSTER\runtime\tools\nssm\nssm.exe"
    if Path(nssm).exists():
        params = ("Application", "AppParameters", "AppDirectory", "AppStdout", "AppStderr",
                  "AppExit", "AppRestartDelay", "AppThrottle", "Start", "AppEnvironmentExtra",
                  "AppRotateFiles", "AppRotateBytes", "DisplayName", "Description")
        for s in ("TAKEOFF-Collector", "TAKEOFF-API", "TAKEOFF-Web"):
            lines_out = []
            for p in params:
                try:
                    rr = subprocess.run([nssm, "get", s, p], capture_output=True, text=True, timeout=10)
                    val = (rr.stdout or "").replace("\x00", "").strip()
                except Exception as exc:  # noqa: BLE001
                    val = f"(failed: {type(exc).__name__})"
                lines_out.append(f"{p} = {val}")
            (sc / f"nssm_{s}.txt").write_text("\n".join(lines_out), encoding="utf-8")
            record(sc / f"nssm_{s}.txt", None, "service_config", note="NSSM service parameters (no credentials)")
    _run_to(["schtasks", "/query", "/tn", "TAKEOFF-Soak-Sampler", "/xml"], sc / "scheduledtask_TAKEOFF-Soak-Sampler.xml")
    _run_to(["powershell", "-NoProfile", "-Command",
             "Get-NetTCPConnection -State Listen -LocalPort 8877,8878,8443,8502 -EA SilentlyContinue | Select LocalAddress,LocalPort,OwningProcess | ConvertTo-Json"],
            sc / "listening_ports.json")
    _run_to([r"C:\Program Files\Tailscale\tailscale.exe", "serve", "status"], sc / "tailscale_serve.txt")

    # --- 14 SECRET_REQUIREMENTS.md (names only) ---------------------
    example = (ROOT / ".env.example").read_text(encoding="utf-8") if (ROOT / ".env.example").exists() else ""
    names = [ln.split("=", 1)[0].strip() for ln in example.splitlines() if "=" in ln and not ln.strip().startswith("#")]
    req_map = {
        "FRED_API_KEY": "OPTIONAL (macro data refresh only; NOT used by the live collector / API)",
        "ETF_DATA_API_KEY": "OPTIONAL (ETF module is UNAVAILABLE by design)",
        "MEANPULSE_NEWS_URL": "OPTIONAL", "MEANPULSE_NEWS_FILE": "OPTIONAL",
        "TELEGRAM_BOT_TOKEN": "OPTIONAL (alerting; DRY_RUN fallback when absent)",
        "TELEGRAM_CHAT_ID": "OPTIONAL (alerting target)",
        "TELEGRAM_ENABLED": "OPTIONAL flag (default false)",
        "TELEGRAM_DRY_RUN": "OPTIONAL flag (default true)",
        "EXECUTION": "REQUIRED - must be DISABLED",
        "BITCOIN_EXECUTION_ENABLED": "REQUIRED - must be false",
        "MT5_ENABLED": "OPTIONAL flag (read-only Vantage ticks when true)",
        "MT5_TERMINAL_PATH": "OPTIONAL (path to a local MT5 terminal; not a secret)",
        "MT5_BTC_SYMBOL": "OPTIONAL (e.g. BTCUSD)",
        "OPENAI_API_KEY": "OPTIONAL (OpenAI disabled)", "OPENAI_ENABLED": "OPTIONAL flag (default false)",
    }
    lines = ["# Secret / configuration requirements (names only - NO values)", "",
             "The production `.env` is deliberately excluded from this transfer. Recreate",
             "it on the target from the names below. Broker / MT5 login credentials live",
             "inside the MetaTrader 5 terminal itself and are never in the repo or export.", ""]
    for n in names or list(req_map):
        lines.append(f"- `{n}` = {req_map.get(n, 'OPTIONAL')}")
    lines += ["", "Not present / NOT IMPLEMENTED: `BLS_API_KEY` (BLS integration is NOT IMPLEMENTED)."]
    (DEST / "14_manifests" / "SECRET_REQUIREMENTS.md").write_text("\n".join(lines), encoding="utf-8")
    record(DEST / "14_manifests" / "SECRET_REQUIREMENTS.md", None, "manifest")

    # persist partial manifest + db_reports for the next stage
    (DEST / "14_manifests" / "_stage1.json").write_text(json.dumps(
        {"stamp": STAMP, "export_start": EXPORT_START, "manifest": MANIFEST,
         "db_reports": db_reports, "head": head, "origin": origin}, indent=2), encoding="utf-8")
    print("STAGE 1 COMPLETE", flush=True)
    print(f"MANIFEST entries so far: {len(MANIFEST)}", flush=True)


if __name__ == "__main__":
    main()
