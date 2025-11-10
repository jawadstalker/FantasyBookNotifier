# books_scraper_full.py
# Requirements:
#   pip install playwright aiohttp
#   playwright install
#
# This file exports an async runner `run_for(publishers, receiver_email, per_publisher=3)`
# that collects books from the requested publishers, downloads images, saves JSON and sends an email.
# It can also be run standalone (will scrape all configured publishers and send to the configured RECEIVER_EMAIL).

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin
import mimetypes
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ======================
# Email Settings (replace with real values or override at runtime)
# ======================
SENDER_EMAIL = "jawadvamps@gmail.com"
APP_PASSWORD = "tdsf iszn bhli sucr"
RECEIVER_EMAIL = "jawadvamps@gmail.com"

# ======================
# Image Folder
# ======================
IMAGE_DIR = Path("book_images")
IMAGE_DIR.mkdir(exist_ok=True)

# ======================
# Site URLs
# ======================
BAAZH_URL = "https://baazhbook.com/"
PORTEGHAAL_URL = "https://porteghaal.com/"
TANDIS_URL = "https://tandispub.com/"
TOR_URL = "https://torpublishinggroup.com/"
DAW_URL = "https://astrapublishinghouse.com/"
FANTASYLIT_URL = "https://fantasyliterature.com/"

# ======================
# Utilities
# ======================
def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r]', "", name)
    name = re.sub(r'\s+', "_", name.strip())
    return name[:180]

def parse_srcset(srcset_text: str):
    pairs = []
    if not srcset_text:
        return pairs
    for part in srcset_text.split(","):
        part = part.strip()
        if not part:
            continue
        if " " in part:
            try:
                url, descriptor = part.rsplit(" ", 1)
            except ValueError:
                url = part
                descriptor = ""
        else:
            url = part
            descriptor = ""
        width = 0
        if descriptor.endswith("w"):
            try:
                width = int(descriptor[:-1])
            except Exception:
                width = 0
        pairs.append((width, url.strip()))
    return pairs

def pick_best_image(base_url: str, attrs: dict) -> str:
    for key in ("data-srcset", "srcset"):
        ss = attrs.get(key) or ""
        parsed = parse_srcset(ss)
        if parsed:
            parsed.sort(key=lambda x: x[0], reverse=True)
            best_url = parsed[0][1]
            return urljoin(base_url, best_url)
    for key in ("data-src", "src", "ix-src"):
        candidate = attrs.get(key) or ""
        if candidate:
            return urljoin(base_url, candidate.strip())
    return ""

def limit_books_per_publisher(all_books, per_publisher=3):
    grouped = {}
    result = []
    for b in all_books:
        pub = b.get("publisher", "Unknown Publisher")
        grouped.setdefault(pub, 0)
        if grouped[pub] < per_publisher:
            result.append(b)
            grouped[pub] += 1
    return result

