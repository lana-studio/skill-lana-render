"""tests/test_font_licenses.py — the copyright notices in assets/fonts/MANIFEST.json
and assets/fonts/OFL.txt must match what's actually embedded in the TTF binaries.

B-02 (2026-09-17): 3 of 5 notes were wrong in BOTH files (Montserrat's authors name
absorbed the ".git" from a clone URL; Poppins carried a stale release-era notice;
Playfair Display lost its Reserved Font Name clause — an operative OFL clause, not
decoration), because they were written from memory / a web page instead of read from
the binary. This is the exact same failure class as the "3 of 5 wrong from memory"
incident that made "no generar texto de licencia, verificar por contenido" a standing
rule for this feature — copyright notices get the same discipline as license bodies:
read from source, never recalled.

nameID 0 (the Copyright Notice, OpenType 'name' table) is the source of truth here —
it's literally what each font's own creator embedded in the binary. No fontTools
dependency: CI only `pip install`s pytest (see .github/workflows/check.yml), so this
parses the sfnt 'name' table directly with stdlib `struct` (verified byte-for-byte
against `fontTools.ttLib.TTFont(...).​['name'].getName(0, 3, 1, 0x409)` while writing
this test — output was identical for all 5 fonts in this directory).
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from conftest import REPO_ROOT

FONTS_DIR = REPO_ROOT / "lana-reel" / "assets" / "fonts"
MANIFEST_PATH = FONTS_DIR / "MANIFEST.json"
OFL_PATH = FONTS_DIR / "OFL.txt"


def read_copyright_nameid0(path: Path) -> str:
    """Return nameID 0 (Copyright Notice) from an sfnt 'name' table, decoded.

    Prefers the Windows/Unicode-BMP/en-US record (platform 3, encoding 1,
    language 0x409) — what fontTools.getName(0, 3, 1, 0x409) returns and what
    every font in this directory actually carries — then falls back to any
    platform-3 record, then Macintosh (platform 1, Mac Roman), then whatever
    nameID-0 record exists at all. Raises if the table or the record is missing
    (a font with no Copyright Notice at all is its own finding, not silently
    passed over).
    """
    data = path.read_bytes()
    (num_tables,) = struct.unpack_from(">H", data, 4)
    tables: dict[bytes, tuple[int, int]] = {}
    off = 12
    for _ in range(num_tables):
        tag, _checksum, offset, length = struct.unpack_from(">4sIII", data, off)
        tables[tag] = (offset, length)
        off += 16
    if b"name" not in tables:
        raise ValueError(f"{path}: no 'name' table")
    name_off, _name_len = tables[b"name"]
    _fmt, count, string_offset = struct.unpack_from(">HHH", data, name_off)
    storage = name_off + string_offset

    records = []
    roff = name_off + 6
    for _ in range(count):
        platform_id, encoding_id, language_id, name_id, length, offset = struct.unpack_from(
            ">HHHHHH", data, roff
        )
        records.append((platform_id, encoding_id, language_id, name_id, length, offset))
        roff += 12

    def decode(rec: tuple[int, int, int, int, int, int]) -> str:
        platform_id, _encoding_id, _language_id, _name_id, length, offset = rec
        raw = data[storage + offset : storage + offset + length]
        if platform_id in (0, 3):  # Unicode, Windows -> UTF-16BE
            return raw.decode("utf-16-be")
        if platform_id == 1:  # Macintosh -> Mac Roman
            return raw.decode("mac-roman")
        return raw.decode("latin-1")

    copyright_records = [r for r in records if r[3] == 0]
    if not copyright_records:
        raise ValueError(f"{path}: no nameID=0 (Copyright Notice) record")

    for platform_id, encoding_id, language_id in ((3, 1, 0x409), (3, 1, None), (1, 0, 0), (1, 0, None)):
        for rec in copyright_records:
            if rec[0] == platform_id and rec[1] == encoding_id and (language_id is None or rec[2] == language_id):
                return decode(rec)
    return decode(copyright_records[0])


def _manifest_by_file() -> dict[str, dict]:
    entries = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {e["file"]: e for e in entries}


def _font_files() -> list[Path]:
    return sorted(FONTS_DIR.glob("*.ttf")) + sorted(FONTS_DIR.glob("*.otf"))


@pytest.mark.parametrize("font_path", _font_files(), ids=lambda p: p.name)
def test_manifest_copyright_matches_binary_nameid0(font_path):
    """MANIFEST.json's "copyright" field, plus its "source_url" put back in
    parentheses where nameID0 embeds it, must reconstruct nameID0 exactly."""
    manifest = _manifest_by_file()
    entry = manifest[font_path.name]
    embedded = read_copyright_nameid0(font_path)

    source_url = entry["source_url"]
    # nameID0's shape is "<copyright...> (<url>)[, with Reserved Font Name ...]" —
    # the url parenthetical sits right after the copyright statement, with any
    # trailing clause (e.g. Playfair's RFN) appended after it, not before. So
    # rebuild by inserting " (<url>)" right after entry["copyright"]'s own
    # copyright-statement prefix, i.e. assert removing " (<url>)" from nameID0
    # gives back exactly entry["copyright"] — same check, the direction that
    # doesn't require guessing where the RFN clause starts.
    assert embedded.replace(f" ({source_url})", "", 1) == entry["copyright"], (
        f"{font_path.name}: MANIFEST.json copyright/source_url don't reconstruct "
        f"the binary's nameID0.\n  binary:   {embedded!r}\n  manifest: "
        f"{entry['copyright']!r} + source_url {source_url!r}"
    )


def _ofl_copyright_lines() -> list[str]:
    """The copyright block is everything between the "Copyright notices, one
    per family:" line and the next blank line — one line per font, nothing
    else. Returned as a list (not joined text) so a comparison against it is
    exact per-line equality, never substring containment."""
    lines = OFL_PATH.read_text(encoding="utf-8").splitlines()
    marker = next(i for i, l in enumerate(lines) if "Copyright notices" in l)
    start = marker + 1
    while start < len(lines) and not lines[start].strip():
        start += 1  # skip the blank separator line right after the marker
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    return lines[start:end]


@pytest.mark.parametrize("font_path", _font_files(), ids=lambda p: p.name)
def test_ofl_txt_has_verbatim_nameid0_line(font_path):
    """Every line in OFL.txt's copyright block must be LITERALLY EQUAL to some
    font's nameID0 — not "contains", not normalized, no tolerance. A
    paraphrase (missing the URL, an added "(c)", a stale release year) is
    exactly what let 2 of the 5 fonts drift unnoticed before B-02's rescope:
    the OFL license text plus these notices IS the license, so this is
    operative text (e.g. Playfair Display's Reserved Font Name clause), not
    documentation of it."""
    embedded = read_copyright_nameid0(font_path)
    ofl_lines = _ofl_copyright_lines()
    assert embedded in ofl_lines, (
        f"{font_path.name}: no line in OFL.txt's copyright block is literally "
        f"equal to the binary's nameID0.\n  expected verbatim: {embedded!r}\n"
        f"  OFL.txt block:    {ofl_lines!r}"
    )


def test_ofl_txt_copyright_block_has_exactly_one_line_per_font():
    """Catches a stale line nobody's per-font test would see: one extra line
    (a font that was removed) or a duplicate would pass every parametrized
    equality check above while still being wrong."""
    ofl_lines = _ofl_copyright_lines()
    assert len(ofl_lines) == len(_font_files()), (len(ofl_lines), len(_font_files()))
    assert len(ofl_lines) == len(set(ofl_lines)), "duplicate copyright line in OFL.txt"


def test_every_manifest_entry_has_a_font_file():
    """Catches the inverse drift: a manifest entry for a file that no longer
    ships, or a copyright note nobody will ever check because check_clean.py's
    font-not-allowlisted rule only walks actual files, never the manifest."""
    manifest = _manifest_by_file()
    on_disk = {p.name for p in _font_files()}
    assert set(manifest) == on_disk, (manifest.keys(), on_disk)
