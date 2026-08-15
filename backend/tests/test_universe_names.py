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

from app.sync.universe import _is_truncation_of

# No asyncio mark: every test here is synchronous. The guard is a pure
# function and the snapshot check just reads a file, so neither needs a
# database or an event loop.


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