def choose_extension_from_content_type(content_type: str) -> str:
    if not content_type:
        return ".jpg"
    content_type = content_type.split(";")[0].strip().lower()
    guess = mimetypes.guess_extension(content_type)
    if guess:
        return guess
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path.stem
    ext = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{base}_{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1

# ======================
# Scrapers
# ======================

async def scrape_baazh(context):
    books = []
    page = await context.new_page()
    try:
        await page.goto(BAAZH_URL, timeout=90000, wait_until="load")
        containers = await page.query_selector_all("div.product-grid-item")
        for el in containers:
            title_el = await el.query_selector("h3.wd-entities-title a")
            title = await title_el.inner_text() if title_el else "No Title"
            link = await title_el.get_attribute("href") if title_el else "#"
            link = urljoin(BAAZH_URL, link)
            price_el = await el.query_selector("span.price")
            price = await price_el.inner_text() if price_el else "No Price"
            img_el = await el.query_selector("div.product-element-top img")
            image = pick_best_image(BAAZH_URL, {
                "src": await img_el.get_attribute("src") if img_el else "",
                "data-src": await img_el.get_attribute("data-src") if img_el else "",
                "srcset": await img_el.get_attribute("srcset") if img_el else "",
                "data-srcset": await img_el.get_attribute("data-srcset") if img_el else ""
            })
            books.append({
                "publisher": "Baazh Book",
                "title": title.strip(),
                "price": price.strip(),
                "image": image,
                "link": link,
                "description": ""
            })
        print(f"[Baazh] Found {len(books)} items")
    except PWTimeout:
        print("Timeout while loading BaazhBook.")
    finally:
        await page.close()
    return books

async def scrape_porteghaal(context):
    books = []
    page = await context.new_page()
    try:
        await page.goto(PORTEGHAAL_URL, timeout=90000, wait_until="load")
        containers = await page.query_selector_all("a.porteghal-slider-item")
        for el in containers:
            title_el = await el.query_selector("p.cart-title")
            title = await title_el.inner_text() if title_el else "No Title"
            link = await el.get_attribute("href") or "#"
            link = urljoin(PORTEGHAAL_URL, link)
            price_el = await el.query_selector("p.sale-price span.font-semibold")
            price = await price_el.inner_text() if price_el else "No Price"
            img_el = await el.query_selector("img.porteghal-card-pic")
            image = pick_best_image(PORTEGHAAL_URL, {
                "src": await img_el.get_attribute("src") if img_el else "",
                "data-src": await img_el.get_attribute("data-src") if img_el else "",
                "srcset": await img_el.get_attribute("srcset") if img_el else "",
                "data-srcset": await img_el.get_attribute("data-srcset") if img_el else ""
            })
            books.append({
                "publisher": "Porteghaal",
                "title": title.strip(),
                "price": price.strip(),
                "image": image,
                "link": link,
                "description": ""
            })
        print(f"[Porteghaal] Found {len(books)} items")
    except PWTimeout:
        print("Timeout while loading Porteghaal.")
    finally:
        await page.close()
    return books

async def scrape_tandis(context):
    books = []
    page = await context.new_page()
    try:
        await page.goto(TANDIS_URL, timeout=90000, wait_until="load")
        containers = await page.query_selector_all("div.sc-item-content")
        for el in containers:
            title_el = await el.query_selector("h3")
            title = await title_el.inner_text() if title_el else "No Title"
            link_node = await el.query_selector("a[href^='https://tandispub.com/book/']")
            link = await link_node.get_attribute("href") if link_node else "#"
            img_el = await el.query_selector("a.fimage img")
            image = pick_best_image(TANDIS_URL, {
                "src": await img_el.get_attribute("src") if img_el else "",
                "data-src": await img_el.get_attribute("data-src") if img_el else "",
                "srcset": await img_el.get_attribute("srcset") if img_el else "",
                "data-srcset": await img_el.get_attribute("data-srcset") if img_el else ""
            })
            price_el = await el.query_selector("p.price")
            price = await price_el.inner_text() if price_el else "No Price"
            books.append({
                "publisher": "Tandis Pub",
                "title": title.strip(),
                "price": price.strip(),
                "image": image,
                "link": link,
                "description": ""
            })
        print(f"[Tandis] Found {len(books)} items")
    except PWTimeout:
        print("Timeout while loading Tandis.")
    finally:
        await page.close()
    return books

async def scrape_tor(context):
    books = []
    page = await context.new_page()
    try:
        await page.goto(TOR_URL, timeout=90000, wait_until="load")
        containers = await page.query_selector_all("div.card-list-item")
        for el in containers:
            title_el = await el.query_selector("h3.card-post-title a")
            title = await title_el.inner_text() if title_el else "No Title"
            link = await title_el.get_attribute("href") if title_el else "#"
            link = urljoin(TOR_URL, link)
            img_el = await el.query_selector("img[ix-src], img[src]")
            image = pick_best_image(TOR_URL, {
                "src": await img_el.get_attribute("src") if img_el else "",
                "ix-src": await img_el.get_attribute("ix-src") if img_el else ""
            })
            books.append({
                "publisher": "Tor Books",
                "title": title.strip(),
                "price": "N/A",
                "image": image,
                "link": link,
                "description": ""
            })
        print(f"[Tor] Found {len(books)} items")
    except PWTimeout:
        print("Timeout while loading Tor Books.")
    finally:
        await page.close()
    return books

async def scrape_daw(context):
    books = []
    page = await context.new_page()
    try:
        await page.goto(DAW_URL, timeout=90000, wait_until="load")
        await page.wait_for_selector("div.portfolio-item-wrap", timeout=15000)
        containers = await page.query_selector_all("div.portfolio-item-wrap")
        for el in containers:
            link = await el.get_attribute("data-permalink") or "#"
            link = urljoin(DAW_URL, link)
            title_el = await el.query_selector("h3")
            title = await title_el.inner_text() if title_el else "No Title"
            img_el = await el.query_selector("div.portfolio-image img")
            image = pick_best_image(DAW_URL, {
                "src": await img_el.get_attribute("src") if img_el else ""
            })
            author_el = await el.query_selector("span")
            author = await author_el.inner_text() if author_el else ""
            books.append({
                "publisher": "DAW Books",
                "title": title.strip(),
                "author": author.strip(),
                "price": "N/A",
                "image": image,
                "link": link,
                "description": ""
            })
        print(f"[DAW] Found {len(books)} items")
    except PWTimeout:
        print("Timeout while loading DAW Books.")
    finally:
        await page.close()
    return books

async def scrape_fantasylit(context):
    books = []
    page = await context.new_page()
    try:
        print("[FantasyLit] Opening page...")
        await page.goto(FANTASYLIT_URL, timeout=90000, wait_until="load")
        try:
            await page.wait_for_selector("article.post", timeout=30000)
        except PWTimeout:
            print("[FantasyLit] no article.post within 30s — continuing to try to find content")
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight);")
            await asyncio.sleep(1.0)
        containers = await page.query_selector_all("article.post")
        print(f"[FantasyLit] Found {len(containers)} article.post elements")
        for idx, el in enumerate(containers, start=1):
            link_el = await el.query_selector("h2.post-title a")
            title = (await link_el.inner_text()) if link_el else "No Title"
            title = title.strip()
            link = (await link_el.get_attribute("href")) if link_el else "#"
            if link:
                link = urljoin(FANTASYLIT_URL, link)
            img_el = await el.query_selector(".header a img, .header img")
            img_src = ""
            if img_el:
                img_src = (await img_el.get_attribute("src")) or ""
                if not img_src:
                    img_src = (await img_el.get_attribute("data-src")) or ""
                if not img_src:
                    srcset = (await img_el.get_attribute("srcset")) or ""
                    if srcset:
                        img_src = srcset.split(",")[0].strip().split(" ")[0]
                if img_src:
                    img_src = urljoin(FANTASYLIT_URL, img_src)
            author = ""
            author_el = await el.query_selector(".post-content .post-block .author-detail a[rel='author'], .post-meta a[rel='author']")
            if author_el:
                try:
                    author = (await author_el.inner_text()).strip()
                except:
                    author = ""
            if not author:
                p_el = await el.query_selector(".excerpt.entry-summary p")
                if p_el:
                    text = (await p_el.inner_text()) or ""
                    m = re.search(r"\bby\s+([A-Z][\w\s\-\.'’]+)", text)
                    if m:
                        author = m.group(1).strip()
            date_meta = ""
            meta_el = await el.query_selector(".post-meta .meta-info, .post-meta")
            if meta_el:
                date_meta = (await meta_el.inner_text()).strip()
                date_meta = re.sub(r"\s+", " ", date_meta)
            excerpt = ""
            excerpt_el = await el.query_selector(".excerpt.entry-summary p")
            if excerpt_el:
                excerpt = (await excerpt_el.inner_text()).strip()
            books.append({
                "publisher": "Fantasy Literature",
                "title": title,
                "author": author,
                "price": "N/A",
                "image": img_src,
                "link": link,
                "date_meta": date_meta,
                "excerpt": excerpt,
                "description": ""
            })
            print(f"[FantasyLit] {idx}. {title} — image: {bool(img_src)} — author: {author or 'N/A'}")
    except PWTimeout:
        print("Timeout while loading Fantasy Literature.")
    except Exception as e:
        print("Error scraping Fantasy Literature:", e)
    finally:
        await page.close()
    return books

