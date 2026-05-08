# from urllib.parse import urljoin, urlparse
# import time
# import xml.etree.ElementTree as ET

# import requests
# from bs4 import BeautifulSoup

# try:
#     from selenium import webdriver
#     from selenium.webdriver.chrome.options import Options
#     from selenium.webdriver.chrome.service import Service
# except Exception:
#     webdriver = None
#     Options = None
#     Service = None


# MAX_FULL_WEBSITE_LINKS = 25
# MAX_SITEMAP_LINKS = 50
# REQUEST_TIMEOUT = 20
# MIN_TEXT_LENGTH_FOR_REQUESTS = 300


# def scrape_by_request(
#     website_url: str,
#     sitemap_url: str,
#     crawl_type: str,
#     content_type: str,
# ):
#     documents = []

#     website_url = (website_url or "").strip()
#     sitemap_url = (sitemap_url or "").strip()
#     crawl_type = (crawl_type or "single_page").strip()

#     if crawl_type == "sitemap":
#         if not sitemap_url:
#             raise ValueError("sitemap_url is required when crawl_type is sitemap")

#         links = get_sitemap_links(sitemap_url)[:MAX_SITEMAP_LINKS]

#         for link in links:
#             try:
#                 doc = scrape_single_page(link, content_type=content_type)
#                 if doc.get("text"):
#                     documents.append(doc)
#             except Exception as exc:
#                 print(f"[SCRAPER] Failed sitemap page: {link} | {exc}")

#         return documents

#     if crawl_type == "full_website":
#         if not website_url:
#             raise ValueError("website_url is required when crawl_type is full_website")

#         links = discover_internal_links(website_url)[:MAX_FULL_WEBSITE_LINKS]

#         if website_url.rstrip("/") not in links:
#             links.insert(0, website_url.rstrip("/"))

#         seen = set()

#         for link in links:
#             if link in seen:
#                 continue

#             seen.add(link)

#             try:
#                 doc = scrape_single_page(link, content_type=content_type)
#                 if doc.get("text"):
#                     documents.append(doc)
#             except Exception as exc:
#                 print(f"[SCRAPER] Failed website page: {link} | {exc}")

#         return documents

#     if website_url:
#         doc = scrape_single_page(website_url, content_type=content_type)
#         if doc.get("text"):
#             documents.append(doc)

#     return documents


# def scrape_single_page(url: str, content_type: str):
#     """
#     Railway-safe scraper:
#     1. Try fast requests-based scraping first.
#     2. Use Selenium only if normal HTML has too little visible text.
#     """
#     url = (url or "").strip()

#     if not url:
#         return empty_doc(url, content_type)

#     try:
#         doc = scrape_single_page_requests(url, content_type)
#         if len((doc.get("text") or "").strip()) >= MIN_TEXT_LENGTH_FOR_REQUESTS:
#             return doc
#     except Exception as exc:
#         print(f"[SCRAPER] requests failed for {url}: {exc}")

#     try:
#         return scrape_single_page_selenium(url, content_type)
#     except Exception as exc:
#         print(f"[SCRAPER] selenium failed for {url}: {exc}")
#         return empty_doc(url, content_type)


# def scrape_single_page_requests(url: str, content_type: str):
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/120.0 Safari/537.36"
#         )
#     }

#     response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#     response.raise_for_status()

#     html = response.text or ""
#     soup = BeautifulSoup(html, "html.parser")

#     title = ""
#     if soup.title and soup.title.string:
#         title = soup.title.string.strip()

#     text = extract_visible_text(html)

#     return {
#         "source_type": "website",
#         "content_type": content_type,
#         "url": url,
#         "file_name": None,
#         "title": title or url,
#         "text": text,
#     }


# def get_driver():
#     if webdriver is None or Options is None:
#         raise RuntimeError("Selenium is not installed or not available.")

#     options = Options()
#     options.add_argument("--headless=new")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--window-size=1366,768")
#     options.add_argument("--log-level=3")
#     options.add_argument("--disable-extensions")
#     options.add_argument("--disable-background-networking")
#     options.add_argument("--disable-sync")
#     options.add_argument("--metrics-recording-only")
#     options.add_argument("--mute-audio")

#     return webdriver.Chrome(options=options)


# def scrape_single_page_selenium(url: str, content_type: str):
#     driver = None

#     try:
#         driver = get_driver()
#         driver.set_page_load_timeout(30)
#         driver.get(url)
#         time.sleep(2)

#         title = driver.title or url
#         html = driver.page_source or ""
#         text = extract_visible_text(html)

#         return {
#             "source_type": "website",
#             "content_type": content_type,
#             "url": url,
#             "file_name": None,
#             "title": title,
#             "text": text,
#         }

#     finally:
#         if driver:
#             driver.quit()


# def empty_doc(url: str, content_type: str):
#     return {
#         "source_type": "website",
#         "content_type": content_type,
#         "url": url,
#         "file_name": None,
#         "title": url,
#         "text": "",
#     }


# def extract_visible_text(html: str) -> str:
#     soup = BeautifulSoup(html or "", "html.parser")

#     for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
#         tag.decompose()

#     texts = []

#     for element in soup.find_all(
#         ["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "a"]
#     ):
#         value = element.get_text(" ", strip=True)
#         if value:
#             texts.append(value)

