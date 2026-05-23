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


# XML/sitemap links are mandatory training pages.
# Internal links found inside normal pages are preserved as metadata links,
# but are not forced as separate documents unless they are also present in sitemap XML.
MAX_CRAWL_PAGES = 150
MAX_SITEMAP_LINKS = 300
REQUEST_TIMEOUT = 20
MIN_TEXT_LENGTH_FOR_REQUESTS = 300
MAX_SITEMAP_DEPTH = 3

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

SKIP_URL_PREFIXES = ("mailto:", "tel:", "javascript:", "data:", "#")
SKIP_URL_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".ico",
    ".css", ".js", ".json", ".txt", ".woff", ".woff2", ".ttf", ".eot",
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
    """Normalize URLs so sitemap + page links do not create duplicate pages."""
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

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = parsed.query or ""
    if query and any(k in query.lower() for k in ["utm_", "fbclid", "gclid", "replytocom"]):
        query = ""

    clean = f"{scheme}://{netloc}{path}"
    if query:
        clean = f"{clean}?{query}"
    return clean


def _is_xml_url(url: str) -> bool:
    return urlparse(url or "").path.lower().endswith(".xml")


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


def get_sitemap_links(sitemap_url: str, domain_anchor: str = "", _depth: int = 0, _seen: set = None):
    """
    Read sitemap.xml and sitemap index XML recursively.
    Returned URLs are actual HTML/content pages to scrape as separate documents.
    Nested .xml sitemap URLs are followed, not stored as normal knowledge pages.
    """
    sitemap_url = normalize_url(sitemap_url)
    if not sitemap_url:
        return []

    _seen = _seen or set()
    if sitemap_url in _seen or _depth > MAX_SITEMAP_DEPTH:
        return []
    _seen.add(sitemap_url)

    response = requests.get(sitemap_url, headers=get_default_headers(), timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    links = []
    nested_sitemaps = []

    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            link = normalize_url(element.text.strip(), base_url=sitemap_url)
            if not link:
                continue
            if domain_anchor and not is_internal_url(domain_anchor, link):
                continue
            if _is_xml_url(link):
                nested_sitemaps.append(link)
            elif not should_skip_crawl_url(link):
                links.append(link)

    for child_sitemap in _unique_keep_order(nested_sitemaps):
        try:
            links.extend(get_sitemap_links(child_sitemap, domain_anchor=domain_anchor or sitemap_url, _depth=_depth + 1, _seen=_seen))
        except Exception as exc:
            print(f"[SCRAPER] Failed nested sitemap {child_sitemap}: {exc}")

    return _priority_sort_urls(links)


def _guess_sitemap_url(website_url: str) -> str:
    parsed = urlparse(website_url or "")
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"


def collect_crawl_urls(website_url: str = "", sitemap_url: str = "", max_pages: int = MAX_CRAWL_PAGES):
    """
    Mandatory training URL collector.
    - Sitemap/XML links are primary pages and must be scraped fully.
    - If website_url itself is an XML URL, it is treated as sitemap_url.
    - Homepage is scraped too when provided.
    - Links found inside pages are kept as metadata by scrape_single_page(), not forced here.
    """
    website_url = normalize_url(website_url)
    sitemap_url = normalize_url(sitemap_url)

    if website_url and _is_xml_url(website_url) and not sitemap_url:
        sitemap_url = website_url
        website_url = ""

    domain_anchor = website_url or sitemap_url
    seed_urls = []

    if website_url and not should_skip_crawl_url(website_url):
        seed_urls.append(website_url)

    sitemap_links = []
    sitemap_candidates = []
    if sitemap_url:
        sitemap_candidates.append(sitemap_url)
    elif website_url:
        # Backward-compatible: even when frontend only sends website_url, try common sitemap.xml.
        sitemap_candidates.append(_guess_sitemap_url(website_url))

    for candidate in _unique_keep_order(sitemap_candidates):
        try:
            sitemap_links.extend(get_sitemap_links(candidate, domain_anchor=domain_anchor))
        except Exception as exc:
            print(f"[SCRAPER] Sitemap not available/readable {candidate}: {exc}")

    seed_urls.extend(sitemap_links[:MAX_SITEMAP_LINKS])

    # If no sitemap is available, fallback to homepage's own internal links as first-level pages.
    # If sitemap exists, we do NOT force child/page menu links as separate docs; they remain metadata.
    if website_url and not sitemap_links:
        try:
            seed_urls.extend(discover_internal_links(website_url))
        except Exception as exc:
            print(f"[SCRAPER] Failed homepage link discovery for {website_url}: {exc}")

    ordered = []
    seen = set()
    for url in _priority_sort_urls(seed_urls):
        clean = normalize_url(url)
        if not clean or clean in seen or should_skip_crawl_url(clean):
            continue
        if domain_anchor and not is_internal_url(domain_anchor, clean):
            continue
        seen.add(clean)
        ordered.append(clean)
        if len(ordered) >= max_pages:
            break

    return ordered


def scrape_by_request(website_url: str, sitemap_url: str, crawl_type: str, content_type: str):
    """
    Main training scraper entry used by /train-agent and /train-agent/start.

    Important behavior:
    - XML/sitemap URLs become complete separate knowledge documents.
    - product.html from sitemap.xml becomes its own card/chunk with text/images/links metadata.
    - Duplicate URLs from sitemap + page links are scraped once only.
    - Links inside each page are preserved as metadata links.
    """
    documents = []

    website_url = normalize_url((website_url or "").strip())
    sitemap_url = normalize_url((sitemap_url or "").strip())
    crawl_type = (crawl_type or "single_page").strip()

    if not website_url and not sitemap_url:
        return documents

    if crawl_type == "single_page" and website_url:
        urls_to_scrape = [website_url]
    else:
        urls_to_scrape = collect_crawl_urls(
            website_url=website_url,
            sitemap_url=sitemap_url,
            max_pages=MAX_CRAWL_PAGES,
        )

    print("[SCRAPER] crawl_type:", crawl_type)
    print("[SCRAPER] website_url:", website_url)
    print("[SCRAPER] sitemap_url:", sitemap_url)
    print("[SCRAPER] total_urls_to_scrape:", len(urls_to_scrape))
    print("[SCRAPER] sample_urls:", urls_to_scrape[:30])

    seen = set()
    for link in urls_to_scrape:
        clean_link = normalize_url(link)
        if not clean_link or clean_link in seen or should_skip_crawl_url(clean_link):
            continue
        seen.add(clean_link)

        try:
            doc = scrape_single_page(clean_link, content_type=content_type)
            text = (doc.get("text") or "").strip()
            if text:
                # source_key/source_hash are added later by training_registry; keep the exact URL here.
                documents.append(doc)
                print(
                    "[SCRAPER] scraped:",
                    clean_link,
                    "chars=", len(text),
                    "images=", len(doc.get("images") or []),
                    "links=", len(doc.get("links") or []),
                    "page_type=", doc.get("page_type"),
                )
            else:
                print("[SCRAPER] skipped empty text:", clean_link)
        except Exception as exc:
            print(f"[SCRAPER] Failed page: {clean_link} | {exc}")

    return documents
def scrape_single_page(url: str, content_type: str):
    url = normalize_url((url or "").strip())
    if not url:
        return empty_doc(url, content_type)

    request_doc = None

    try:
        request_doc = scrape_single_page_requests(url, content_type)
        text = (request_doc.get("text") or "").strip()

        if text or request_doc.get("images") or request_doc.get("links"):
            return request_doc

    except Exception as exc:
        print(f"[SCRAPER] requests failed for {url}: {exc}")

    try:
        return scrape_single_page_selenium(url, content_type)
    except Exception as exc:
        print(f"[SCRAPER] selenium failed for {url}: {exc}")
        return request_doc or empty_doc(url, content_type)

# def scrape_single_page(url: str, content_type: str):
#     """
#     Railway-safe scraper:
#     1. Try fast requests-based scraping first.
#     2. Use Selenium only if normal HTML has too little visible text.
#     Image URLs and page links are preserved as metadata.
#     """
#     url = normalize_url((url or "").strip())
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
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
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
    """
    Extract full readable page text, not only the first paragraph/meta description.

    Some business websites place useful content outside <main> in builders such as
    Elementor/WPBakery/Bootstrap sections. So we collect text from common content
    containers first and then add a body fallback. This keeps the full page visible
    in Knowledge Base edit and sends the same full text into FAISS training.
    """
    soup = BeautifulSoup(html or "", "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe", "form"]):
        tag.decompose()

    # Remove obvious chrome/noise, but keep page content sections.
    for selector in [
        "header", "footer", "nav", "aside",
        ".cookie", ".cookies", ".cookie-banner", ".popup", ".modal",
        ".newsletter", ".social-share", ".breadcrumb", ".breadcrumbs",
    ]:
        for tag in soup.select(selector):
            tag.decompose()

    texts = []

    def add_text(value):
        value = " ".join(str(value or "").split()).strip()
        if value:
            texts.append(value)

    # Keep useful SEO/meta text, but do not depend only on this.
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        if name in {"description", "og:description", "twitter:description", "keywords", "og:title", "twitter:title"}:
            add_text(meta.get("content"))

    title_tag = soup.find("title")
    if title_tag:
        add_text(title_tag.get_text(" ", strip=True))

    # Alt text helps image/product-heavy pages.
    for img in soup.find_all("img"):
        add_text(img.get("alt") or img.get("title"))

    content_selectors = [
        "main", "article", "section",
        "[role='main']",
        ".content", ".main-content", ".page-content", ".entry-content", ".post-content",
        ".product", ".product-detail", ".product-details", ".product-description",
        ".woocommerce-product-details__short-description", ".elementor", ".elementor-section",
        ".container", ".row",
    ]

    matched_any = False
    for selector in content_selectors:
        for block in soup.select(selector):
            block_text = block.get_text("\n", strip=True)
            if block_text:
                matched_any = True
                for line in block_text.splitlines():
                    add_text(line)

    # Explicitly collect structured text that sometimes gets missed in visual sections.
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "caption"]):
        add_text(tag.get_text(" ", strip=True))

    # Body fallback ensures full page text is captured if builders use uncommon classes.
    body = soup.find("body") or soup
    body_text = body.get_text("\n", strip=True)
    if body_text and (not matched_any or len("\n".join(texts)) < len(body_text) * 0.6):
        for line in body_text.splitlines():
            add_text(line)

    cleaned = []
    seen = set()
    for line in texts:
        key = line.lower()
        if len(line) < 2 or key in seen:
            continue
        seen.add(key)
        cleaned.append(line)

    return "\n".join(cleaned)
