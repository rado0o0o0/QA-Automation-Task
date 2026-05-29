"""
Task 2 - Link Checker
======================
Senior Manual QA perspective | Python + Selenium + requests
Target: https://the-internet.herokuapp.com/

Steps:
  1. Open the page with Selenium
  2. Collect every <a href> link in the main content area
  3. Visit each link with requests and record HTTP status
  4. Write a timestamped CSV: url, http_status, page_title, result
     - result = OK (2xx) or Dead link (4xx / 5xx / timeout / connection error)
  5. Timeout per request: 10 seconds
  6. Running twice produces two separate timestamped files (idempotent)
"""

import csv
import os
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_URL     = "https://the-internet.herokuapp.com/"
REQUEST_TIMEOUT = 10          # seconds per HTTP request
OUTPUT_DIR     = "."          # folder where the CSV is saved


# ---------------------------------------------------------------------------
# Page Object
# ---------------------------------------------------------------------------

class HerokuAppPage:
    """Responsible only for opening the page and collecting links."""

    def __init__(self, driver):
        self.driver = driver
        self.wait   = WebDriverWait(driver, 10)

    def open(self):
        self.driver.get(TARGET_URL)
        # Wait until at least one link is visible in the content area
        self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#content a")))

    def collect_links(self):
        """
        Returns a list of absolute URL strings found inside #content.
        Skips empty hrefs and javascript: pseudo-links.
        """
        anchors = self.driver.find_elements(By.CSS_SELECTOR, "#content a")
        links = []
        for anchor in anchors:
            href = anchor.get_attribute("href")
            if href and href.startswith("http"):
                links.append(href)
        # Deduplicate while preserving order
        seen  = set()
        unique = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)
        return unique


# ---------------------------------------------------------------------------
# Title extractor (lightweight, no extra Selenium navigation)
# ---------------------------------------------------------------------------

class _TitleParser(HTMLParser):
    """Minimal HTML parser that pulls the <title> text."""
    def __init__(self):
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _extract_title(html: str) -> str:
    parser = _TitleParser()
    parser.feed(html)
    return parser.title.strip() or "N/A"


# ---------------------------------------------------------------------------
# HTTP checker
# ---------------------------------------------------------------------------

def check_link(url: str) -> dict:
    """
    Visits a URL with requests (not Selenium) and returns a result dict:
      url, http_status, page_title, result
    """
    result_row = {
        "url":         url,
        "http_status": "",
        "page_title":  "",
        "result":      "",
    }

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        status   = response.status_code
        result_row["http_status"] = str(status)

        # Try to extract page title from response body (HTML pages only)
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type:
            result_row["page_title"] = _extract_title(response.text)

        if 200 <= status < 300:
            result_row["result"] = "OK"
        else:
            result_row["result"] = "Dead link"

    except requests.exceptions.Timeout:
        result_row["http_status"] = "timeout"
        result_row["result"]      = "Dead link"

    except requests.exceptions.ConnectionError:
        result_row["http_status"] = "connection refused"
        result_row["result"]      = "Dead link"

    except requests.exceptions.RequestException as e:
        result_row["http_status"] = f"error: {type(e).__name__}"
        result_row["result"]      = "Dead link"

    return result_row


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(rows: list, output_dir: str) -> str:
    """
    Writes results to <timestamp>_results.csv.
    Returns the file path written.
    Handles commas and quotes in titles correctly via csv.writer quoting.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{timestamp}_results.csv"
    filepath  = os.path.join(output_dir, filename)

    fieldnames = ["url", "http_status", "page_title", "result"]

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)   # always quote → safe for commas in titles
        writer.writeheader()
        writer.writerows(rows)

    return filepath


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def build_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_link_checker():
    print(f"[INFO] Starting link checker for: {TARGET_URL}")

    # Step 1 & 2: Open page and collect links via Selenium
    driver = build_driver(headless=False)   # set True for headless run
    try:
        page  = HerokuAppPage(driver)
        page.open()
        links = page.collect_links()
    finally:
        driver.quit()

    print(f"[INFO] Found {len(links)} unique links to check")

    # Step 3: Check each link via requests
    results = []
    for idx, url in enumerate(links, start=1):
        print(f"  [{idx}/{len(links)}] Checking: {url}")
        row = check_link(url)
        results.append(row)
        status_label = f"HTTP {row['http_status']}" if row["http_status"] else "N/A"
        print(f"         → {row['result']} | {status_label} | {row['page_title'] or 'no title'}")

    # Step 4: Write timestamped CSV
    output_path = write_csv(results, OUTPUT_DIR)
    print(f"\n[INFO] Results written to: {output_path}")

    # Summary
    ok_count   = sum(1 for r in results if r["result"] == "OK")
    dead_count = len(results) - ok_count
    print(f"[INFO] Summary → OK: {ok_count} | Dead links: {dead_count}")

    return output_path


if __name__ == "__main__":
    run_link_checker()