#     return "\n".join(texts)


# def discover_internal_links(start_url: str):
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/120.0 Safari/537.36"
#         )
#     }

#     response = requests.get(start_url, headers=headers, timeout=REQUEST_TIMEOUT)
#     response.raise_for_status()

#     soup = BeautifulSoup(response.text, "html.parser")
#     base_domain = urlparse(start_url).netloc

#     links = []

#     for a in soup.find_all("a", href=True):
#         href = a.get("href")
#         absolute_url = urljoin(start_url, href)
#         parsed = urlparse(absolute_url)

#         if parsed.scheme not in ["http", "https"]:
#             continue

#         if parsed.netloc != base_domain:
#             continue

#         clean_url = absolute_url.split("#")[0].rstrip("/")

#         if clean_url and clean_url not in links:
#             links.append(clean_url)

#     return links


# def get_sitemap_links(sitemap_url: str):
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/120.0 Safari/537.36"
#         )
#     }

#     response = requests.get(sitemap_url, headers=headers, timeout=30)
#     response.raise_for_status()

#     root = ET.fromstring(response.content)

#     links = []

#     for element in root.iter():
#         if element.tag.endswith("loc") and element.text:
#             link = element.text.strip()
#             if link.startswith("http"):
#                 links.append(link)

#     return list(dict.fromkeys(links)) 
from urllib.parse import urljoin, urlparse
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except Exception:
    webdriver = None
    Options = None
    Service = None


MAX_FULL_WEBSITE_LINKS = 25
MAX_SITEMAP_LINKS = 50
REQUEST_TIMEOUT = 20
MIN_TEXT_LENGTH_FOR_REQUESTS = 300


def scrape_by_request(
    website_url: str,
    sitemap_url: str,
    crawl_type: str,
    content_type: str,
):
    documents = []

    website_url = (website_url or "").strip()
    sitemap_url = (sitemap_url or "").strip()
    crawl_type = (crawl_type or "single_page").strip()

    if crawl_type == "sitemap":
        if not sitemap_url:
            raise ValueError("sitemap_url is required when crawl_type is sitemap")

        links = get_sitemap_links(sitemap_url)[:MAX_SITEMAP_LINKS]

        for link in links:
            try:
                doc = scrape_single_page(link, content_type=content_type)
                if doc.get("text"):
                    documents.append(doc)
            except Exception as exc:
                print(f"[SCRAPER] Failed sitemap page: {link} | {exc}")

        return documents

    if crawl_type == "full_website":
        if not website_url:
            raise ValueError("website_url is required when crawl_type is full_website")

        links = discover_internal_links(website_url)[:MAX_FULL_WEBSITE_LINKS]

        if website_url.rstrip("/") not in links:
            links.insert(0, website_url.rstrip("/"))

        seen = set()

        for link in links:
            if link in seen:
                continue

            seen.add(link)

            try:
                doc = scrape_single_page(link, content_type=content_type)
                if doc.get("text"):
                    documents.append(doc)
            except Exception as exc:
                print(f"[SCRAPER] Failed website page: {link} | {exc}")

        return documents

    if website_url:
        doc = scrape_single_page(website_url, content_type=content_type)
        if doc.get("text"):
            documents.append(doc)

    return documents


def scrape_single_page(url: str, content_type: str):
    """
    Railway-safe scraper:
    1. Try fast requests-based scraping first.
    2. Use Selenium only if normal HTML has too little visible text.
    """
    url = (url or "").strip()

    if not url:
        return empty_doc(url, content_type)

    try:
        doc = scrape_single_page_requests(url, content_type)
        if len((doc.get("text") or "").strip()) >= MIN_TEXT_LENGTH_FOR_REQUESTS:
            return doc
    except Exception as exc:
        print(f"[SCRAPER] requests failed for {url}: {exc}")

    try:
        return scrape_single_page_selenium(url, content_type)
    except Exception as exc:
        print(f"[SCRAPER] selenium failed for {url}: {exc}")
        return empty_doc(url, content_type)


def scrape_single_page_requests(url: str, content_type: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    html = response.text or ""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    text = extract_visible_text(html)

    return {
        "source_type": "website",
        "content_type": content_type,
        "url": url,
        "file_name": None,
        "title": title or url,
        "text": text,
    }


def get_driver():
    if webdriver is None or Options is None:
        raise RuntimeError("Selenium is not installed or not available.")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--mute-audio")

    return webdriver.Chrome(options=options)


def scrape_single_page_selenium(url: str, content_type: str):
    driver = None

    try:
        driver = get_driver()
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(2)

        title = driver.title or url
        html = driver.page_source or ""
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


def empty_doc(url: str, content_type: str):
    return {
        "source_type": "website",
        "content_type": content_type,
        "url": url,
        "file_name": None,
        "title": url,
        "text": "",
    }


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
        tag.decompose()

    texts = []

    for element in soup.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "a"]
    ):
        value = element.get_text(" ", strip=True)
        if value:
            texts.append(value)

    return "\n".join(texts)


def discover_internal_links(start_url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(start_url, headers=headers, timeout=REQUEST_TIMEOUT)
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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(sitemap_url, headers=headers, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    links = []

    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            link = element.text.strip()
            if link.startswith("http"):
                links.append(link)

    return list(dict.fromkeys(links))