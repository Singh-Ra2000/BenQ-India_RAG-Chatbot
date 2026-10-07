"""
=====================================================
  BENQ FAQ CRAWLER v2 — Selenium powered
  Handles: Cookie popups, JavaScript content,
           Accordion FAQs, Individual answer pages
=====================================================
WHY v2?
  The old crawler used a basic method that could NOT
  handle JavaScript. BenQ's website loads content
  using JavaScript AFTER the page opens — so the old
  script only saw the cookie popup, not the real content.

  This version opens a REAL Chrome browser (just like
  you do manually), dismisses the cookie popup, then
  reads the actual FAQ content.

SETUP (run once in Command Prompt):
    pip install selenium

RUN:
    python crawl_faq.py
"""

import time
import os
import re
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException,
        ElementClickInterceptedException, StaleElementReferenceException
    )
except ImportError:
    print("❌  Selenium not installed!")
    print("    Run this in Command Prompt:  pip install selenium")
    input("\nPress Enter to close...")
    exit()


# ══════════════════════════════════════════════════════════
#
#   ✏️  ADD YOUR BENQ FAQ PAGE URLS HERE
#
#   These are the MAIN FAQ LIST pages for each projector model.
#   The script will find and visit every individual answer automatically.
#
#   How to find your FAQ page URL:
#   → Go to benq.com → Support → find your projector model → FAQ tab
#   → Copy that page's URL and paste it below
#
# ══════════════════════════════════════════════════════════

FAQ_PAGES = [

    {
        "url":    "https://www.benq.com/en-in/support/downloads-faq/products/projector/gv50/faq.html",
        "folder": "documents/post_sales",
        "label":  "BenQ GV50 FAQ",
    },

    {
        "url":    "https://www.benq.com/en-in/support/downloads-faq/products/projector/gv32/faq.html",
        "folder": "documents/post_sales",
        "label":  "BenQ GV32 FAQ",
    },

    # Add more models below — copy the block above and change URL + label:
    # {
    #     "url":    "https://www.benq.com/en-in/support/downloads-faq/products/projector/gp20/faq.html",
    #     "folder": "documents/post_sales",
    #     "label":  "BenQ GP20 FAQ",
    # },

]


# ══════════════════════════════════════════════════════════
#   SETTINGS
# ══════════════════════════════════════════════════════════

PAGE_LOAD_WAIT   = 5    # seconds to wait for each page to load
MIN_CONTENT_LEN  = 100  # skip pages with less than this many characters
MAX_FAQS         = 80   # max FAQ links to follow per model (safety limit)


# ══════════════════════════════════════════════════════════
#   ENGINE — do not edit below
# ══════════════════════════════════════════════════════════

def open_browser():
    """Open Chrome in a way that avoids bot detection."""
    options = Options()
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    # Hide the webdriver flag (reduces bot detection)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def dismiss_cookie_popup(driver):
    """
    Try to click the 'Accept Cookies' button if it appears.
    This is the popup that was blocking all the content before.
    """
    cookie_button_texts = [
        "Accept Cookies", "Accept All", "Accept all cookies",
        "Only Required Cookies", "I Accept", "OK"
    ]
    # Try by button text
    for text in cookie_button_texts:
        try:
            btn = driver.find_element(
                By.XPATH, f"//button[contains(text(), '{text}')]"
            )
            btn.click()
            time.sleep(1)
            return True
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    # Try by common CSS classes used for cookie accept buttons
    cookie_selectors = [
        ".cookie-accept", "#cookie-accept", ".accept-cookies",
        "[data-testid='cookie-accept']", ".js-accept-cookies",
        "button[class*='accept']", "button[class*='cookie']"
    ]
    for sel in cookie_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            btn.click()
            time.sleep(1)
            return True
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    return False  # No cookie popup found (that's fine too)


def get_faq_links_from_page(driver, base_url):
    """
    Find all the individual FAQ answer links on the FAQ list page.
    These are the links you'd normally click to read each answer.
    """
    links = driver.execute_script("""
        var results = [];
        var seen = new Set();
        var allLinks = document.querySelectorAll('a[href]');

        allLinks.forEach(function(a) {
            var href = a.href;
            if (!href || seen.has(href)) return;

            // Only keep links that look like FAQ answer pages
            var lower = href.toLowerCase();

            // Must be on benq.com
            if (!lower.includes('benq.com')) return;

            // Skip useless links
            var skip = ['javascript:', 'mailto:', '#', '/cart',
                        '/login', '/register', '/account',
                        '/sitemap', '.pdf', '.jpg', '.png',
                        'cookie', 'privacy', 'policy'];
            if (skip.some(function(s){ return lower.includes(s); })) return;

            // Must look like a FAQ/support/troubleshoot page
            var good = ['faq', 'support', 'troubleshoot', 'help',
                        'downloads-faq', 'projector-faq', 'kn-'];
            if (good.some(function(g){ return lower.includes(g); })) {
                seen.add(href);
                results.push(href);
            }
        });

        return results;
    """)
    return links or []


