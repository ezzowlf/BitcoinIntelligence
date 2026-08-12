from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

import requests


@dataclass(frozen=True)
class AIResult:
    status: str
    text: str
    model: str | None = None
    cached: bool = False
    reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    contradiction_guard: str = "NOT_RUN"
    hallucination_guard: str = "NOT_RUN"
    response_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BitcoinAIRouter:
    """Explanation-only OpenAI layer. Engine decisions remain authoritative."""

    API = "https://api.openai.com/v1"
    DEFAULT_MODELS = {"NANO": "gpt-4.1-nano", "ANALYSIS": "gpt-5.1"}
    # Official public rates; unknown models require explicit environment rates.
    DEFAULT_PRICING = {
        "gpt-4.1-nano": (0.10, 0.025, 0.40),
        "gpt-5.1": (1.25, 0.125, 10.00),
        "gpt-5.1-chat-latest": (1.25, 0.125, 10.00),
    }

    def __init__(self, values=None, session=None, cache_dir: Path | None = None):
        self.values = dict(os.environ) if values is None else dict(values)
        self.session = session or requests.Session()
        self.cache_dir = Path(cache_dir or "runtime/ai_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.key = self.values.get("OPENAI_API_KEY", "").strip()
        self.enabled = self.values.get("OPENAI_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        analysis = self.values.get("OPENAI_ANALYSIS_MODEL") or self.values.get("OPENAI_MINI_MODEL")
        self.models = {
            "NANO": self.values.get("OPENAI_NANO_MODEL") or self.DEFAULT_MODELS["NANO"],
            "ANALYSIS": analysis or self.DEFAULT_MODELS["ANALYSIS"],
        }
        self.models["MINI"] = self.models["ANALYSIS"]  # backwards-compatible UI role
        self.ledger_path = self.cache_dir / "usage.db"
        self._init_ledger()

    def _init_ledger(self):
        with sqlite3.connect(self.ledger_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage(timestamp TEXT,model TEXT,input_tokens INTEGER,output_tokens INTEGER,cached INTEGER,request_type TEXT,estimated_cost REAL)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(usage)")}
            for name, kind in (("state_hash", "TEXT"), ("api_status", "TEXT"), ("guard_status", "TEXT"), ("fallback", "INTEGER")):
                if name not in columns: db.execute(f"ALTER TABLE usage ADD COLUMN {name} {kind}")

    def _rates(self, model: str) -> tuple[float, float, float] | None:
        key = re.sub(r"[^A-Z0-9]+", "_", model.upper()).strip("_")
        names = (f"OPENAI_{key}_INPUT_PER_M", f"OPENAI_{key}_CACHED_INPUT_PER_M", f"OPENAI_{key}_OUTPUT_PER_M")
        if any(self.values.get(name) not in (None, "") for name in names):
            return tuple(float(self.values.get(name, 0) or 0) for name in names)  # type: ignore[return-value]
        return self.DEFAULT_PRICING.get(model)

    def _cost(self, model: str, usage: dict) -> float | None:
        rates = self._rates(model)
        if rates is None:
            return None
        input_tokens = int(usage.get("input_tokens", 0))
        cached_tokens = int(usage.get("input_tokens_details", {}).get("cached_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        normal_input = max(0, input_tokens - cached_tokens)
        return round((normal_input * rates[0] + cached_tokens * rates[1] + output_tokens * rates[2]) / 1_000_000, 8)

    def _record(self, model, input_tokens, output_tokens, cached, request_type, cost=0.0, state_hash=None, api_status="AVAILABLE", guard_status="NOT_RUN", fallback=False):
        with sqlite3.connect(self.ledger_path) as db:
            db.execute("INSERT INTO usage(timestamp,model,input_tokens,output_tokens,cached,request_type,estimated_cost,state_hash,api_status,guard_status,fallback) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), model, int(input_tokens), int(output_tokens), int(cached), request_type, float(cost or 0), state_hash, api_status, guard_status, int(fallback)))

    def usage_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.ledger_path) as db:
            row = db.execute("SELECT COUNT(*),COALESCE(SUM(cached),0),COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),COALESCE(SUM(estimated_cost),0),COALESCE(SUM(request_type='NANO'),0),COALESCE(SUM(request_type='ANALYSIS'),0),COALESCE(SUM(fallback),0) FROM usage WHERE timestamp LIKE ?", (today + "%",)).fetchone()
        return {"calls": row[0], "cache_hits": row[1], "input_tokens": row[2], "output_tokens": row[3], "estimated_cost_usd": round(row[4], 8), "nano_requests": row[5], "deep_requests": row[6], "fallbacks": row[7]}

    def _budget_available(self):
        limit = float(self.values.get("OPENAI_MAX_DAILY_COST", 0) or 0)
        return limit <= 0 or self.usage_today()["estimated_cost_usd"] < limit

    def discover_models(self) -> dict:
        if not self.key:
            return {"status": "UNAVAILABLE_NO_API_KEY", "count": 0, "models": [], "nano": [], "mini": [], "selected": self.models}
        try:
            response = self._request("get", f"{self.API}/models", headers={"Authorization": f"Bearer {self.key}"}, timeout=30)
            response.raise_for_status()
            ids = sorted(item["id"] for item in response.json().get("data", []) if item.get("id"))
            return {
                "status": "CONNECTED",
                "count": len(ids),
                "models": ids,
                "nano": [model for model in ids if "nano" in model],
                "mini": [model for model in ids if "mini" in model],
                "selected": {"NANO": self.models["NANO"], "ANALYSIS": self.models["ANALYSIS"]},
                "selected_available": {role: model in ids for role, model in (("NANO", self.models["NANO"]), ("ANALYSIS", self.models["ANALYSIS"]))},
            }
        except Exception as exc:
            return {"status": "UNAVAILABLE_API_ERROR", "count": 0, "models": [], "selected": self.models, "reason": type(exc).__name__}

    def _request(self, method: str, url: str, **kwargs):
        response = None
        for attempt in range(3):
            try:
                response = getattr(self.session, method)(url, **kwargs)
            except (requests.Timeout, requests.ConnectionError):
                if attempt < 2: time.sleep(0.25 * (attempt + 1))
                continue
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt < 2: time.sleep(0.25 * (attempt + 1))
        if response is not None:
            return response
        raise requests.Timeout("OpenAI request timed out after retries")

    def health(self) -> dict:
        discovered = self.discover_models() if self.enabled else {"status": "DISABLED"}
        return {"enabled": self.enabled, "discovery": discovered["status"], "nano_model": self.models["NANO"], "analysis_model": self.models["ANALYSIS"], "key_configured": bool(self.key), "usage_today": self.usage_today(), "budget_available": self._budget_available()}

    @staticmethod
    def deterministic_summary(state: dict) -> str:
        d = state["master"]["decision"]
        actions = state.get("macro7", {}).get("actions", {})
        return (f"MASTER bewertet Bitcoin langfristig mit {d['long_term_action']}. Für einen neuen Einstieg gilt {d['new_entry_action']}; "
                f"Long Swing steht auf {actions.get('long_swing', 'UNAVAILABLE')}, das Risiko auf {d['risk_action']}. "
                f"Es liegt {d['production_signal']} vor. Diese Zusammenfassung ist deterministisch; Execution bleibt DISABLED.")

    @staticmethod
    def grounded_state(state: dict) -> dict:
        macro = state.get("macro7", {})
        master = state.get("master", {})
        master_state = master.get("state") or {}
        elliott = macro.get("elliott") or {}
        historical = state.get("historical_entry_quality") or {}
        fusion = state.get("fusion6") or {}
        live = state.get("live_market") or {}
        return {
            "master": {"decision": master.get("decision"), "state": {key: master_state.get(key) for key in ("btc_price", "regime", "timing", "risk", "distribution", "support", "value", "drawdown")}},
            "macro7": {
                "actions": macro.get("actions"), "cycle": macro.get("cycle"), "zones": macro.get("zones"), "scenarios": macro.get("scenarios"),
                "indicators": macro.get("indicators"), "waiting_for": macro.get("waiting_for"), "why": macro.get("why"),
                "elliott": {key: elliott.get(key) for key in ("primary", "alternatives", "explanation", "quality", "status")},
                "production_impact": macro.get("production_impact"), "execution": macro.get("execution"),
            },
            "historical_context": {key: historical.get(key) for key in ("score", "state", "closest_historical_entries", "active_factors", "missing_factors")},
            "fusion6": {key: fusion.get(key) for key in ("regime", "decision", "signals", "active_historical_patterns", "risk", "status")},
            "data_status": state.get("data_status") or state.get("modules"),
            "live_market": {key: live.get(key) for key in ("status", "tick", "divergence", "last_confirmed_h4", "last_confirmed_d1", "timing_confirmation", "provenance")},
            "execution": "DISABLED",
        }

    @staticmethod
    def _all_numbers(value: Any) -> set[float]:
        found: set[float] = set()
        if isinstance(value, dict):
            for item in value.values(): found.update(BitcoinAIRouter._all_numbers(item))
        elif isinstance(value, list):
            for item in value: found.update(BitcoinAIRouter._all_numbers(item))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            found.add(round(float(value), 2))
        return found

    def _guard(self, text: str, grounded: dict) -> tuple[bool, str | None, str, str]:
        if "macro7" not in grounded and "master" in grounded:
            grounded = self.grounded_state(grounded)
        lower = text.lower()
        actions = grounded.get("macro7", {}).get("actions") or {}
        production = str((grounded.get("master", {}).get("decision") or {}).get("production_signal", ""))
        scenarios = grounded.get("macro7", {}).get("scenarios") or []
        forbidden = ("garantiert", "sicherer gewinn", "unbedingt kaufen", "order ausführen", "execute order")
        if any(x in lower for x in forbidden):
            return False, "ORDER_OR_CERTAINTY_LANGUAGE", "FAILED", "PASSED"
        if (actions.get("long_swing") == "WAIT" or production in {"NO_PRODUCTION_SIGNAL", "NONE", "DISABLED"}) and re.search(r"\b(jetzt kaufen|sofort kaufen|strong buy|buy now)\b", lower):
            return False, "CONTRADICTS_LONG_SWING_WAIT", "FAILED", "PASSED"
        dormant = [str(x.get("name", "")).lower() for x in scenarios if x.get("status") == "DORMANT"]
        if any(name and name in lower for name in dormant) and not re.search(r"bedingt|dormant|inaktiv|nur falls|szenario", lower):
            return False, "DORMANT_SCENARIO_NOT_CONDITIONAL", "FAILED", "PASSED"
        allowed = self._all_numbers(grounded)
        for match in re.findall(r"(?:\$|USD\s*)\s*([0-9][0-9.,]*)", text, re.I):
            normalized = match.replace(".", "").replace(",", ".") if "," in match and "." in match else match.replace(",", "")
            try: price = round(float(normalized), 2)
            except ValueError: continue
            if price not in allowed:
                return False, "HALLUCINATED_PRICE", "PASSED", "FAILED"
        for match in re.findall(r"(?:invalidation|confirmation|invalidierung|bestätigung)(?:slevel|spreis| level)?\D{0,12}([0-9]{4,}(?:[.,][0-9]+)?)", text, re.I):
            level = round(float(match.replace(",", ".")), 2)
            if level not in allowed: return False, "ELLIOTT_LEVEL_NOT_GROUNDED", "PASSED", "FAILED"
        if re.search(r"\b(wahrscheinlichkeit|probability|chance of)\b", lower):
            return False, "UNSUPPORTED_PROBABILITY", "PASSED", "FAILED"
        data_status = grounded.get("data_status") or {}
        unsupported = {"etf": ("etf inflow", "etf-zufluss", "etf zufluss"), "macro": ("macro is supportive", "makro ist unterstützend"), "news": ("news are positive", "positive nachrichten")}
        for name, phrases in unsupported.items():
            if (data_status.get(name) or {}).get("status") != "AVAILABLE" and any(x in lower for x in phrases):
                return False, "CLAIM_FROM_MISSING_DATA", "PASSED", "FAILED"
        return True, None, "PASSED", "PASSED"

    @staticmethod
    def _output_text(payload: dict) -> str:
        parts = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    parts.append(content["text"])
        return "\n".join(parts).strip()

    def explain(self, role: str, state: dict, deep: bool = False, bypass_cache: bool = False) -> AIResult:
        role = role.upper()
        role = "ANALYSIS" if role == "MINI" else role
        model = self.models.get(role)
        fallback = self.deterministic_summary(state)
        if not self.enabled: return AIResult("FALLBACK", fallback, reason="OPENAI_DISABLED")
        if not self.key or not model: return AIResult("FALLBACK", fallback, reason="MODEL_OR_KEY_MISSING")
        if not self._budget_available(): return AIResult("FALLBACK", fallback, model, reason="DAILY_COST_LIMIT_REACHED")
        grounded = self.grounded_state(state)
        cache_state = deepcopy(grounded)
        live_tick = (cache_state.get("live_market") or {}).get("tick") or {}
        if role == "ANALYSIS":
            cache_state.get("live_market", {}).pop("tick", None)
        else:
            cache_state["live_market"]["tick"] = {"mid_bucket_100": None if live_tick.get("mid") is None else round(float(live_tick["mid"]) / 100) * 100, "freshness": live_tick.get("freshness")}
        state_hash = hashlib.sha256(json.dumps(cache_state, default=str, sort_keys=True).encode()).hexdigest()
        cache_key = hashlib.sha256(f"{state_hash}|{model}|live-acceptance-v2|{deep}".encode()).hexdigest()
        target = self.cache_dir / f"{cache_key}.json"
        if target.exists() and not bypass_cache:
            payload = json.loads(target.read_text(encoding="utf-8")); self._record(model, 0, 0, True, role, 0, state_hash, "CACHE_HIT", "PASSED", False)
            return AIResult("AVAILABLE", payload["text"], model, True, contradiction_guard="PASSED", hallucination_guard="PASSED")
        if role == "NANO":
            task = "Fasse den strukturierten Bitcoin-State auf Deutsch in genau 2 bis 4 Sätzen als reinen Fließtext zusammen. Kein JSON, keine Liste."
            max_tokens = 250
        else:
            task = ("Analysiere auf Deutsch mit den Abschnitten Macro Cycle, Long Swing, Timing, Risk, Elliott, Bull Case, Bear Case, "
                    "Deep-Bear Scenario, Historical Context und Activation/Invalidation Conditions. Schreibe kompaktes Markdown, kein JSON, höchstens 700 Wörter.")
            max_tokens = 1800
        rules = ("Du bist ausschließlich eine Erklärungsschicht. Verwende nur das JSON. Erfinde keine Signale, Preise, Levels, News oder Wahrscheinlichkeiten. "
                 "MASTER und MACRO7 sind bindend. Bei LONG SWING=WAIT darfst du keinen Kauf empfehlen. DORMANT-Szenarien sind nur bedingte, inaktive Szenarien. "
                 "Keine Orders. Execution ist DISABLED. " + task)
        messages = [{"role": "developer", "content": rules}, {"role": "user", "content": json.dumps(grounded, ensure_ascii=False, default=str)}]
        use_chat = model.endswith("-chat-latest")
        body = ({"model": model, "messages": messages, "max_completion_tokens": max_tokens}
                if use_chat else {"model": model, "input": messages, "max_output_tokens": max_tokens})
        try:
            endpoint = "chat/completions" if use_chat else "responses"
            response = self._request("post", f"{self.API}/{endpoint}", headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}, json=body, timeout=120)
            if not response.ok:
                try:
                    error = response.json().get("error", {})
                    detail = error.get("code") or error.get("type") or error.get("message")
                except Exception:
                    detail = None
                reason = f"HTTP_{response.status_code}:{detail or 'API_ERROR'}"; self._record(model, 0, 0, False, role, 0, state_hash, reason, "NOT_RUN", True)
                return AIResult("FALLBACK", fallback, model, reason=reason)
            payload = response.json()
            if use_chat:
                text = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                raw_usage = payload.get("usage", {})
                usage = {"input_tokens": raw_usage.get("prompt_tokens", 0), "output_tokens": raw_usage.get("completion_tokens", 0), "input_tokens_details": raw_usage.get("prompt_tokens_details", {})}
            else:
                text = self._output_text(payload); usage = payload.get("usage", {})
            input_tokens = int(usage.get("input_tokens", 0)); output_tokens = int(usage.get("output_tokens", 0)); cost = self._cost(model, usage)
            if payload.get("status") == "incomplete":
                self._record(model, input_tokens, output_tokens, False, role, cost, state_hash, "INCOMPLETE_RESPONSE", "NOT_RUN", True)
                return AIResult("FALLBACK", fallback, model, reason="INCOMPLETE_RESPONSE", input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost_usd=cost, response_id=payload.get("id"))
            ok, reason, contradiction, hallucination = self._guard(text, grounded)
            self._record(model, input_tokens, output_tokens, False, role, cost, state_hash, "AVAILABLE", f"{contradiction}/{hallucination}", not ok or not text)
            if not ok or not text:
                return AIResult("REJECTED_FALLBACK", fallback, model, reason=reason or "EMPTY_RESPONSE", input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost_usd=cost, contradiction_guard=contradiction, hallucination_guard=hallucination, response_id=payload.get("id"))
            target.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
            return AIResult("AVAILABLE", text, model, input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost_usd=cost, contradiction_guard=contradiction, hallucination_guard=hallucination, response_id=payload.get("id"))
        except Exception as exc:
            self._record(model, 0, 0, False, role, 0, state_hash, type(exc).__name__, "NOT_RUN", True)
            return AIResult("FALLBACK", fallback, model, reason=type(exc).__name__)