# ======================
# Download Images
# ======================
async def download_images_with_playwright(context, books):
    for book in books:
        img_url = book.get("image")
        book["local_image"] = None
        book["cid"] = None

        if not img_url:
            print(f"[Download] No image URL for '{book.get('title','<no title>')}' — skipping")
            continue

        try:
            print(f"[Download] fetching {img_url}")
            response = await context.request.get(img_url, timeout=30000)
        except Exception as e:
            print(f"[Download] exception for {img_url}: {e}")
            continue

        if response.status != 200:
            print(f"[Download] failed {img_url} status={response.status}")
            continue

        ct = response.headers.get("content-type", "") if hasattr(response, "headers") else ""
        ext = choose_extension_from_content_type(ct)
        filename_base = safe_filename(f"{book.get('publisher','Unknown')}_{book.get('title','no_title')[:60]}")
        filename = filename_base + ext
        path = IMAGE_DIR / filename
        path = unique_path(path)

        try:
            body = await response.body()
            with open(path, "wb") as f:
                f.write(body)
            book["local_image"] = str(path)
            book["cid"] = path.name
            print(f"[Download] saved {path} (content-type: {ct})")
        except Exception as e:
            print(f"[Download] write exception for {img_url}: {e}")
            book["local_image"] = None
            book["cid"] = None

