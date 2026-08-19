"""The CSV fallback may repair a truncated name, and nothing else.

IDX's stock-list endpoint clips Name at 30 characters. The live sync papers
over that by preferring the profiles endpoint, but that path 403s from a
datacenter IP — so a deployed instance runs entirely off the bundled snapshot
and inherits whatever the snapshot holds. When the snapshot carries the full
name and the database holds a clipped one, the fallback is allowed to restore
the missing tail.

It is allowed to do nothing else. These pin the boundary, because the guard
sits inside a code path whose whole point is that it does not overwrite.
"""

import pytest

from app.sync.universe import _is_truncation_of, sync_universe

# Only the last test needs an event loop; the rest are pure or read a file.


# ---------------------------------------------------------------------------
# the guard itself — pure, so no database needed
# ---------------------------------------------------------------------------


def test_repairs_a_name_clipped_at_thirty_characters():
    assert _is_truncation_of(
        "Abadi Nusantara Hijau Investam", "Abadi Nusantara Hijau Investama Tbk"
    )
    assert _is_truncation_of(
        "Bank Negara Indonesia (Persero", "Bank Negara Indonesia (Persero) Tbk"
    )


def test_ignores_case_because_idx_shouts_some_names():
    """APIC comes back as PACIFIC STRATEGIC FINANCIAL Tbk from profiles."""
    assert _is_truncation_of(
        "Pacific Strategic Financial Tb", "PACIFIC STRATEGIC FINANCIAL Tbk"
    )


def test_refuses_a_name_that_merely_differs():
    """The trap: a complete name that happens to be exactly 30 characters.

    "Akasha Wira International Tbk." is finished, not clipped. IDX's profile
    for it is the messier "Akasha Wira International Tbk  Tbk", and a
    length-based rule would have written that over a good value.
    """
    assert not _is_truncation_of(
        "Akasha Wira International Tbk.", "Akasha Wira International Tbk  Tbk"
    )
    # IDX's own prefix style is inconsistent; "PT X" is not a completion of "X".
    assert not _is_truncation_of(
        "Alamtri Minerals Indonesia Tbk", "PT Alamtri Minerals Indonesia Tbk"
    )
    # The profile is sometimes the ABBREVIATED one — never take a shorter name.
    assert not _is_truncation_of(
        "Argha Karya Prima Industry Tbk", "Argha Karya Prima Ind. Tbk"
    )


def test_refuses_equal_or_shorter_and_handles_empties():
    assert not _is_truncation_of("Astra Agro Lestari Tbk.", "Astra Agro Lestari Tbk.")
    assert not _is_truncation_of("Something Long Indeed Tbk", "Something")
    assert not _is_truncation_of("", "Anything At All")
    assert not _is_truncation_of("Anything At All", "")


# ---------------------------------------------------------------------------
# the shipped snapshot
# ---------------------------------------------------------------------------


def test_bundled_snapshot_is_no_longer_clipped_at_thirty():
    """Regression guard on the data file itself.

    The snapshot used to be generated straight from the stock-list endpoint,
    so every name in it stopped at 30 characters — max length 30, a pile-up of
    190 rows sitting exactly on the cap, and nothing beyond it. A distribution
    with a hard wall like that is the signature of the clip, and it is what a
    deployed instance would inherit wholesale.
    """
    import csv

    from app.sync.universe import CSV_PATH

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        names = [r["name"] for r in csv.DictReader(f) if r.get("ticker")]

    assert len(names) > 900
    longest = max(len(n) for n in names)
    assert longest > 30, (
        f"snapshot's longest name is {longest} chars — it looks clipped again; "
        "regenerate it with the profiles endpoint before shipping"
    )
    # A few known-long ones, so a partial regeneration cannot pass either.
    joined = set(names)
    assert "Bank Negara Indonesia (Persero) Tbk" in joined
    assert "Abadi Nusantara Hijau Investama Tbk" in joined


# ---------------------------------------------------------------------------
# where the data comes from
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_default_sync_never_contacts_idx(client, monkeypatch):
    """The default path must not reach for the network.

    This is a licensing guarantee, not a performance one. IDX's terms exclude
    obtaining their data by crawling, so the scheduled job was removed and the
    universe comes from the committed snapshot. A future edit that restores
    the live fetch as the default would be a silent regression — the app would
    keep working, look identical, and quietly resume the thing the terms
    exclude. So the test fails loudly instead of asserting on a log line.
    """
    called = False

    async def _boom():
        nonlocal called
        called = True
        raise AssertionError("sync_universe() reached for IDX without --from-idx")

    monkeypatch.setattr("app.sync.universe.fetch_universe", _boom)

    result = await sync_universe()

    assert called is False
    assert result.source == "csv-fallback"


def test_snapshot_names_are_house_style_not_idx_raw():
    """The shipped snapshot must not carry IDX's own formatting.

    IDX's profiles feed is inconsistent: some names gain a "PT " prefix the
    rest of this app never uses, and some arrive shouting
    ("PACIFIC STRATEGIC FINANCIAL Tbk"). The snapshot is normalised when it is
    regenerated, and this pins that — a regeneration that forgets to normalise
    would otherwise ship straight into the holdings table, where it looks far
    worse than the truncation it was meant to fix.
    """
    import csv

    from app.sync.universe import CSV_PATH

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        names = {r["ticker"]: r["name"] for r in csv.DictReader(f) if r.get("ticker")}

    pt = [t for t, n in names.items() if n.startswith("PT ")]
    assert not pt, f"snapshot carries IDX's 'PT ' prefix on {len(pt)}: {pt[:5]}"

    def shouting(n: str) -> bool:
        letters = [c for c in n if c.isalpha()]
        return len(letters) > 6 and sum(c.isupper() for c in letters) > 0.8 * len(letters)

    loud = [t for t, n in names.items() if shouting(n)]
    assert not loud, f"snapshot has ALL-CAPS names: {loud[:5]}"

    # The two that started this whole thread.
    assert names["APIC"] == "Pacific Strategic Financial Tbk"
    assert names["PACK"] == "Abadi Nusantara Hijau Investama Tbk"
