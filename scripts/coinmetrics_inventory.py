from __future__ import annotations
import json
from pathlib import Path
import requests
import truststore


def main():
    truststore.inject_into_ssl()
    response=requests.get("https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics",params={"assets":"btc","page_size":10000},timeout=60)
    response.raise_for_status(); metrics=response.json()["data"][0]["metrics"]
    inventory=[]
    for item in metrics:
        for frequency in item.get("frequencies",[]):
            if frequency.get("community"):
                inventory.append({"name":item["metric"],"description":"See Coin Metrics metric reference",
                                  "start_date":frequency.get("min_time"),"end_date":frequency.get("max_time"),
                                  "frequency":frequency.get("frequency"),"coverage":"community","current_status":"AVAILABLE"})
    root=Path(__file__).resolve().parents[1]; output=root/"data"/"reports"/"coinmetrics_community_inventory.json"
    output.write_text(json.dumps({"count":len(inventory),"metrics":inventory},indent=2),encoding="utf-8")
    return {"count":len(inventory),"output":str(output)}


if __name__=="__main__": print(json.dumps(main(),indent=2))