# ======================
# Send Email
# ======================
def send_email(all_books):
    msg = MIMEMultipart("related")
    msg["Subject"] = "📚 Latest Books from Publishers"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText("Latest books available.", "plain"))

    html_parts = [
        """
       <html>
<head>
<style>
body { font-family: Arial, sans-serif; background:#f4f4f4; color:#333; margin:0; padding:0;}
.container { width:90%; max-width:700px; margin:20px auto; background:#fff; border-radius:10px; box-shadow:0 4px 8px rgba(0,0,0,0.1); padding:20px;}
h1 { text-align:center; color:#2c3e50; }
.book { border-bottom:1px solid #ddd; padding:15px 0; display:flex; align-items:flex-start;}
.book img { width:120px; max-width:130px; height:auto; margin-right:15px; border-radius:5px;}
.book h2 { margin:0; color:#2980b9; font-size:16px;}
.book p { margin:5px 0; font-size:14px;}
.book a { text-decoration:none; color:#e74c3c; font-weight:bold;}
</style>
</head>
<body>
<div class="container">
<h1>Latest Books</h1>
"""
    ]

    for book in all_books:
        title = book.get("title", "No Title")
        publisher = book.get("publisher", "Unknown Publisher")
        price = book.get("price", "N/A")
        link = book.get("link", "#")
        author = book.get("author", "N/A")
        cid = book.get("cid")
        img_html = ""
        if cid:
            img_html = f'<img src="cid:{cid}" alt="{title}" />'
        else:
            img_html = '<div style="width:120px; height:180px; background:#eee; display:inline-block; margin-right:15px; border-radius:5px;"></div>'

        html_parts.append(f"""
        <div class="book">
            {img_html}
            <div>
                <h2>{title} ({publisher})</h2>
                <p>Author: {author}</p>
                <p>Price: {price}</p>
                <p><a href="{link}">View Book / Article</a></p>
            </div>
        </div>
        """)

    html_parts.append("</div></body></html>")
    html_content = "".join(html_parts)
    alt.attach(MIMEText(html_content, "html"))

    for book in all_books:
        img_path = book.get("local_image")
        cid = book.get("cid")
        if img_path and cid:
            p = Path(img_path)
            if p.exists():
                try:
                    with open(p, "rb") as f:
                        data = f.read()
                    mime_type, _ = mimetypes.guess_type(str(p))
                    if mime_type and mime_type.startswith("image/"):
                        subtype = mime_type.split("/")[1]
                    else:
                        subtype = "jpeg"
                    img = MIMEImage(data, _subtype=subtype)
                    img.add_header("Content-ID", f"<{cid}>")
                    img.add_header("Content-Disposition", "inline", filename=cid)
                    msg.attach(img)
                    print(f"[Email] attached {p} as cid:{cid}")
                except Exception as e:
                    print(f"[Email] failed to attach {p}: {e}")
            else:
                print(f"[Email] image file missing: {p}")
        else:
            pass

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print("Failed to send email:", e)

# ======================
# Runner wrapper and mapping
# ======================

# Map human-readable publisher names to scraper functions
SCRAPERS_MAP = {
    "Baazh Book": scrape_baazh,
    "Porteghaal": scrape_porteghaal,
    "Tandis Pub": scrape_tandis,
    "Tor Books": scrape_tor,
    "DAW Books": scrape_daw,
    "Fantasy Literature": scrape_fantasylit,
}

async def run_for(publishers: list, receiver_email: str, per_publisher: int = 3):
    """
    Run scrapers for the requested publishers and send email to receiver_email.
    publishers: list of publisher names which must match keys in SCRAPERS_MAP.
    """
    global RECEIVER_EMAIL
    prev_receiver = RECEIVER_EMAIL
    RECEIVER_EMAIL = receiver_email

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width":1280,"height":800})

        all_books = []
        for name in publishers:
            fn = SCRAPERS_MAP.get(name)
            if fn:
                try:
                    books = await fn(context)
                    all_books += books
                except Exception as e:
                    print(f"[Runner] error scraping {name}: {e}")
            else:
                print(f"[Runner] unknown publisher requested: {name}")

        all_books = limit_books_per_publisher(all_books, per_publisher)

        with open("all_books.json", "w", encoding="utf-8") as f:
            json.dump(all_books, f, ensure_ascii=False, indent=2)
        print(f"[Runner] Saved all_books.json ({len(all_books)} entries)")

        await download_images_with_playwright(context, all_books)
        send_email(all_books)

        await browser.close()

    RECEIVER_EMAIL = prev_receiver

# ======================
# Main: allow running standalone
# ======================
async def main():
    # default run: all publishers; sends to configured RECEIVER_EMAIL
    all_pubs = list(SCRAPERS_MAP.keys())
    await run_for(all_pubs, RECEIVER_EMAIL)

if __name__ == "__main__":
    asyncio.run(main())
