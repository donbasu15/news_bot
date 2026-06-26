import time
import json
import re
import subprocess
import os
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_chrome_major_version():
    """
    Detects the installed Google Chrome or Chromium major version.
    """
    for cmd in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
        try:
            output = subprocess.check_output([cmd, "--version"], stderr=subprocess.STDOUT).decode("utf-8")
            match = re.search(r"(?:Google Chrome|Chromium) (\d+)", output)
            if match:
                return int(match.group(1))
        except Exception:
            continue
    return None

def scrape_cryptopanic(num_items=30, output_file="cryptopanic_news.json"):
    """
    Scrapes news rows from CryptoPanic using undetected-chromedriver.
    Scrolls down until 'num_items' are collected.
    """
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    major_version = get_chrome_major_version()
    print(f"Detected Chrome major version: {major_version}")

    driver = uc.Chrome(options=options, version_main=major_version)
    
    try:
        print("Navigating to CryptoPanic...")
        driver.get("https://cryptopanic.com/")

        # Wait for the first news row to appear
        print("Waiting for news feed to load...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".news-row"))
        )
        print("Feed loaded successfully!")

        collected = []
        last_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 50

        # Find the scrollable container
        container = driver.find_element(By.CSS_SELECTOR, ".news-container")

        while len(collected) < num_items and scroll_attempts < max_scroll_attempts:
            # Find all news rows currently visible
            rows = driver.find_elements(By.CSS_SELECTOR, ".news-row")

            # Process visible rows
            for row in rows:
                try:
                    # Skip sponsored rows
                    row_class = row.get_attribute("class") or ""
                    if "sponsored" in row_class:
                        continue

                    # Extract unique identifier (the link) to avoid duplicates
                    title_elem = row.find_element(By.CSS_SELECTOR, "a.nc-title")
                    link = title_elem.get_attribute("href")
                    if not link:
                        continue

                    if any(item['link'] == link for item in collected):
                        continue  # skip duplicates

                    # Extract title text (using textContent for non-visible elements)
                    title = title_elem.find_element(By.CSS_SELECTOR, ".title-text > span:first-child").get_attribute("textContent").strip()
                    
                    # Extract source
                    source = row.find_element(By.CSS_SELECTOR, ".si-source-domain").get_attribute("textContent").strip()
                    
                    # Extract timestamp
                    time_elem = row.find_element(By.CSS_SELECTOR, ".nc-date time")
                    published = time_elem.get_attribute("datetime") or time_elem.get_attribute("textContent").strip()

                    # Sentiment: look for bullish/bearish indicators
                    sentiment = "neutral"
                    try:
                        sentiment_span = row.find_element(By.CSS_SELECTOR, "span.sentiment")
                        sentiment = sentiment_span.get_attribute("textContent").strip().lower()
                    except Exception:
                        # Fallback: check class names on the row itself
                        if "bullish" in row_class:
                            sentiment = "bullish"
                        elif "bearish" in row_class:
                            sentiment = "bearish"

                    collected.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": published,
                        "sentiment": sentiment
                    })

                    if len(collected) >= num_items:
                        break

                except Exception:
                    # Skip if any element extraction fails
                    continue

            print(f"Collected {len(collected)} / {num_items} items...")

            if len(collected) >= num_items:
                break

            # Scroll down the news container to load more content
            driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", container)
            time.sleep(2.5)  # allow time for new content to load

            # Check scroll progress
            new_count = len(collected)
            if new_count == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = new_count

    finally:
        driver.quit()

    # Save to JSON
    # with open(output_file, "w", encoding="utf-8") as f:
    #     json.dump(collected[:num_items], f, indent=2, ensure_ascii=False)

    # print(f"Scraping complete. Saved {len(collected[:num_items])} items to {output_file}")

    # Push to API endpoint
    api_url = os.environ.get("NEWS_API_URL", "https://binance-autopost1.onrender.com/api/news")
    print(f"Sending news payload to API endpoint: {api_url}")
    try:
        response = requests.post(api_url, json=collected[:num_items], headers={"Content-Type": "application/json"}, timeout=10)
        print(f"API Response: Status {response.status_code}, Body: {response.text}")
    except Exception as e:
        print(f"Failed to send news to API endpoint: {e}")

if __name__ == "__main__":
    scrape_cryptopanic(num_items=30)