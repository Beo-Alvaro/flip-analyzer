"""One-click searches for a house's comps.

The sites with the most resales (Facebook, Lamudi, OnePropertee...) block
automated reading or need you to log in, so the app doesn't read them.
Instead it opens ready-made searches in your own browser, where you are
logged in, and you paste what you find into Paste a listing.
"""

from urllib.parse import quote_plus

LISTING_SITES = ["lamudi.com.ph", "dotproperty.com.ph", "onepropertee.com", "carousell.ph",
                 "fazwaz.ph", "myproperty.ph"]
RESALE_WORDS = '(resale OR owner OR renovated OR "clean title")'


def search_links(query: str) -> list[tuple[str, str]]:
    """(label, address) for each search, e.g. for "Jade Residences Imus"."""
    query = " ".join(str(query).split())
    sites = " OR ".join(f"site:{site}" for site in LISTING_SITES)
    return [
        ("Facebook Marketplace",
         f"https://www.facebook.com/marketplace/search/?query={quote_plus(query)}"),
        ("Facebook posts and groups",
         f"https://www.facebook.com/search/posts/?q={quote_plus(query + ' for sale')}"),
        ("Listing sites, via Google",
         f"https://www.google.com/search?q={quote_plus(f'{query} for sale ({sites})')}"),
        ("Resale words, via Google",
         f"https://www.google.com/search?q={quote_plus(f'{query} for sale {RESALE_WORDS}')}"),
    ]