def expand_accordion_faqs(driver):
    """
    Some FAQ pages show Q&A on the SAME page using expandable sections.
    This clicks all of them open so we can read the answers.
    """
    clicked = driver.execute_script("""
        var count = 0;
        // Click anything with aria-expanded=false
        document.querySelectorAll('[aria-expanded="false"]').forEach(function(el) {
            try { el.click(); count++; } catch(e) {}
        });
        // Click collapsed accordion items
        document.querySelectorAll('.collapsed, .accordion-button.collapsed').forEach(function(el) {
            try { el.click(); count++; } catch(e) {}
        });
        return count;
    """)
    if clicked > 0:
        time.sleep(2)  # wait for animations
    return clicked


def extract_faq_content(driver):
    """
    Extract the actual Q&A content from the page.
    Specifically targets the answer content area, skips all navigation/cookie text.
    """
    content = driver.execute_script("""

        // Tags and classes to completely skip
        var SKIP_TAGS = new Set(['SCRIPT','STYLE','NAV','HEADER',
                                  'FOOTER','IFRAME','NOSCRIPT']);
        var SKIP_CLASSES = [
            'cookie', 'nav', 'menu', 'header', 'footer',
            'breadcrumb', 'sidebar', 'chat', 'banner',
            'social', 'share', 'related', 'recommend'
        ];

        function isBadElement(el) {
            if (!el || !el.tagName) return false;
            if (SKIP_TAGS.has(el.tagName)) return true;
            var c = String(el.className || '').toLowerCase();
            var id = String(el.id || '').toLowerCase();
            return SKIP_CLASSES.some(function(s) {
                return c.includes(s) || id.includes(s);
            });
        }

        // Try to find the specific answer/content container first
        var contentSelectors = [
            '.faq-answer', '.faq-content', '.answer-content',
            '[class*="faq-body"]', '[class*="answer"]',
            'article', 'main', '#main-content', '#content',
            '[class*="content-body"]', '[class*="page-content"]',
            '[role="main"]'
        ];

        var root = null;
        for (var i = 0; i < contentSelectors.length; i++) {
            var el = document.querySelector(contentSelectors[i]);
            if (el && el.innerText && el.innerText.trim().length > 100) {
                root = el;
                break;
            }
        }
        if (!root) root = document.body;

        // Walk only the good part of the page and collect text
        var lines = [];
        var walker = document.createTreeWalker(
            root, NodeFilter.SHOW_TEXT, null, false
        );

        var node;
        while ((node = walker.nextNode())) {
            // Check all parent elements — skip if any is bad
            var parent = node.parentElement;
            var bad = false;
            while (parent && parent !== root) {
                if (isBadElement(parent)) { bad = true; break; }
                parent = parent.parentElement;
            }
            if (bad) continue;

            var text = node.textContent.trim();
            if (text.length > 2 && text.length < 500) {
                lines.push(text);
            }
        }

        return lines.join('\\n');
    """)
    return content or ""


def clean_faq_text(raw, question_hint=""):
    """Remove cookie text, nav text, duplicates. Keep only real FAQ content."""

    # These phrases indicate we're reading noise, not content
    NOISE_PHRASES = [
        "cookie setting", "benq respect your data privacy",
        "strictly necessary cookies", "functional cookies",
        "performance cookies", "advertising cookies",
        "accept cookies", "only required cookies",
        "we use cookies", "privacy policy", "cookie policy",
        "hotjar", "sessioncam", "google analytics",
        "change language", "change region",
        "was this information helpful", "yes no",
        "thanks for your feedback", "inaccurate", "unclear",
        "sign in", "register", "add to cart", "buy now",
        "follow us", "linkedin", "facebook", "youtube",
        "copyright", "all rights reserved", "back to top",
        "price qty", "education", "news", "e-store",
        "show more", "show less", "find more"
    ]

    lines = raw.split('\n')
    cleaned = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        low = line.lower()
        # Skip if it matches any noise phrase
        if any(noise in low for noise in NOISE_PHRASES):
            continue
        # Skip pure navigation words
        if low in {"on", "off", "back", "next", "home", "top",
                   "projector", "monitor", "lighting", "support",
                   "overview", "spec", "faq", "buy"}:
            continue
        if line in seen:
            continue
        seen.add(line)
        cleaned.append(line)

    if not cleaned:
        return ""

    header = ""
    if question_hint:
        header = f"FAQ: {question_hint}\n{'─'*50}\n"

    return header + "\n".join(cleaned)


def get_page_title(driver):
    """Get the page title — this is usually the FAQ question."""
    try:
        # Try H1 first (most reliable for FAQ pages)
        h1 = driver.find_element(By.TAG_NAME, "h1")
        if h1.text.strip():
            return h1.text.strip()
    except Exception:
        pass
    try:
        return driver.title.replace(" | BenQ India", "").replace(" | BenQ", "").strip()
    except Exception:
        return ""


def save_text(text, folder, filename):
    Path(folder).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath


