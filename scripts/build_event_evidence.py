from __future__ import annotations
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"src"))
from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase
from bitcoin_cycle_analyzer.calendar_research import complete_calendar_study,black_friday_finding
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore

EVENTS=[
 {"event_time":"2020-03-03T15:00:00Z","first_known_at":"2020-03-03T15:00:00Z","available_at":"2020-03-03T15:00:00Z","source_url":"https://www.federalreserve.gov/newsevents/pressreleases/monetary20200303a.htm","source_name":"Federal Reserve","source_quality":"PRIMARY","category":"FED","headline":"FOMC lowers target range by 50 basis points","severity_at_time":"EXTRAORDINARY_INTERMEETING_ACTION"},
 {"event_time":"2020-03-15T21:00:00Z","first_known_at":"2020-03-15T21:00:00Z","available_at":"2020-03-15T21:00:00Z","source_url":"https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm","source_name":"Federal Reserve","source_quality":"PRIMARY","category":"MONETARY_POLICY","headline":"FOMC lowers target range to 0 to 1/4 percent","severity_at_time":"EXTRAORDINARY_INTERMEETING_ACTION"},
 {"event_time":"2021-09-03T00:00:00Z","first_known_at":"2021-09-03T00:00:00Z","available_at":"2021-09-03T00:00:00Z","source_url":"https://policy.mofcom.gov.cn/claw/clawContent.shtml?id=90896","source_name":"China Ministry of Commerce policy registry","source_quality":"PRIMARY","category":"REGULATION","headline":"China authorities publish virtual-currency mining rectification notice","severity_at_time":"NATIONAL_POLICY_NOTICE"},
 {"event_time":"2021-09-24T00:00:00Z","first_known_at":"2021-09-24T00:00:00Z","available_at":"2021-09-24T00:00:00Z","source_url":"https://www.gov.cn/zhengce/zhengceku/2021-10/08/content_5641404.htm","source_name":"State Council of China","source_quality":"PRIMARY","category":"REGULATION","headline":"China authorities further restrict virtual-currency trading activity","severity_at_time":"NATIONAL_POLICY_NOTICE"},
 {"event_time":"2023-03-10T16:15:00Z","first_known_at":"2023-03-10T16:15:00Z","available_at":"2023-03-10T16:15:00Z","source_url":"https://www.fdic.gov/news/press-releases/2023/pr23016.html","source_name":"FDIC","source_quality":"PRIMARY","category":"BANKING_CRISIS","headline":"FDIC appointed receiver for Silicon Valley Bank","severity_at_time":"BANK_CLOSURE"},
 {"event_time":"2023-03-12T22:15:00Z","first_known_at":"2023-03-12T22:15:00Z","available_at":"2023-03-12T22:15:00Z","source_url":"https://www.fdic.gov/news/press-releases/2023/pr23017.html","source_name":"FDIC Federal Reserve Treasury","source_quality":"PRIMARY","category":"BANKING_CRISIS","headline":"Authorities announce systemic-risk protections for SVB and Signature depositors","severity_at_time":"SYSTEMIC_RISK_EXCEPTION"},
 {"event_time":"2024-01-10T21:00:00Z","first_known_at":"2024-01-10T21:00:00Z","available_at":"2024-01-10T21:00:00Z","source_url":"https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023","source_name":"US SEC","source_quality":"PRIMARY","category":"ETF","headline":"SEC approves listing and trading of spot Bitcoin ETP shares","severity_at_time":"REGULATORY_APPROVAL"},
]
def main():
 config=load_config(root/"config.yaml");frame=OHLCVStore(root/config["data"]["database"]).load("1d");db=PointInTimeEventDatabase(root/"database"/"historical_event_evidence.db")
 for event in EVENTS:db.append(event)
 db.compute_reactions(frame);calendar=complete_calendar_study(frame);black_friday=black_friday_finding(frame)
 report={"event_db":db.health(),"calendar":calendar,"black_friday":black_friday,"unresolved_cases":["Mt. Gox contemporaneous primary timestamp","2017/2018 peak classification without hindsight","Terra/LUNA first-known incident timestamp","Celsius first-known withdrawal halt","FTX first-known insolvency evidence","Evergrande BTC-specific transmission","geopolitical escalation timestamp library"],"status":"RESEARCH_ONLY","execution":"DISABLED"}
 out=root/"data"/"reports"/"fusion6_event_evidence.json";out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,default=str),encoding="utf-8");print(json.dumps({"output":str(out),**db.health(),"black_friday":black_friday["conclusion"]},indent=2))
if __name__=="__main__":main()
