# books_scraper_full.py
# Requirements:
#   pip install playwright aiohttp
#   playwright install
#
# Usage:
#   python books_scraper_full.py

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
# Email Settings
# ======================
SENDER_EMAIL = "your email"
APP_PASSWORD = "your app password"
RECEIVER_EMAIL = "your reciver email"

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
    # attrs is a dict with possible keys: data-srcset, srcset, data-src, src, ix-src
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

# ======================
# Scrapers (existing ones kept similar)
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

# ======================
# Improved FantasyLiterature scraper (reliable)
# ======================
async def scrape_fantasylit(context):
    books = []
    page = await context.new_page()
    try:
        print("[FantasyLit] Opening page...")
        await page.goto(FANTASYLIT_URL, timeout=90000, wait_until="load")

        # Wait a bit for client-side rendering (if any)
        try:
            await page.wait_for_selector("article.post", timeout=30000)
        except PWTimeout:
            print("[FantasyLit] no article.post within 30s — continuing to try to find content")

        # Some pages may lazy-load later; do a gentle scroll to encourage loading
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight);")
            await asyncio.sleep(1.0)

        containers = await page.query_selector_all("article.post")
        print(f"[FantasyLit] Found {len(containers)} article.post elements")

        for idx, el in enumerate(containers, start=1):
            # Title & link
            link_el = await el.query_selector("h2.post-title a")
            title = (await link_el.inner_text()) if link_el else "No Title"
            title = title.strip()
            link = (await link_el.get_attribute("href")) if link_el else "#"
            if link:
                link = urljoin(FANTASYLIT_URL, link)

            # Image: check src, data-src, srcset
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

            # Author: try author link first
            author = ""
            author_el = await el.query_selector(".post-content .post-block .author-detail a[rel='author'], .post-meta a[rel='author']")
            if author_el:
                try:
                    author = (await author_el.inner_text()).strip()
                except:
                    author = ""
            if not author:
                # fallback: look for "by ..." in excerpt
                p_el = await el.query_selector(".excerpt.entry-summary p")
                if p_el:
                    text = (await p_el.inner_text()) or ""
                    m = re.search(r"\bby\s+([A-Z][\w\s\-\.'’]+)", text)
                    if m:
                        author = m.group(1).strip()

            # Date / meta and excerpt
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
# Download Images (uses Playwright context.request)
# ======================
async def download_images_with_playwright(context, books):
    for book in books:
        img_url = book.get("image")
        if not img_url:
            continue
        filename = safe_filename(f"{book['publisher']}_{book['title'][:40]}")
        # preserve extension if present
        ext = Path(img_url).suffix
        if ext and len(ext) <= 6:
            filename = f"{filename}{ext}"
        else:
            filename = f"{filename}.jpg"
        path = IMAGE_DIR / filename
        if path.exists():
            print(f"[Download] exists {path}")
            book["local_image"] = str(path)
            continue
        try:
            print(f"[Download] fetching {img_url}")
            response = await context.request.get(img_url, timeout=30000)
            if response.status == 200:
                body = await response.body()
                with open(path, "wb") as f:
                    f.write(body)
                book["local_image"] = str(path)
                print(f"[Download] saved {path}")
            else:
                print(f"[Download] failed {img_url} status={response.status}")
                book["local_image"] = None
        except Exception as e:
            print(f"[Download] exception for {img_url}: {e}")
            book["local_image"] = None

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
body { 
    font-family: Arial, sans-serif; 
    background:#f4f4f4; 
    color:#333; 
    margin:0; 
    padding:0; 
}
.container { 
    width:90%; 
    max-width:700px; 
    margin:20px auto; 
    background:#fff; 
    border-radius:10px; 
    box-shadow:0 4px 8px rgba(0,0,0,0.1); 
    padding:20px; 
}
h1 { 
    text-align:center; 
    color:#2c3e50; 
}
.book { 
    border-bottom:1px solid #ddd; 
    padding:15px 0; 
    display:flex; 
    align-items:flex-start; 
}
.book img { 
    width:120px; 
    max-width:120px; 
    height:auto; 
    margin-right:15px; 
    border-radius:5px; 
}
.book h2 { 
    margin:0; 
    color:#2980b9; 
    font-size:16px; 
}
.book p { 
    margin:5px 0; 
    font-size:14px; 
}
.book a { 
    text-decoration:none; 
    color:#e74c3c; 
    font-weight:bold; 
}
</style>
</head>
<body>
<div class="container">
<h1>Latest Books</h1>

<!-- Example of a book -->
<div class="book">
    <img src="cid:example.jpg" alt="Book Title" style="width:120px; max-width:100%; height:auto; border-radius:5px;">
    <div>
        <h2>Book Title (Publisher Name)</h2>
        <p>Price: $19.99</p>
        <p><a href="https://example.com/book-link">View Book</a></p>
    </div>
</div>

<!-- Repeat .book blocks for each book -->

</div>
</body>
</html>

        """
    ]

    for book in all_books:
        filename = safe_filename(f"{book['publisher']}_{book['title'][:30]}.jpg")
        img_path = IMAGE_DIR / filename
        html_parts.append(f"""
        <div class="book">
            <img src="cid:{filename}" alt="{book['title']}">
            <div>
                <h2>{book['title']} ({book['publisher']})</h2>
                <p>Author: {book.get('author','N/A')}</p>
                <p>Price: {book.get('price','N/A')}</p>
                <p><a href="{book['link']}">View Book / Article</a></p>
            </div>
        </div>
        """)

        # Attach the image if we have a local copy matching this filename
        if img_path.exists():
            with open(img_path, "rb") as f:
                mime_type, _ = mimetypes.guess_type(img_path)
                subtype = mime_type.split("/")[-1] if mime_type else "jpeg"
                img = MIMEImage(f.read(), _subtype=subtype)
                img.add_header("Content-ID", f"<{filename}>")
                img.add_header("Content-Disposition", "inline", filename=filename)
                msg.attach(img)

    html_parts.append("</div></body></html>")
    html_content = "".join(html_parts)
    alt.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print("Failed to send email:", e)

# ======================
# Main
# ======================
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width":1280,"height":800})

        all_books = []
        # run scrapers (you can reorder or remove as you like)
        all_books += await scrape_baazh(context)
        all_books += await scrape_fantasylit(context)
        all_books += await scrape_porteghaal(context)
        all_books += await scrape_tandis(context)
        all_books += await scrape_tor(context)
        all_books += await scrape_daw(context)

        # limit per publisher (default 3)
        all_books = limit_books_per_publisher(all_books, 3)

        # Save JSON
        with open("all_books.json", "w", encoding="utf-8") as f:
            json.dump(all_books, f, ensure_ascii=False, indent=2)
        print(f"Saved all_books.json ({len(all_books)} entries)")

        # Download images (using Playwright context.request)
        await download_images_with_playwright(context, all_books)

        # Send email (will include images if filenames match those used above)
        send_email(all_books)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