def make_filename(index, title):
    safe = re.sub(r'[^\w\s]', '', title or "faq").strip()
    safe = re.sub(r'\s+', '_', safe).lower()[:50]
    return f"{index:03d}_{safe}.txt"


def crawl_one_model(driver, entry, first_page):
    """Full crawl process for one projector model's FAQ page."""
    url    = entry["url"]
    folder = entry["folder"]
    label  = entry["label"]

    print(f"\n{'═'*56}")
    print(f"  📋  {label}")
    print(f"  🔗  {url}")
    print(f"{'═'*56}")

    # ── Step 1: Open the FAQ list page ─────────────────────
    print(f"\n  1️⃣   Opening FAQ list page...")
    driver.get(url)
    time.sleep(PAGE_LOAD_WAIT)

    # ── Step 2: Handle cookie popup (only need to do once) ──
    if first_page:
        print(f"  2️⃣   Dismissing cookie popup (if any)...")
        dismissed = dismiss_cookie_popup(driver)
        print(f"        → {'Cookie popup dismissed ✅' if dismissed else 'No popup found (OK)'}")
        time.sleep(1)
    else:
        print(f"  2️⃣   Cookie already accepted from previous page ✅")

    # ── Step 3: Expand accordion FAQs (if same-page style) ──
    print(f"  3️⃣   Expanding accordion Q&As on this page...")
    n_expanded = expand_accordion_faqs(driver)
    print(f"        → Expanded {n_expanded} section(s)")

    # Save the full FAQ list page itself (accordion content included)
    page_content = extract_faq_content(driver)
    page_clean   = clean_faq_text(page_content, label + " - Overview")
    if len(page_clean) > MIN_CONTENT_LEN:
        fp = save_text(page_clean, folder, "000_faq_overview.txt")
        print(f"        → Saved overview page → {fp}")

    # ── Step 4: Find all individual answer page links ───────
    print(f"\n  4️⃣   Finding individual answer page links...")
    faq_links = get_faq_links_from_page(driver, url)
    # Remove the current page from list
    faq_links  = [l for l in faq_links if l.rstrip('/') != url.rstrip('/')]
    faq_links  = list(dict.fromkeys(faq_links))  # deduplicate, keep order
    faq_links  = faq_links[:MAX_FAQS]
    print(f"        → Found {len(faq_links)} answer page(s) to visit")

    if not faq_links:
        print("        → All answers are on this page already (accordion style) ✅")
        return 1, 0

    # ── Step 5: Visit each answer page ─────────────────────
    print(f"\n  5️⃣   Visiting each answer page...\n")
    success = 0
    failed  = 0

    for i, link in enumerate(faq_links):
        print(f"  [{i+1}/{len(faq_links)}] Opening: {link.split('/')[-1]}")

        try:
            driver.get(link)
            time.sleep(PAGE_LOAD_WAIT)

            # Dismiss cookie on first sub-page too (just in case)
            if i == 0:
                dismiss_cookie_popup(driver)
                time.sleep(1)

            title   = get_page_title(driver)
            raw     = extract_faq_content(driver)
            cleaned = clean_faq_text(raw, title)

            if len(cleaned) < MIN_CONTENT_LEN:
                print(f"         ⚠️  Too little content ({len(cleaned)} chars) — skipping")
                failed += 1
                continue

            filename = make_filename(i + 1, title)
            filepath = save_text(cleaned, folder, filename)
            print(f"         ✅  '{title[:55]}...' → {filename}")
            success += 1

        except Exception as e:
            print(f"         ❌  Error: {e}")
            failed += 1

        time.sleep(2)   # be polite, don't hammer the server

    return success, failed


def main():
    print("\n" + "═"*56)
    print("  🤖  BenQ FAQ Crawler v2 — Selenium Powered")
    print("  Handles: Cookie popups + JavaScript content")
    print("  Result:  Real FAQ answers, no cookie noise!")
    print("═"*56)

    print("\n  🌐  Opening Chrome browser...")
    print("      (A browser window will appear — don't close it!)\n")

    try:
        driver = open_browser()
    except Exception as e:
        print(f"\n❌  Could not open Chrome: {e}")
        print("    Make sure Chrome is installed, then run:")
        print("    pip install --upgrade selenium")
        input("\nPress Enter to close...")
        return

    total_ok   = 0
    total_fail = 0

    for i, entry in enumerate(FAQ_PAGES):
        ok, fail = crawl_one_model(driver, entry, first_page=(i == 0))
        total_ok   += ok
        total_fail += fail

    driver.quit()

    print(f"\n{'═'*56}")
    print(f"  🏁  ALL DONE!")
    print(f"  ✅  {total_ok}  FAQ answer file(s) saved")
    print(f"  ❌  {total_fail} page(s) failed or had no content")
    print(f"{'═'*56}")
    print(f"\n  📁  Open your 'documents/post_sales/' folder")
    print(f"      Each .txt file = one FAQ answer, clean text only")
    print(f"\n  ▶️   Next step:  python ingest.py\n")

    input("Press Enter to close...")


if __name__ == "__main__":
    main()
