"""
=====================================================
  BENQ SPEC SCRAPER v3
  Specifically handles BenQ's + button accordion pages
  e.g. Display +, Optical +, Picture +, I/O Interface +
=====================================================
SETUP (run once):
    pip install selenium

RUN:
    python spec_scraper.py
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
except ImportError:
    print("❌  Selenium not installed. Run:  pip install selenium")
    input("Press Enter to close...")
    exit()


# ══════════════════════════════════════════════════════════
#   ✏️  ADD YOUR BENQ SPEC PAGE URLS HERE
# ══════════════════════════════════════════════════════════

PAGES = [

    {
        "url":    "https://www.benq.com/en-in/projector/portable/gv32/spec.html",
        "folder": "documents/pre_sales",
        "label":  "BenQ GV32 Specifications",
    },

    # Add more — copy the block above and change URL + label:
    # {
    #     "url":    "https://www.benq.com/en-in/projector/portable/gv50/spec.html",
    #     "folder": "documents/pre_sales",
    #     "label":  "BenQ GV50 Specifications",
    # },

]


# ══════════════════════════════════════════════════════════
#   ENGINE
# ══════════════════════════════════════════════════════════

def open_browser():
    options = Options()
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def dismiss_cookie_popup(driver):
    """
    Try 5 different methods to find and click the Accept Cookies button.
    BenQ's cookie popup can appear in different ways — this covers all of them.
    """
    time.sleep(2)  # give popup time to fully appear

    # Method 1: Find button by visible text "Accept Cookies"
    try:
        btn = driver.find_element(
            By.XPATH,
            "//button[contains(text(),'Accept Cookies')]"
        )
        btn.click()
        time.sleep(1.5)
        print("        → Cookie accepted (Method 1 - button text) ✅")
        return True
    except Exception:
        pass

    # Method 2: Find any button with "Accept" in text
    try:
        btn = driver.find_element(
            By.XPATH,
            "//button[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'ACCEPT')]"
        )
        btn.click()
        time.sleep(1.5)
        print("        → Cookie accepted (Method 2 - any Accept button) ✅")
        return True
    except Exception:
        pass

    # Method 3: Find by common CSS class names BenQ uses
    cookie_selectors = [
        ".cookie-accept",
        ".accept-cookies",
        "#cookie-accept",
        "#acceptCookies",
        "[class*='accept-cookie']",
        "[class*='cookie-accept']",
        "[class*='cookieAccept']",
        "[id*='accept']",
    ]
    for sel in cookie_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            btn.click()
            time.sleep(1.5)
            print(f"        → Cookie accepted (Method 3 - CSS {sel}) ✅")
            return True
        except Exception:
            continue

    # Method 4: Use JavaScript to forcefully click any accept-looking button
    try:
        result = driver.execute_script("""
            var buttons = document.querySelectorAll('button, a, div[role="button"]');
            for (var i = 0; i < buttons.length; i++) {
                var txt = (buttons[i].innerText || buttons[i].textContent || '').trim();
                if (txt.toLowerCase().includes('accept') ||
                    txt.toLowerCase().includes('agree') ||
                    txt.toLowerCase().includes('allow all')) {
                    buttons[i].click();
                    return 'clicked: ' + txt;
                }
            }
            return null;
        """)
        if result:
            time.sleep(1.5)
            print(f"        → Cookie accepted (Method 4 - JS click: {result}) ✅")
            return True
    except Exception:
        pass

    # Method 5: Press Escape to close any modal popup
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
        print("        → Tried closing popup with Escape key")
    except Exception:
        pass

    print("        → No cookie popup found (this is OK — page may not need it)")
    return False


def slow_scroll(driver):
    """Scroll slowly so lazy-loaded content appears."""
    height = driver.execute_script("return document.body.scrollHeight")
    for pos in range(0, height, 250):
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(0.15)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)


def click_all_plus_buttons(driver):
    """
    BenQ spec pages use + icons on each section row (Display, Optical etc.)
    We try multiple approaches to click all of them open.
    Returns how many were clicked.
    """

    # Approach A: Use JavaScript to find and click collapsed items
    clicked_js = driver.execute_script("""
        var count = 0;

        // aria-expanded="false" is the most standard way to mark collapsed items
        document.querySelectorAll('[aria-expanded="false"]').forEach(function(el) {
            try { el.click(); count++; } catch(e) {}
        });

        // Some BenQ pages use a custom closed/open class
        var closedSelectors = [
            '.is-closed', '.is-collapsed', '.collapsed',
            '[class*="closed"]', '[class*="collapse"]:not([class*="show"])',
            'details:not([open])'
        ];
        closedSelectors.forEach(function(sel) {
            document.querySelectorAll(sel).forEach(function(el) {
                try { el.click(); count++; } catch(e) {}
            });
        });

        // data-toggle pattern
        document.querySelectorAll('[data-toggle="collapse"]').forEach(function(el) {
            try { el.click(); count++; } catch(e) {}
        });

        return count;
    """)

    time.sleep(1.5)  # wait for first wave of animations

    # Approach B: Find all rows that have a + looking button and click them
    # BenQ renders + as an SVG inside the row heading — we click the whole row
    clicked_rows = driver.execute_script("""
        var count = 0;

        // Look for any heading row that has a child with "+" in its text or an SVG
        // BenQ spec headings are often: <div class="..."> Display <svg>+</svg> </div>
        var candidates = document.querySelectorAll(
            'h2, h3, h4, h5, ' +
            '[class*="title"], [class*="heading"], [class*="header"], ' +
            '[class*="label"], [class*="category"], [class*="group"]'
        );

        candidates.forEach(function(el) {
            // Only click elements that sit inside a spec/accordion area
            var cls = String(el.className || '').toLowerCase();
            var parent = el.parentElement;
            var parentCls = parent ? String(parent.className || '').toLowerCase() : '';

            var looksLikeSpecRow = (
                cls.includes('spec') || cls.includes('accord') ||
                parentCls.includes('spec') || parentCls.includes('accord') ||
                el.querySelector('svg') !== null  // has an SVG icon (the + sign)
            );

            if (looksLikeSpecRow) {
                // Check it's not already open
                var expanded = el.getAttribute('aria-expanded');
                if (expanded !== 'true') {
                    try { el.click(); count++; } catch(e) {}
                }
            }
        });

        return count;
    """)

    time.sleep(2)   # wait for all animations to finish

    total = (clicked_js or 0) + (clicked_rows or 0)
    return total


def extract_spec_pairs(driver):
    """
    After all sections are expanded, extract every label: value pair.
    Works by walking the visible DOM and pairing adjacent text nodes.
    """

    result = driver.execute_script("""
        var pairs = [];

        // ── Method 1: definition list pairs (dt + dd) ──────────────
        var dts = document.querySelectorAll('dt');
        if (dts.length > 2) {
            dts.forEach(function(dt) {
                var label = dt.innerText.trim();
                var dd = dt.nextElementSibling;
                while (dd && dd.tagName !== 'DD') dd = dd.nextElementSibling;
                if (dd && label) {
                    pairs.push(label + ': ' + dd.innerText.trim());
                }
            });
        }

        // ── Method 2: 2-column table rows ──────────────────────────
        if (pairs.length < 3) {
            document.querySelectorAll('tr').forEach(function(row) {
                var cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    var label = cells[0].innerText.trim();
                    var value = cells[1].innerText.trim();
                    if (label && value && label.length < 100) {
                        pairs.push(label + ': ' + value);
                    }
                }
            });
        }

        // ── Method 3: BenQ-specific class pairs ─────────────────────
        // BenQ often uses sibling elements like:
        //   <span class="spec-label">Brightness</span>
        //   <span class="spec-value">500</span>
        if (pairs.length < 3) {
            var labelSelectors = [
                '[class*="spec-label"]', '[class*="specLabel"]',
                '[class*="spec-name"]',  '[class*="specName"]',
                '[class*="attr-name"]',  '[class*="feature-label"]',
                '[class*="prop-name"]',  '[class*="key"]'
            ];
            labelSelectors.forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(el) {
                    var label = el.innerText.trim();
                    var next = el.nextElementSibling;
                    if (next && label && label.length < 100) {
                        var val = next.innerText.trim();
                        if (val) pairs.push(label + ': ' + val);
                    }
                });
            });
        }

        // ── Method 4: Walk the whole page text smartly ──────────────
        // Skip nav/header/footer/cookie sections
        // Pair short lines (labels) with the next line (values)
        if (pairs.length < 3) {
            var SKIP = new Set(['SCRIPT','STYLE','NAV','HEADER',
                                'FOOTER','IFRAME','NOSCRIPT']);
            var SKIP_CLS = ['cookie','nav','menu','header','footer',
                            'breadcrumb','banner','chat','social'];

            function bad(el) {
                if (!el) return false;
                if (SKIP.has(el.tagName)) return true;
                var c = String(el.className || '').toLowerCase();
                var id = String(el.id || '').toLowerCase();
                return SKIP_CLS.some(function(s){
                    return c.includes(s) || id.includes(s);
                });
            }

            var root = document.querySelector('main, article, #main-content')
                       || document.body;

            var walker = document.createTreeWalker(
                root, NodeFilter.SHOW_TEXT, null, false
            );

            var texts = [];
            var node;
            while ((node = walker.nextNode())) {
                var p = node.parentElement;
                var skip = false;
                while (p && p !== root) {
                    if (bad(p)) { skip = true; break; }
                    p = p.parentElement;
                }
                if (skip) continue;
                var t = node.textContent.trim();
                if (t.length > 1 && t.length < 200) texts.push(t);
            }

            // Pair consecutive entries: label followed by value
            for (var i = 0; i < texts.length - 1; i++) {
                var a = texts[i];
                var b = texts[i+1];
                if (a.length < 80 && b.length <= 200 && !a.includes(':')) {
                    pairs.push(a + ': ' + b);
                    i++; // skip b, already used as value
                } else {
                    pairs.push(a);
                }
            }
        }

        return pairs.join('\\n');
    """)

    return result or ""


def clean_output(raw, label):
    """Remove nav/cookie noise and format the output nicely."""

    NOISE = [
        "cookie setting", "benq respect", "strictly necessary",
        "functional cookies", "performance cookies", "advertising cookies",
        "accept cookies", "only required", "privacy policy", "cookie policy",
        "hotjar", "sessioncam", "google analytics", "change language",
        "was this information helpful", "yes no", "thanks for",
        "sign in", "register", "add to cart", "buy now", "e-store",
        "follow us", "linkedin", "facebook", "youtube", "instagram",
        "copyright", "all rights reserved", "back to top",
        "show more", "show less", "education", "business", "news",
        "price qty", "overview", "find more", "applicable models"
    ]

    # Section headers from the page we WANT to keep
    SECTION_HEADERS = [
        "display", "optical", "picture", "compatibility",
        "i/o interface", "power", "mechanical", "audio",
        "connectivity", "general", "environment"
    ]

    lines  = raw.split('\n')
    output = []
    seen   = set()
    current_section = ""

    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue

        low = line.lower()

        # Skip noise
        if any(n in low for n in NOISE):
            continue

        # Skip pure single nav words
        if low in {"on", "off", "back", "next", "home", "top", "buy",
                   "spec", "faq", "overview", "projector", "monitor",
                   "lighting", "support", "menu", "search"}:
            continue

        # Detect section headers and format them nicely
        if low in SECTION_HEADERS or low.rstrip(':') in SECTION_HEADERS:
            current_section = line.title()
            output.append(f"\n[ {current_section} ]")
            seen.add(line)
            continue

        if line in seen:
            continue
        seen.add(line)
        output.append(line)

    header = (
        f"PRODUCT SPECIFICATIONS: {label}\n"
        f"{'=' * 55}\n"
        f"Source: BenQ India — benq.com\n"
        f"{'=' * 55}\n"
    )
    return header + "\n".join(output)


def save(text, folder, label):
    Path(folder).mkdir(parents=True, exist_ok=True)
    filename = re.sub(r'[^\w\s]', '', label).strip()
    filename = re.sub(r'\s+', '_', filename).lower() + ".txt"
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath


def scrape_page(driver, page, first):
    url    = page["url"]
    folder = page["folder"]
    label  = page["label"]

    print(f"\n  {'─'*54}")
    print(f"  📦  {label}")
    print(f"  🔗  {url}")
    print(f"  {'─'*54}")

    # 1. Open page
    print("  1️⃣   Opening page in Chrome...")
    driver.get(url)
    time.sleep(5)

    # 2. Cookie popup (only first page)
    if first:
        print("  2️⃣   Handling cookie popup...")
        dismiss_cookie_popup(driver)
    else:
        print("  2️⃣   Cookie already accepted ✅")

    # 3. Scroll to trigger lazy loading
    print("  3️⃣   Scrolling page to load all content...")
    slow_scroll(driver)

    # 4. Click ALL the + buttons
    print("  4️⃣   Clicking all + expand buttons...")
    n = click_all_plus_buttons(driver)
    print(f"        → Clicked {n} expandable section(s)")

    # 5. Scroll again after expanding (new content may have loaded)
    print("  5️⃣   Scrolling again after expanding...")
    slow_scroll(driver)
    time.sleep(1)

    # 6. Extract the spec data
    print("  6️⃣   Reading all specification values...")
    raw = extract_spec_pairs(driver)

    if len(raw) < 80:
        print("\n  ⚠️   Very little data captured.")
        print("       Fallback: please save this page manually.")
        print("       In Chrome: press Ctrl+S → Save as 'Webpage, HTML Only'")
        print(f"       Save into: {folder}/")
        return False

    cleaned = clean_output(raw, label)

    # Show preview in terminal
    preview = [l for l in cleaned.split('\n') if l.strip()][:15]
    print("\n  📋  Preview of captured specs:")
    for line in preview:
        print(f"       {line}")
    print("       ...")

    filepath = save(cleaned, folder, label)
    line_count = len([l for l in cleaned.split('\n') if l.strip()])
    print(f"\n  ✅  Saved {line_count} lines of spec data → {filepath}")
    return True


def main():
    print("\n" + "═"*56)
    print("  🤖  BenQ Spec Scraper v3")
    print("  Clicks: Display+, Optical+, Picture+,")
    print("          Compatibility+, I/O Interface+ etc.")
    print("  Result: All spec values saved cleanly")
    print("═"*56)

    print("\n  🌐  Opening Chrome...")
    print("      (A browser window will appear — don't close it!)\n")

    try:
        driver = open_browser()
    except Exception as e:
        print(f"\n❌  Chrome could not open: {e}")
        print("    Make sure Google Chrome is installed.")
        print("    Then run:  pip install --upgrade selenium")
        input("\nPress Enter to close...")
        return

    ok = fail = 0
    for i, page in enumerate(PAGES):
        if scrape_page(driver, page, first=(i == 0)):
            ok += 1
        else:
            fail += 1
        time.sleep(2)

    driver.quit()

    print(f"\n{'═'*56}")
    print(f"  🏁  DONE!")
    print(f"  ✅  {ok} spec file(s) saved with full details")
    print(f"  ❌  {fail} page(s) could not be scraped")
    print(f"{'═'*56}")
    print(f"\n  ▶️   Next step:  python ingest.py\n")
    input("Press Enter to close...")


if __name__ == "__main__":
    main()
