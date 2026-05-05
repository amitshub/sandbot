# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin, urlparse

# BASE_URL = "https://sandlus.com"
# SITEMAP_URL = "https://sandlus.com/sitemap.html"


# def get_links_from_sitemap():
#     headers = {
#         "User-Agent": "Mozilla/5.0"
#     }

#     response = requests.get(SITEMAP_URL, headers=headers, timeout=20)
#     response.raise_for_status()

#     soup = BeautifulSoup(response.text, "lxml")

#     links = set()

#     for a in soup.find_all("a", href=True):
#         full_url = urljoin(BASE_URL, a["href"])

#         parsed = urlparse(full_url)

#         if parsed.netloc == "sandlus.com":
#             links.add(full_url.split("#")[0])

#     return list(links)


# def clean_html_to_text(html):
#     soup = BeautifulSoup(html, "lxml")

#     for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
#         tag.decompose()

#     text = soup.get_text(separator=" ", strip=True)
#     return " ".join(text.split())


# def fetch_page_text(url):
#     headers = {
#         "User-Agent": "Mozilla/5.0"
#     }

#     response = requests.get(url, headers=headers, timeout=20)
#     response.raise_for_status()

#     return clean_html_to_text(response.text)


# def load_website_documents():
#     links = get_links_from_sitemap()

#     documents = []

#     for url in links:
#         try:
#             text = fetch_page_text(url)

#             if len(text) > 100:
#                 documents.append({
#                     "url": url,
#                     "text": text
#                 })

#             print("Loaded:", url)

#         except Exception as e:
#             print("Skipped:", url, e)

#     return documents  

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

SITEMAP_URL = "https://sandlus.com/sitemap.xml"


def get_urls_from_sitemap():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(SITEMAP_URL, headers=headers, timeout=20)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "xml")

    urls = []

    for loc in soup.find_all("loc"):
        url = loc.text.strip()

        if urlparse(url).netloc in ["sandlus.com", "www.sandlus.com"]:
            urls.append(url)

    return urls


def clean_html(html):
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()

    return clean_html(res.text)


def load_website_documents():
    urls = get_urls_from_sitemap()

    documents = []

    for url in urls:
        try:
            text = fetch_page_text(url)

            if len(text) > 100:
                documents.append({
                    "url": url,
                    "text": text
                })

            print("Loaded:", url)

        except Exception as e:
            print("Skipped:", url, e)

    return documents