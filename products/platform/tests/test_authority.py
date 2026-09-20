import pytest

from agentplatform.authority import Applied, Level, NotAuthorisedError, Table


def table() -> Table:
    return (
        Table()
        .grant("enricher", "company.*", Level.WRITE)
        .grant("analyst", "deal.risk_factors", Level.WRITE)
        .grant("analyst", ("deal.amount", "deal.close_date"), Level.PROPOSE)
    )


def test_anything_not_granted_is_never():
    assert table().level_for("enricher", "deal.amount") is Level.NEVER


def test_a_new_field_is_closed_by_default():
    # The property that matters: adding a column to the schema must not
    # silently hand every agent write access to it.
    assert table().level_for("analyst", "deal.commission") is Level.NEVER


def test_prefix_grant_covers_its_fields():
    assert table().level_for("enricher", "company.headcount") is Level.WRITE


def test_check_raises_on_a_field_the_agent_may_never_touch():
    with pytest.raises(NotAuthorisedError):
        table().check("enricher", "deal.close_date")


def test_apply_splits_a_change_set_three_ways():
    out = table().apply(
        "analyst",
        {
            "deal.risk_factors": ["no reply 12d"],
            "deal.close_date": "2026-10-14",
            "contact.email": "a@b.co",
        },
    )
    assert out.written == {"deal.risk_factors": ["no reply 12d"]}
    assert out.proposed == {"deal.close_date": "2026-10-14"}
    assert out.refused == {"contact.email": "a@b.co"}


def test_an_entirely_refused_change_set_is_falsey():
    out = table().apply("enricher", {"deal.amount": 1})
    assert not out
    assert isinstance(out, Applied)
