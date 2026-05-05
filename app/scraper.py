from urllib.parse import urljoin, urlparse
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


MAX_FULL_WEBSITE_LINKS = 25
MAX_SITEMAP_LINKS = 50


def scrape_by_request(
    website_url: str,
    sitemap_url: str,
    crawl_type: str,
    content_type: str,
):
    documents = []

    if crawl_type == "sitemap":
        if not sitemap_url:
            raise ValueError("sitemap_url is required when crawl_type is sitemap")

        links = get_sitemap_links(sitemap_url)[:MAX_SITEMAP_LINKS]

        for link in links:
            doc = scrape_single_page(link, content_type=content_type)
            if doc.get("text"):
                documents.append(doc)

        return documents

    if crawl_type == "full_website":
        if not website_url:
            raise ValueError("website_url is required when crawl_type is full_website")

        links = discover_internal_links(website_url)[:MAX_FULL_WEBSITE_LINKS]

        if website_url not in links:
            links.insert(0, website_url)

        seen = set()

        for link in links:
            if link in seen:
                continue

            seen.add(link)

            doc = scrape_single_page(link, content_type=content_type)
            if doc.get("text"):
                documents.append(doc)

        return documents

    if website_url:
        doc = scrape_single_page(website_url, content_type=content_type)
        if doc.get("text"):
            documents.append(doc)

    return documents


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--log-level=3")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def scrape_single_page(url: str, content_type: str):
    driver = None

    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(2)

        title = driver.title or url
        html = driver.page_source
        text = extract_visible_text(html)

        return {
            "source_type": "website",
            "content_type": content_type,
            "url": url,
            "file_name": None,
            "title": title,
            "text": text,
        }

    finally:
        if driver:
            driver.quit()


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
        tag.decompose()

    texts = []

    for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "a"]):
        value = element.get_text(" ", strip=True)

        if value:
            texts.append(value)

    return "\n".join(texts)


def discover_internal_links(start_url: str):
    response = requests.get(start_url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    base_domain = urlparse(start_url).netloc

    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        absolute_url = urljoin(start_url, href)
        parsed = urlparse(absolute_url)

        if parsed.scheme not in ["http", "https"]:
            continue

        if parsed.netloc != base_domain:
            continue

        clean_url = absolute_url.split("#")[0].rstrip("/")

        if clean_url and clean_url not in links:
            links.append(clean_url)

    return links


def get_sitemap_links(sitemap_url: str):
    response = requests.get(sitemap_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    links = []

    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            link = element.text.strip()

            if link.startswith("http"):
                links.append(link)

    return links
