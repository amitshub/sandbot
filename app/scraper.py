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


# IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
# SKIP_IMAGE_KEYWORDS = (
#     "logo",
#     "icon",
#     "favicon",
#     "sprite",
#     "loader",
#     "placeholder",
#     "blank",
# )


# def _unique_keep_order(values):
#     seen = set()
#     output = []
#     for value in values or []:
#         if isinstance(value, dict):
#             key = value.get("url") or value.get("src") or str(value)
#         else:
#             key = str(value)
#         key = (key or "").strip()
#         if not key or key in seen:
#             continue
#         seen.add(key)
#         output.append(value)
#     return output


# def _clean_absolute_url(base_url: str, value: str) -> str:
#     value = (value or "").strip()
#     if not value:
#         return ""

#     # Ignore inline/base64 images and javascript/mail links.
#     lower = value.lower()
#     if lower.startswith(("data:", "javascript:", "mailto:", "tel:")):
#         return ""

#     # srcset can contain: image-320.jpg 320w, image-640.jpg 640w
#     if "," in value and " " in value:
#         value = value.split(",")[0].strip().split(" ")[0].strip()
#     elif " " in value:
#         value = value.split(" ")[0].strip()

#     absolute = urljoin(base_url, value)
#     parsed = urlparse(absolute)
#     if parsed.scheme not in ["http", "https"]:
#         return ""

#     return absolute.split("#")[0]


# def _looks_like_product_image(url: str, alt: str = "") -> bool:
#     value = f"{url} {alt}".lower()

#     if any(skip in value for skip in SKIP_IMAGE_KEYWORDS):
#         return False

#     parsed_path = urlparse(url).path.lower()
#     return parsed_path.endswith(IMAGE_EXTENSIONS) or "/image" in value or "/upload" in value


# def extract_page_assets(html: str, page_url: str):
#     """
#     Extract image URLs and page links from one HTML page.
#     We store only URLs, never actual image files/base64.
#     """
#     soup = BeautifulSoup(html or "", "html.parser")
#     base_domain = urlparse(page_url).netloc

#     image_urls = []

#     # Common image attributes used by normal and lazy-loaded websites.
#     image_attrs = ["src", "data-src", "data-original", "data-lazy-src", "data-url"]

#     for img in soup.find_all("img"):
#         alt = (img.get("alt") or img.get("title") or "").strip()

#         candidates = []
#         for attr in image_attrs:
#             if img.get(attr):
#                 candidates.append(img.get(attr))
#         if img.get("srcset"):
#             candidates.append(img.get("srcset"))
#         if img.get("data-srcset"):
#             candidates.append(img.get("data-srcset"))

#         for candidate in candidates:
#             image_url = _clean_absolute_url(page_url, candidate)
#             if image_url and _looks_like_product_image(image_url, alt):
#                 image_urls.append(image_url)

#     # Some websites use OpenGraph/Twitter product image meta tags.
#     for meta in soup.find_all("meta"):
#         prop = (meta.get("property") or meta.get("name") or "").lower()
#         if prop in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
#             image_url = _clean_absolute_url(page_url, meta.get("content"))
#             if image_url:
#                 image_urls.append(image_url)

#     links = []
#     for a in soup.find_all("a", href=True):
#         link = _clean_absolute_url(page_url, a.get("href"))
#         if not link:
#             continue

#         parsed = urlparse(link)
#         if parsed.netloc != base_domain:
#             continue

#         clean_link = link.rstrip("/")
#         if clean_link:
#             links.append(clean_link)

#     return {
#         "images": _unique_keep_order(image_urls),
#         "links": _unique_keep_order(links),
#     }


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
#         seen = set()

#         for link in links:
#             clean_link = (link or "").strip().rstrip("/")
#             if not clean_link or clean_link in seen:
#                 continue
#             seen.add(clean_link)

#             try:
#                 doc = scrape_single_page(clean_link, content_type=content_type)
#                 if doc.get("text"):
#                     documents.append(doc)
#             except Exception as exc:
#                 print(f"[SCRAPER] Failed sitemap page: {clean_link} | {exc}")

#         return documents

#     if crawl_type == "full_website":
#         if not website_url:
#             raise ValueError("website_url is required when crawl_type is full_website")

#         links = discover_internal_links(website_url)[:MAX_FULL_WEBSITE_LINKS]
#         home = website_url.rstrip("/")

#         if home not in links:
#             links.insert(0, home)

#         seen = set()

#         for link in links:
#             clean_link = (link or "").strip().rstrip("/")
#             if not clean_link or clean_link in seen:
#                 continue

#             seen.add(clean_link)

