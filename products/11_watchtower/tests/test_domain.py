import pytest

from watchtower.domain import (
    BACKPORTED,
    UPSTREAM_AT_OR_ABOVE,
    Advisory,
    OutOfScopeError,
    Package,
    Verdict,
    assess,
    false_positive_rate,
    in_scope,
    revision,
    upstream,
)

SCOPE = {"workstation.local", "nas.local"}


def test_an_authorised_host_passes():
    assert in_scope("nas.local", SCOPE) == "nas.local"


def test_an_unauthorised_host_is_refused_not_warned_about():
    with pytest.raises(OutOfScopeError):
        in_scope("someone-elses-box.example.com", SCOPE)


def test_versions_compare_numerically_not_lexically():
    assert upstream("1.10.0") > upstream("1.9.0")


def test_the_distribution_suffix_is_kept_separately():
    assert upstream("1.2.3-4ubuntu1.2") == (1, 2, 3)
    assert revision("1.2.3-4ubuntu1.2") == "-4ubuntu1.2"


def test_an_unreadable_version_is_refused():
    with pytest.raises(ValueError):
        upstream("unknown")


def test_a_package_past_the_fix_is_not_vulnerable():
    v = assess(Package("openssl", "3.0.9"), Advisory("CVE-1", "openssl", "3.0.8"))
    assert v == Verdict(False, UPSTREAM_AT_OR_ABOVE)


def test_a_package_below_the_fix_is_vulnerable():
    assert assess(Package("openssl", "3.0.2"), Advisory("CVE-1", "openssl", "3.0.8")).vulnerable


def test_a_backport_clears_a_package_the_version_string_condemns():
    # The finding: upstream 3.0.2 looks three releases behind and is patched.
    advisory = Advisory("CVE-1", "openssl", "3.0.8", {"jammy": "3.0.2-0ubuntu1.10"})
    package = Package("openssl", "3.0.2-0ubuntu1.12", release="jammy")
    verdict = assess(package, advisory)
    assert not verdict.vulnerable
    assert verdict.reason == BACKPORTED


def test_an_older_backport_revision_is_still_vulnerable():
    advisory = Advisory("CVE-1", "openssl", "3.0.8", {"jammy": "3.0.2-0ubuntu1.10"})
    package = Package("openssl", "3.0.2-0ubuntu1.1", release="jammy")
    assert assess(package, advisory).vulnerable


def test_a_backport_for_another_release_does_not_apply():
    advisory = Advisory("CVE-1", "openssl", "3.0.8", {"jammy": "3.0.2-0ubuntu1.10"})
    package = Package("openssl", "3.0.2-0ubuntu1.12", release="focal")
    assert assess(package, advisory).vulnerable


def test_an_advisory_for_a_different_package_never_matches():
    assert not assess(Package("curl", "7.0"), Advisory("CVE-1", "openssl", "3.0.8")).vulnerable


def test_the_false_positive_rate_is_the_headline_number():
    naive = [Verdict(True, ""), Verdict(True, ""), Verdict(False, "")]
    checked = [Verdict(False, ""), Verdict(True, ""), Verdict(False, "")]
    assert false_positive_rate(naive, checked) == pytest.approx(0.5)


def test_two_runs_must_cover_the_same_findings():
    with pytest.raises(ValueError):
        false_positive_rate([Verdict(True, "")], [])
