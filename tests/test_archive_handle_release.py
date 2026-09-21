"""Archive verification must not leave the file open (WinError 32), 2026-09-21.

archive.verify_archive() and archive.archive_segment() called
pq.read_table(<path>), letting pyarrow open the file itself. The resulting OS
handle is owned by Arrow-side objects that CPython's refcounting does not
release deterministically - they are reclaimed by the cyclic collector, so the
handle can outlive the call. verify_archive() is called by retain_segment() and
expire_archive() immediately before those delete the very file just verified,
and archive_segment() round-trip reads `temp` before os.replace() renames it to
`target`, so a handle leaked there follows the file onto its final name.

On Windows that intermittently produced
`PermissionError: [WinError 32] ... being used by another process` on the
following unlink/replace. Measured on this host: tests/test_waverun_storage_policy.py
failed 5 of 5 runs before the fix (which test failed varied between runs) and
passed 10 of 10 after it. Forcing gc.collect() before the unlink also cleared
it, which is what identified an uncollected cycle rather than a live reference
as the holder.

HONEST SCOPE OF THESE TESTS: they pin the *invariant* the fix establishes - the
handle is gone once the call returns, without relying on a garbage-collection
pass. They are NOT a deterministic reproduction of the original race, and they
pass on the unfixed code too: the leak only manifests under allocation/timing
conditions that could not be reproduced in isolation (merely adding diagnostic
code to the failing path was enough to make it vanish). The real regression
guard for this bug remains the pass rate of tests/test_waverun_storage_policy.py.
"""
from __future__ import annotations

import gc
import json
import os

import pytest

pytest.importorskip("pyarrow")

from bitcoin_cycle_analyzer.short_term.archive import archive_segment, verify_archive


def _segment(tmp_path, name="seg0001", rows=200):
    """A raw .jsonl segment in the shape archive_segment() expects."""
    raw = tmp_path / f"{name}.jsonl"
    with raw.open("wb") as handle:
        for i in range(rows):
            handle.write(json.dumps({"source": "BINANCE_SPOT", "received_at": 1_790_000_000.0 + i,
                                     "payload": "x" * 64}).encode() + b"\n")
    return raw


@pytest.fixture()
def no_cyclic_gc():
    """Disable the cyclic collector, so only a deterministically released
    handle can satisfy the assertions below."""
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def test_archive_can_be_deleted_immediately_after_verification(tmp_path, no_cyclic_gc):
    """verify_archive() then unlink, with no collection in between - the exact
    sequence retain_segment() and expire_archive() perform."""
    manifest = archive_segment(_segment(tmp_path))
    archive = tmp_path / manifest["filename"]

    verify_archive(archive)
    os.unlink(archive)
    assert not archive.exists()


def test_archive_can_be_deleted_immediately_after_creation(tmp_path, no_cyclic_gc):
    """archive_segment()'s round-trip read must not leave a handle that follows
    the file through os.replace() onto the final archive name."""
    manifest = archive_segment(_segment(tmp_path, "seg0002"))
    archive = tmp_path / manifest["filename"]

    os.unlink(archive)
    assert not archive.exists()


def test_repeated_verify_then_delete_never_leaks(tmp_path, no_cyclic_gc):
    """One maintenance pass verifies the same archive more than once (via
    retain_segment and then expire_archive), so the handle must be released
    every time, not only on the first call."""
    for index in range(5):
        manifest = archive_segment(_segment(tmp_path, f"seg01{index:02d}"))
        archive = tmp_path / manifest["filename"]
        verify_archive(archive)
        verify_archive(archive)
        os.unlink(archive)
        assert not archive.exists()


def test_verification_still_reads_the_real_contents(tmp_path):
    """Closing the handle early must not weaken what verify_archive checks: the
    Table is already in memory, so every field is still validated."""
    manifest = archive_segment(_segment(tmp_path, "seg0003"))
    archive = tmp_path / manifest["filename"]

    verified = verify_archive(archive)
    assert verified["records"] == 200
    assert verified["verification"] == "VERIFIED_ARCHIVE"
    assert verified["raw_checksum"] == manifest["raw_checksum"]
    assert verified["schema"] == manifest["schema"]


def test_corrupted_archive_is_still_rejected(tmp_path):
    """The deterministic close must not turn verification into a no-op."""
    manifest = archive_segment(_segment(tmp_path, "seg0004"))
    archive = tmp_path / manifest["filename"]

    archive.write_bytes(archive.read_bytes()[:-64] + b"\x00" * 64)
    with pytest.raises(Exception):
        verify_archive(archive)