#             try:
#                 doc = scrape_single_page(clean_link, content_type=content_type)
#                 if doc.get("text"):
#                     documents.append(doc)
#             except Exception as exc:
#                 print(f"[SCRAPER] Failed website page: {clean_link} | {exc}")

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
#     Image URLs are extracted in both paths and stored as metadata only.
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
#     assets = extract_page_assets(html, url)

#     return {
#         "source_type": "website",
#         "content_type": content_type,
#         "url": url,
#         "file_name": None,
#         "title": title or url,
#         "text": text,
#         "images": assets.get("images", []),
#         "links": assets.get("links", []),
#         "images_count": len(assets.get("images", [])),
#         "links_count": len(assets.get("links", [])),
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
#         assets = extract_page_assets(html, url)

#         return {
#             "source_type": "website",
#             "content_type": content_type,
#             "url": url,
#             "file_name": None,
#             "title": title,
#             "text": text,
#             "images": assets.get("images", []),
#             "links": assets.get("links", []),
#             "images_count": len(assets.get("images", [])),
#             "links_count": len(assets.get("links", [])),
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
#         "images": [],
#         "links": [],
#         "images_count": 0,
#         "links_count": 0,
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

#     return "\n".join(_unique_keep_order(texts))


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
#                 links.append(link.rstrip("/"))

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


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
SKIP_IMAGE_KEYWORDS = (
    "logo",
    "icon",
    "favicon",
    "sprite",
    "loader",
    "placeholder",
    "blank",
)

# These pages are useful for SEO/education, but they should NOT train the sales/product agent.
# Example problem solved: a blog comparing copper pipes vs stainless steel pipes should not make
# the bot claim the company sells copper pipes.
SKIP_URL_KEYWORDS = (
    "/blog/",
    "/blogs/",
    "/news/",
    "/article/",
    "/articles/",
    "/comparison/",
    "/comparisons/",
    "/compare/",
    "/guide/",
    "/guides/",
    "/vs/",
)


