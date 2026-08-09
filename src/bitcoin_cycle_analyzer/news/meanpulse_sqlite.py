from __future__ import annotations
import json
import sqlite3
import pandas as pd
from .ingestion import parse_meanpulse_event

CATEGORY_MAP={"central_bank":"FED","geopolitical":"WAR_ESCALATION","regulation":"REGULATION",
              "energy":"ENERGY_SHOCK","banking":"BANKING","inflation":"INFLATION","labor":"LABOR"}


def load_meanpulse_sqlite(path,as_of=None):
    """Read-only adapter; preserves story versions and never mutates MeanPulse."""
    con=sqlite3.connect(f"file:{path}?mode=ro",uri=True); con.row_factory=sqlite3.Row
    rows=con.execute("""SELECT s.story_id,s.canonical_title,s.first_seen,s.source_count,v.version,v.classification,v.created_at,
                        a.assessment_json FROM news_stories s JOIN news_story_versions v ON v.story_id=s.story_id
                        LEFT JOIN news_intelligence_assessments a ON a.story_id=v.story_id AND a.story_version=v.version
                        ORDER BY v.created_at""").fetchall(); events=[]
    for row in rows:
        assessment=json.loads(row["assessment_json"] or "{}")
        payload={"event_id":f"{row['story_id']}:v{row['version']}","event_time":row["first_seen"],"available_at":row["created_at"],
                 "category":CATEGORY_MAP.get(str(row["classification"]).lower(),"REGULATION"),"headline":row["canonical_title"],
                 "severity":min(1,float(assessment.get("urgency_score",0))/100),"risk_direction":"UNKNOWN",
                 "btc_direction":"UNKNOWN","confidence":float(assessment.get("confidence",0)),"source":"meanpulse-news",
                 "source_count":row["source_count"],"market_scope":assessment.get("affected_assets",[])}
        events.append(parse_meanpulse_event(payload))
    if as_of is not None: events=[event for event in events if event.available_at<=pd.Timestamp(as_of)]
    return events


def event_chains(events):
    chains={}
    for event in events:
        story_id=event.event.split(":v",1)[0]; chains.setdefault(story_id,[]).append(event)
    return {story:sorted(items,key=lambda event:event.available_at) for story,items in chains.items()}


def transmission_state(event):
    mapping={"war_escalation":{"oil":"UP_PRESSURE","inflation":"UP_PRESSURE","rates":"UNCERTAIN","risk_assets":"NEGATIVE_PRESSURE"},
             "energy":{"oil":"UP_PRESSURE","inflation":"UP_PRESSURE","rates":"UNCERTAIN","risk_assets":"MIXED"}}
    return {"event":event.category.value,**mapping.get(event.category.value,{}),"btc":"UNKNOWN","signal":"CONTEXT_ONLY"}
