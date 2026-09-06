import json
import sys
from datetime import UTC,datetime

import pytest

from bitcoin_cycle_analyzer.short_term.journal import atomic_json
from bitcoin_cycle_analyzer.short_term.process_watchdog import ProcessWatchdog


class Child:
    pid=123
    def __init__(self):self.exit=None;self.terminated=False
    def poll(self):return self.exit
    def terminate(self):self.terminated=True;self.exit=0
    def kill(self):self.exit=-1
    def wait(self,timeout):return self.exit


def watcher(path,**kwargs):
    return ProcessWatchdog(path,['unused'],spawn=lambda env:Child(),**kwargs)


def test_restart_request_bound_to_owned_generation(tmp_path):
    w=watcher(tmp_path)
    try:
        assert w.step(100)=='STARTED';old=w.child
        atomic_json(tmp_path/'restart_request.json',{'boot_id':'foreign','request_id':'x'})
        assert w.step(101)=='RUNNING' and not old.terminated
        atomic_json(tmp_path/'restart_request.json',{'boot_id':w.boot_id,'request_id':'x'})
        assert w.step(102)=='RESTARTED' and old.terminated
        assert w.step(103)=='RUNNING'
    finally:w.close()


def test_health_writer_freeze_and_future_time_restart(tmp_path):
    w=watcher(tmp_path,grace=10,health_timeout=5)
    try:
        w.step(100)
        atomic_json(tmp_path/'health.json',{'boot_id':w.boot_id,'server_time':datetime.fromtimestamp(110,UTC).isoformat()})
        assert w.step(110)=='RUNNING'
        assert w.step(116)=='RESTARTED'
        atomic_json(tmp_path/'health.json',{'boot_id':w.boot_id,'server_time':datetime.fromtimestamp(200,UTC).isoformat()})
        assert w.step(130)=='RESTARTED'
    finally:w.close()


def test_restart_budget_survives_watchdog_restart_and_clock_rollback(tmp_path):
    w=watcher(tmp_path,budget=1);w.step(100);w.close()
    next_w=watcher(tmp_path,budget=1)
    try:assert next_w.step(90)=='MANUAL_INTERVENTION_REQUIRED'
    finally:next_w.close()


def test_single_process_owner(tmp_path):
    first=watcher(tmp_path);second=watcher(tmp_path)
    try:
        first.step(100)
        with pytest.raises(RuntimeError,match='another watchdog'):second.step(101)
    finally:first.close();second.close()


def test_real_child_is_restarted_and_old_child_reaped(tmp_path):
    w=ProcessWatchdog(tmp_path,[sys.executable,'-c','import time; time.sleep(30)'])
    try:
        assert w.step()=='STARTED';old=w.child
        atomic_json(tmp_path/'restart_request.json',{'boot_id':w.boot_id,'request_id':'real-process-test'})
        assert w.step()=='RESTARTED'
        assert old.poll() is not None and w.child.pid!=old.pid
    finally:w.close()