def _unique_keep_order(values):
    seen = set()
    output = []
    for value in values or []:
        if isinstance(value, dict):
            key = value.get("url") or value.get("src") or str(value)
        else:
            key = str(value)
        key = (key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def should_skip_url(url: str) -> bool:
    """
    Skip blog/article/SEO comparison pages during website training.
    This keeps FAISS focused on real business/product/service pages.
    """
    value = (url or "").lower()
    if not value:
        return True
    return any(keyword in value for keyword in SKIP_URL_KEYWORDS)


def detect_page_type(url: str, title: str = "") -> str:
    """
    Lightweight page type metadata. The main anti-hallucination behavior is should_skip_url(),
    but this metadata is useful in chunks.json and future filtering.
    """
    value = f"{url or ''} {title or ''}".lower()

    if any(keyword in value for keyword in SKIP_URL_KEYWORDS):
        return "blog"
    if any(keyword in value for keyword in ["/product/", "/products/", "/catalog/", "/category/", "/shop/"]):
        return "product"
    if any(keyword in value for keyword in ["/service/", "/services/"]):
        return "service"
    if any(keyword in value for keyword in ["/about", "/contact", "/company"]):
        return "company"
    return "website"


def _clean_absolute_url(base_url: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    # Ignore inline/base64 images and javascript/mail links.
    lower = value.lower()
    if lower.startswith(("data:", "javascript:", "mailto:", "tel:")):
        return ""

    # srcset can contain: image-320.jpg 320w, image-640.jpg 640w
    if "," in value and " " in value:
        value = value.split(",")[0].strip().split(" ")[0].strip()
    elif " " in value:
        value = value.split(" ")[0].strip()

    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in ["http", "https"]:
        return ""

    return absolute.split("#")[0]


def _looks_like_product_image(url: str, alt: str = "") -> bool:
    value = f"{url} {alt}".lower()

    if any(skip in value for skip in SKIP_IMAGE_KEYWORDS):
        return False

    parsed_path = urlparse(url).path.lower()
    return parsed_path.endswith(IMAGE_EXTENSIONS) or "/image" in value or "/upload" in value


def extract_page_assets(html: str, page_url: str):
    """
    Extract image URLs and page links from one HTML page.
    We store only URLs, never actual image files/base64.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    base_domain = urlparse(page_url).netloc

    image_urls = []

    # Common image attributes used by normal and lazy-loaded websites.
    image_attrs = ["src", "data-src", "data-original", "data-lazy-src", "data-url"]

    for img in soup.find_all("img"):
        alt = (img.get("alt") or img.get("title") or "").strip()

        candidates = []
        for attr in image_attrs:
            if img.get(attr):
                candidates.append(img.get(attr))
        if img.get("srcset"):
            candidates.append(img.get("srcset"))
        if img.get("data-srcset"):
            candidates.append(img.get("data-srcset"))

        for candidate in candidates:
            image_url = _clean_absolute_url(page_url, candidate)
            if image_url and _looks_like_product_image(image_url, alt):
                image_urls.append(image_url)

    # Some websites use OpenGraph/Twitter product image meta tags.
    for meta in soup.find_all("meta"):
        prop = (meta.get("property") or meta.get("name") or "").lower()
        if prop in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            image_url = _clean_absolute_url(page_url, meta.get("content"))
            if image_url:
                image_urls.append(image_url)

    links = []
    for a in soup.find_all("a", href=True):
        link = _clean_absolute_url(page_url, a.get("href"))
        if not link:
            continue

        parsed = urlparse(link)
        if parsed.netloc != base_domain:
            continue

        clean_link = link.rstrip("/")
        if clean_link:
            links.append(clean_link)

    return {
        "images": _unique_keep_order(image_urls),
        "links": _unique_keep_order(links),
    }


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
        seen = set()

        for link in links:
            clean_link = (link or "").strip().rstrip("/")
            if not clean_link or clean_link in seen:
                continue
            seen.add(clean_link)

            if should_skip_url(clean_link):
                print(f"[SCRAPER] Skipping blog/article page: {clean_link}")
                continue

            try:
                doc = scrape_single_page(clean_link, content_type=content_type)
                if doc.get("text"):
                    documents.append(doc)
            except Exception as exc:
                print(f"[SCRAPER] Failed sitemap page: {clean_link} | {exc}")

        return documents

    if crawl_type == "full_website":
        if not website_url:
            raise ValueError("website_url is required when crawl_type is full_website")

        links = discover_internal_links(website_url)[:MAX_FULL_WEBSITE_LINKS]
        home = website_url.rstrip("/")

        if home not in links and not should_skip_url(home):
            links.insert(0, home)

        seen = set()

        for link in links:
            clean_link = (link or "").strip().rstrip("/")
            if not clean_link or clean_link in seen:
                continue

            seen.add(clean_link)

            if should_skip_url(clean_link):
                print(f"[SCRAPER] Skipping blog/article page: {clean_link}")
                continue

            try:
                doc = scrape_single_page(clean_link, content_type=content_type)
                if doc.get("text"):
                    documents.append(doc)
            except Exception as exc:
                print(f"[SCRAPER] Failed website page: {clean_link} | {exc}")

        return documents

    if website_url:
        if should_skip_url(website_url):
            print(f"[SCRAPER] Skipping blog/article page: {website_url}")
            return documents

        doc = scrape_single_page(website_url, content_type=content_type)
        if doc.get("text"):
            documents.append(doc)

    return documents


def scrape_single_page(url: str, content_type: str):
    """
    Railway-safe scraper:
    1. Try fast requests-based scraping first.
    2. Use Selenium only if normal HTML has too little visible text.
    Image URLs are extracted in both paths and stored as metadata only.
    """
    url = (url or "").strip()

    if not url:
        return empty_doc(url, content_type)

    if should_skip_url(url):
        print(f"[SCRAPER] Skipping blog/article page: {url}")
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
    assets = extract_page_assets(html, url)
    page_type = detect_page_type(url, title)

    return {
        "source_type": "website",
        "content_type": content_type,
        "page_type": page_type,
        "url": url,
        "file_name": None,
        "title": title or url,
        "text": text,
        "images": assets.get("images", []),
        "links": assets.get("links", []),
        "images_count": len(assets.get("images", [])),
        "links_count": len(assets.get("links", [])),
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
        assets = extract_page_assets(html, url)
        page_type = detect_page_type(url, title)

        return {
            "source_type": "website",
            "content_type": content_type,
            "page_type": page_type,
            "url": url,
            "file_name": None,
            "title": title,
            "text": text,
            "images": assets.get("images", []),
            "links": assets.get("links", []),
            "images_count": len(assets.get("images", [])),
            "links_count": len(assets.get("links", [])),
        }

    finally:
        if driver:
            driver.quit()


def empty_doc(url: str, content_type: str):
    return {
        "source_type": "website",
        "content_type": content_type,
        "page_type": detect_page_type(url),
        "url": url,
        "file_name": None,
        "title": url,
        "text": "",
        "images": [],
        "links": [],
        "images_count": 0,
        "links_count": 0,
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

    return "\n".join(_unique_keep_order(texts))


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

        if should_skip_url(clean_url):
            print(f"[SCRAPER] Skipping discovered blog/article link: {clean_url}")
            continue

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
                clean_link = link.rstrip("/")
                if should_skip_url(clean_link):
                    print(f"[SCRAPER] Skipping sitemap blog/article link: {clean_link}")
                    continue
                links.append(clean_link)

    return list(dict.fromkeys(links))

