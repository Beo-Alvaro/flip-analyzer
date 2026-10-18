"""Tests for the one-click comp searches (flip.find_comps)."""

from urllib.parse import parse_qs, urlparse

from flip.find_comps import LISTING_SITES, search_links


def query(url, name):
    return parse_qs(urlparse(url).query)[name][0]


def test_search_links():
    links = dict(search_links("  Jade Residences   Imus "))

    assert list(links) == ["Facebook Marketplace", "Facebook posts and groups",
                           "Listing sites, via Google", "Resale words, via Google"]
    assert query(links["Facebook Marketplace"], "query") == "Jade Residences Imus"
    assert query(links["Facebook posts and groups"], "q") == "Jade Residences Imus for sale"
    google = query(links["Listing sites, via Google"], "q")
    assert google.startswith("Jade Residences Imus for sale (site:lamudi.com.ph OR ")
    assert all(f"site:{site}" in google for site in LISTING_SITES)
    assert query(links["Resale words, via Google"], "q") == (
        'Jade Residences Imus for sale (resale OR owner OR renovated OR "clean title")')
