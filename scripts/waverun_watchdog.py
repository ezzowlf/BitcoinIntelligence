"""Run after acceptance as the service entry point; never enables execution."""
import argparse
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from bitcoin_cycle_analyzer.short_term.process_watchdog import ProcessWatchdog

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime',type=Path,default=ROOT/'runtime/waverun')
    parser.add_argument('collector_args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    child_args=args.collector_args
    if child_args[:1]==['--']:child_args=child_args[1:]
    watcher=ProcessWatchdog(args.runtime,[sys.executable,str(ROOT/'scripts/waverun_live.py'),*child_args])
    try:
        while True:
            state=watcher.step()
            if state=='MANUAL_INTERVENTION_REQUIRED':return 2
            time.sleep(1)
    finally:watcher.close()

if __name__=='__main__':raise SystemExit(main())
