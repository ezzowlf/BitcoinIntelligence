from __future__ import annotations

import json
import hashlib
from pathlib import Path


def load_production8_config(root: Path) -> dict:
    payload=json.loads((Path(root)/"config"/"production8.json").read_text(encoding="utf-8"))
    if payload.get("execution")!="DISABLED":raise RuntimeError("Production 8 execution must remain DISABLED")
    return payload


def verify_underlying_frozen(root: Path) -> dict:
    root=Path(root);results={}
    for label,manifest,folder in (("MASTER5","master_5_0_challenger_frozen.json","master5"),("FUSION6","fusion_6_research_frozen.json","fusion6"),("MACRO7","macro_swing_7_0_research_frozen.json","macro7")):
        payload=json.loads((root/"frozen"/manifest).read_text(encoding="utf-8"));ok=True
        for name,expected in payload["code_manifest_sha256"].items():
            actual=hashlib.sha256((root/"src"/"bitcoin_cycle_analyzer"/folder/name).read_bytes().replace(b"\r\n",b"\n")).hexdigest().upper();ok=ok and actual==expected
        results[label]=ok
    master=json.loads((root/"frozen"/"master_3_0_frozen.json").read_text(encoding="utf-8"));digest=hashlib.sha256()
    for name in ("engine.py","models.py","registry.py","replay.py"):digest.update((root/"src"/"bitcoin_cycle_analyzer"/"master"/name).read_bytes().replace(b"\r\n",b"\n"))
    results["MASTER3"]=digest.hexdigest()==master["master_code_hash"]
    if not all(results.values()):raise RuntimeError("UNDERLYING_FROZEN_HASH_MISMATCH")
    return results
