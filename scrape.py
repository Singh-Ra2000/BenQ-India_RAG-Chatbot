"""
=====================================================
  WEB SCRAPER for Projector Chatbot Data Collection
  Works with: BenQ website, Amazon, any product page
=====================================================
HOW TO USE:
  1. Open this file in Notepad
  2. Scroll down to the section that says "ADD YOUR URLS HERE"
  3. Paste your BenQ / Amazon product page links
  4. Save and close Notepad
  5. Double-click this file to run (or run: python scrape.py)
"""

import time
import re
import os
from pathlib import Path
from urllib.request import urlopen, Request
from html.parser import HTMLParser

# ── Simple HTML text extractor (no extra libraries needed) ──
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip = False
        self.skip_tags = {"script", "style", "nav", "footer", "head", "iframe", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip = True

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            cleaned = data.strip()
            if cleaned:
                self.text_parts.append(cleaned)

    def get_text(self):
        return "\n".join(self.text_parts)


def fetch_page(url):
    """Download a webpage and return its text content."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")
        return html
    except Exception as e:
        print(f"  ❌  Could not fetch: {url}")
        print(f"      Reason: {e}")
        return None


def html_to_text(html):
    """Convert raw HTML into clean readable text."""
    extractor = TextExtractor()
    extractor.feed(html)
    text = extractor.get_text()
    # Remove duplicate blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def make_filename(url):
    """Turn a URL into a safe filename."""
    name = re.sub(r'https?://', '', url)
    name = re.sub(r'[^\w]', '_', name)
    name = name[:80]  # keep it short
    return name + ".txt"


def save_text(text, folder, filename):
    """Save text to a file in the given folder."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath


# ══════════════════════════════════════════════════════════
#
#   ✏️  ADD YOUR URLS HERE
#
#   Format:  ("URL",  "folder_name"),
#
#   Folder names to use:
#     "documents/pre_sales"   → specs, features, pricing, comparisons
#     "documents/post_sales"  → manuals, troubleshooting, setup guides
#     "documents/retailer"    → wholesale info, dealer pages
#     "documents/general"     → FAQs, support pages, about pages
#
#   Example:
#     ("https://www.benq.com/en-in/projector/gp20.html", "documents/pre_sales"),
#
# ══════════════════════════════════════════════════════════

URLS = [

    # ── BenQ Product Pages (Specs & Features) ──────────────
    # Paste your BenQ product URLs below, between the quotes

    # ("https://www.benq.com/en-in/projector/YOURMODEL.html", "documents/pre_sales"),
    # ("https://www.benq.com/en-in/projector/YOURMODEL/specs.html", "documents/pre_sales"),

    # ── Amazon Product Listings ─────────────────────────────
    # Paste your Amazon URLs below

    # ("https://www.amazon.in/dp/YOURASIN", "documents/pre_sales"),

    # ── BenQ Support / FAQ Pages ────────────────────────────

    # ("https://www.benq.com/en-in/support/...", "documents/post_sales"),

    # ── DELETE THE EXAMPLE LINES ABOVE AND ADD YOUR REAL URLS ──
    # Here are some examples to get you started — replace with your actual models:

    ("https://www.benq.com/en-in/projector/", "documents/pre_sales"),

]

# ══════════════════════════════════════════════════════════
#   DO NOT EDIT BELOW THIS LINE
# ══════════════════════════════════════════════════════════

def main():
    print("\n" + "═"*55)
    print("  🌐  Projector Chatbot — Web Scraper")
    print("═"*55)

    if not URLS:
        print("\n⚠️  No URLs found!")
        print("   Open this file in Notepad and add your URLs")
        print("   in the URLS section above.\n")
        return

    success = 0
    failed  = 0

    for i, entry in enumerate(URLS):
        url, folder = entry
        print(f"\n[{i+1}/{len(URLS)}] Fetching: {url}")

        html = fetch_page(url)
        if not html:
            failed += 1
            continue

        text = html_to_text(html)

        if len(text) < 100:
            print(f"  ⚠️  Page seems empty or blocked (got {len(text)} chars)")
            print(f"     Try saving this page manually with Ctrl+S in Chrome")
            failed += 1
            continue

        filename = make_filename(url)
        filepath = save_text(text, folder, filename)

        print(f"  ✅  Saved {len(text):,} characters → {filepath}")
        success += 1

        # Be polite — wait 2 seconds between requests
        # (avoids getting blocked by websites)
        if i < len(URLS) - 1:
            print("     ⏳ Waiting 2 seconds before next page...")
            time.sleep(2)

    print("\n" + "═"*55)
    print(f"  Done!  ✅ {success} saved   ❌ {failed} failed")
    print("═"*55)

    if failed > 0:
        print("\n  💡 For pages that failed, use the manual method:")
        print("     1. Open the page in Chrome")
        print("     2. Press Ctrl+S")
        print("     3. Save as 'Web Page, HTML Only'")
        print("     4. Drop the file into the correct folder\n")

    if success > 0:
        print("\n  📁 Your text files are saved in the 'documents' folder.")
        print("     Now run:  python ingest.py")
        print("     And your data will be ready for Step 2!\n")


if __name__ == "__main__":
    main()
    input("Press Enter to close...")   # keeps window open so you can read it
