from urllib.parse import urljoin, urlparse, urldefrag
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


# Higher limits because sales/support bot needs real website knowledge, not only homepage text.
MAX_CRAWL_PAGES = 100
MAX_FULL_WEBSITE_LINKS = 100
MAX_SITEMAP_LINKS = 150
MAX_CHILD_LINKS_PER_PAGE = 80
REQUEST_TIMEOUT = 20
MIN_TEXT_LENGTH_FOR_REQUESTS = 300


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar")
SKIP_IMAGE_KEYWORDS = (
    "logo",
    "icon",
    "favicon",
    "sprite",
    "loader",
    "placeholder",
    "blank",
)


# Hard skip only technical / non-content URLs. Do not skip blog/product/service links here,
# because the requirement is to extract website data well and let FAISS decide relevance.
SKIP_URL_PREFIXES = ("mailto:", "tel:", "javascript:", "data:", "#")
SKIP_URL_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".ico",
    ".css", ".js", ".xml", ".json", ".txt", ".woff", ".woff2", ".ttf", ".eot",
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


def normalize_url(url: str, base_url: str = None) -> str:
    """Normalize URLs so sitemap + page links do not create duplicates."""
    value = (url or "").strip()
    if not value:
        return ""

    if value.lower().startswith(SKIP_URL_PREFIXES):
        return ""

    absolute = urljoin(base_url or value, value) if base_url else value
    absolute, _fragment = urldefrag(absolute)
    parsed = urlparse(absolute)

    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    # Normalize trailing slash except root.
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Keep query only for URLs that look intentionally query-based.
    # Most ecommerce / WordPress query URLs create duplicate pages.
    query = parsed.query or ""
    if query and any(k in query.lower() for k in ["utm_", "fbclid", "gclid", "replytocom"]):
        query = ""

    clean = f"{scheme}://{netloc}{path}"
    if query:
        clean = f"{clean}?{query}"
    return clean


def is_internal_url(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url or "")
    candidate = urlparse(candidate_url or "")
    return bool(base.netloc and candidate.netloc and base.netloc.lower() == candidate.netloc.lower())


def should_skip_crawl_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return True

    path = urlparse(value).path.lower()
    if path.endswith(SKIP_URL_EXTENSIONS):
        return True

    return False


def detect_page_type(url: str, title: str = "") -> str:
    value = f"{url or ''} {title or ''}".lower()
    path = urlparse(url or "").path.lower()

    if any(x in value for x in ["privacy", "terms", "cookie"]):
        return "policy_page"
    if any(x in value for x in ["blog", "article", "news"]):
        return "blog"

    product_markers = [
        "product", "products", "catalog", "catalogue", "category", "shop",
        "item", "items", "model", "models", "collection", "collections",
    ]
    if any(marker in path or marker in value for marker in product_markers):
        return "product_page"

    if any(keyword in value for keyword in ["/service", "/services", "service", "support"]):
        return "service_page"
    if any(keyword in value for keyword in ["/about", "/contact", "/company", "about us", "contact us"]):
        return "company_page"
    if any(keyword in value for keyword in ["sitemap"]):
        return "sitemap"
    return "website_page"


def _clean_absolute_url(base_url: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    lower = value.lower()
    if lower.startswith(SKIP_URL_PREFIXES):
        return ""

    # srcset can contain: image-320.jpg 320w, image-640.jpg 640w
    if "," in value and " " in value:
        value = value.split(",")[0].strip().split(" ")[0].strip()
    elif " " in value:
        value = value.split(" ")[0].strip()

    return normalize_url(value, base_url=base_url)


def _looks_like_product_image(url: str, alt: str = "") -> bool:
    value = f"{url} {alt}".lower()

    if any(skip in value for skip in SKIP_IMAGE_KEYWORDS):
        return False

    parsed_path = urlparse(url).path.lower()
    return parsed_path.endswith(IMAGE_EXTENSIONS) or "/image" in value or "/upload" in value


def extract_page_assets(html: str, page_url: str):
    """Extract image URLs and internal page links from one HTML page."""
    soup = BeautifulSoup(html or "", "html.parser")
    base_domain = urlparse(page_url).netloc.lower()

    image_urls = []
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
        if parsed.netloc.lower() != base_domain:
            continue
        if should_skip_crawl_url(link):
            continue

        links.append(link)

    return {
        "images": _unique_keep_order(image_urls),
        "links": _unique_keep_order(links),
    }


def get_default_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }


def _priority_sort_urls(urls):
    def score(u):
        value = (u or "").lower()
        page_type = detect_page_type(value)
        if page_type == "product_page":
            return 0
        if page_type in {"service_page", "company_page"}:
            return 1
        if page_type == "website_page":
            return 2
        if page_type == "blog":
            return 4
        return 3

    return sorted(_unique_keep_order(urls), key=lambda u: (score(u), len(u), u))


def discover_internal_links(start_url: str):
    start_url = normalize_url(start_url)
    if not start_url:
        return []

    response = requests.get(start_url, headers=get_default_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    assets = extract_page_assets(response.text or "", start_url)
    return assets.get("links", [])


def get_sitemap_links(sitemap_url: str):
    sitemap_url = normalize_url(sitemap_url)
    if not sitemap_url:
        return []

    response = requests.get(sitemap_url, headers=get_default_headers(), timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    links = []

    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            link = normalize_url(element.text.strip())
            if link and not should_skip_crawl_url(link):
                links.append(link)

    return _priority_sort_urls(links)


def collect_crawl_urls(website_url: str = "", sitemap_url: str = "", max_pages: int = MAX_CRAWL_PAGES, max_depth: int = 2):
    """
    BFS crawler URL collector.
    - Sitemap URLs and homepage links are both first-class pages.
    - Links found inside those pages are visited too, up to max_depth.
    - Duplicate URLs are skipped using normalize_url().
    """
    website_url = normalize_url(website_url)
    sitemap_url = normalize_url(sitemap_url)

    seed_urls = []
    if website_url:
        seed_urls.append(website_url)

    sitemap_links = []
    if sitemap_url:
        try:
            sitemap_links = get_sitemap_links(sitemap_url)[:MAX_SITEMAP_LINKS]
            seed_urls.extend(sitemap_links)
        except Exception as exc:
            print(f"[SCRAPER] Failed to read sitemap {sitemap_url}: {exc}")

    # If only sitemap is supplied, use first sitemap URL as domain anchor.
    domain_anchor = website_url or (sitemap_links[0] if sitemap_links else "")
    if not domain_anchor:
        return []

    queue = []
    queued = set()
    visited = set()
    ordered_urls = []

    for url in _priority_sort_urls(seed_urls):
        clean = normalize_url(url)
        if not clean or clean in queued or should_skip_crawl_url(clean):
            continue
        if not is_internal_url(domain_anchor, clean):
            continue
        queue.append((clean, 0))
        queued.add(clean)

    while queue and len(ordered_urls) < max_pages:
        current_url, depth = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)
        ordered_urls.append(current_url)

        if depth >= max_depth:
            continue

        try:
            # Lightweight requests fetch only for discovering child links.
            response = requests.get(current_url, headers=get_default_headers(), timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            assets = extract_page_assets(response.text or "", current_url)
            child_links = _priority_sort_urls(assets.get("links", []))[:MAX_CHILD_LINKS_PER_PAGE]
        except Exception as exc:
            print(f"[SCRAPER] Failed link discovery for {current_url}: {exc}")
            child_links = []

        for link in child_links:
            clean_link = normalize_url(link, base_url=current_url)
            if not clean_link or clean_link in queued or clean_link in visited:
                continue
            if should_skip_crawl_url(clean_link):
                continue
            if not is_internal_url(domain_anchor, clean_link):
                continue
            queue.append((clean_link, depth + 1))
            queued.add(clean_link)

    return ordered_urls[:max_pages]


def scrape_by_request(
    website_url: str,
    sitemap_url: str,
    crawl_type: str,
    content_type: str,
):
    """
    Main training scraper entry used by /train-agent and /train-agent/start.

    Important behavior:
    - Even if frontend sends crawl_type='single_page', we still crawl internal links.
      This keeps old endpoint/frontend unchanged while making KB complete.
    - Every internal link becomes its own document with its own url/title/text/images/links.
    - Same URL found from sitemap + page links is scraped only once.
    """
    documents = []

    website_url = normalize_url((website_url or "").strip())
    sitemap_url = normalize_url((sitemap_url or "").strip())
    crawl_type = (crawl_type or "single_page").strip()

    if not website_url and not sitemap_url:
        return documents

    # Different modes only adjust depth/limit, not endpoint behavior.
    if crawl_type == "sitemap":
        max_depth = 1
        max_pages = MAX_CRAWL_PAGES
    elif crawl_type == "full_website":
        max_depth = 2
        max_pages = MAX_CRAWL_PAGES
    else:
        # Old frontend default is often single_page. Use depth 2 so important links like product.html
        # become separate KB pages without requiring frontend changes.
        max_depth = 2
        max_pages = MAX_CRAWL_PAGES

    urls_to_scrape = collect_crawl_urls(
        website_url=website_url,
        sitemap_url=sitemap_url,
        max_pages=max_pages,
        max_depth=max_depth,
    )

    print("[SCRAPER] crawl_type:", crawl_type)
    print("[SCRAPER] total_urls_to_scrape:", len(urls_to_scrape))
    print("[SCRAPER] sample_urls:", urls_to_scrape[:20])

    seen = set()
    for link in urls_to_scrape:
        clean_link = normalize_url(link)
        if not clean_link or clean_link in seen or should_skip_crawl_url(clean_link):
            continue
        seen.add(clean_link)

        try:
            doc = scrape_single_page(clean_link, content_type=content_type)
            if doc.get("text"):
                documents.append(doc)
        except Exception as exc:
            print(f"[SCRAPER] Failed page: {clean_link} | {exc}")

    return documents


def scrape_single_page(url: str, content_type: str):
    """
    Railway-safe scraper:
    1. Try fast requests-based scraping first.
    2. Use Selenium only if normal HTML has too little visible text.
    Image URLs and page links are preserved as metadata.
    """
    url = normalize_url((url or "").strip())

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
    response = requests.get(url, headers=get_default_headers(), timeout=REQUEST_TIMEOUT)
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
        "priority": 90 if page_type == "product_page" else 40,
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
            "priority": 90 if page_type == "product_page" else 40,
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
        "priority": 0,
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

    # Include anchor text because menus/product cards often hold useful product labels.
    for element in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "span", "a", "strong", "b"]
    ):
        value = element.get_text(" ", strip=True)
        if value:
            texts.append(value)

    return "\n".join(_unique_keep_order(texts))
