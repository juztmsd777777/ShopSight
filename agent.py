import asyncio
import re

SHOPS = [
    {
        "name": "Amazon",
        "url": "https://www.amazon.in/s?k={query}",
    },
    {
        "name": "Flipkart",
        "url": "https://www.flipkart.com/search?q={query}",
    },
    {
        "name": "Reliance Digital",
        "url": "https://www.reliancedigital.in/products?q={query}",
    },
]

ACCESSORY_WORDS = {
    "case", "cover", "adapter", "charger", "cable", "tempered glass", "screen protector",
    "protector", "skin", "pouch", "sleeve", "stand", "mount", "strap", "band", "eartips",
    "ear tips", "lens", "guard", "back cover", "silicone case", "magsafe"
}

def is_valid_product(title: str, query: str) -> bool:
    if not title or len(title) < 5:
        return False

    title_lower = title.lower()
    query_lower = query.lower()

    # 1. Filter out accessories if query is not asking for one
    query_has_accessory = any(acc in query_lower for acc in ACCESSORY_WORDS)
    if not query_has_accessory:
        if any(re.search(r'\b' + re.escape(acc) + r'\b', title_lower) for acc in ACCESSORY_WORDS):
            return False

    # 2. Extract model identifier tokens (e.g. "15", "s24", "m2", "12", "xm5")
    query_numbers = set(re.findall(r'\b\d+[a-zA-Z]*\b|\b[a-zA-Z]+\d+\b', query_lower))
    model_numbers = {
        num for num in query_numbers
        if not any(unit in num for unit in ["gb", "tb", "ram", "rom", "cm", "inch", "mah", "mp"])
    }

    for num in model_numbers:
        if not re.search(r'\b' + re.escape(num) + r'\b', title_lower):
            return False

    # 3. Check for conflicting model versions (e.g. query "iphone 15" vs title "iphone 16" or "iphone 14")
    for brand in ["iphone", "galaxy s", "macbook", "oneplus"]:
        if brand in query_lower:
            q_match = re.search(brand + r'\s*([a-zA-Z0-9]+)', query_lower)
            t_match = re.search(brand + r'\s*([a-zA-Z0-9]+)', title_lower)
            if q_match and t_match:
                if q_match.group(1) != t_match.group(1):
                    return False

    # 4. Check key brand / product terms match
    query_words = [
        w for w in re.findall(r'\w+', query_lower)
        if len(w) > 2 and w not in ["gb", "tb", "ram", "rom", "inch", "phone", "mobile", "laptop"]
    ]
    matched_words = [w for w in query_words if w in title_lower]
    if query_words and len(matched_words) < max(1, len(query_words) // 2):
        return False

    return True

async def scrape_amazon(page, product: str) -> list:
    items = []
    try:
        results = await page.query_selector_all("div[data-component-type='s-search-result']")
        for r in results:
            if len(items) >= 3:
                break
            try:
                # Skip sponsored / ad results
                sponsored = await r.query_selector(".s-sponsored-label-info-icon, .s-sponsored-label-text")
                if sponsored:
                    continue

                # Title - try multiple selectors
                title = None
                for sel in ["h2 a span", "h2 .a-text-normal", "h2 span.a-text-normal", ".a-size-medium.a-text-normal", "h2 a"]:
                    el = await r.query_selector(sel)
                    if el:
                        t = (await el.inner_text()).strip()
                        if len(t) > 5 and t.lower() not in ["apple", "samsung", "oneplus", "iqoo", "oppo", "vivo", "realme", "xiaomi"]:
                            title = t
                            break

                if not title or not is_valid_product(title, product):
                    continue

                # Price
                price = None
                for sel in [".a-price .a-offscreen", ".a-price-whole", "span.a-price"]:
                    el = await r.query_selector(sel)
                    if el:
                        price = (await el.inner_text()).strip()
                        if price:
                            break

                # Rating
                rating = "N/A"
                el = await r.query_selector(".a-icon-alt")
                if el:
                    rating = (await el.inner_text()).strip()[:15]

                # URL extraction
                url_el = await r.query_selector("h2 a[href], a.a-link-normal[href]")
                link = await url_el.get_attribute("href") if url_el else None
                if link and not link.startswith("http"):
                    link = "https://www.amazon.in" + link

                if title and price:
                    price = price.replace("\n", "").split("₹")[-1]
                    price = "₹" + price.strip().split("\n")[0]
                    items.append({"title": title[:80], "price": price, "rating": rating, "delivery": "N/A", "url": link})
            except Exception:
                continue
    except Exception as e:
        print(f"Amazon scrape error: {e}")
    return items[:3]

async def scrape_flipkart(page, product: str) -> list:
    items = []
    try:
        containers = []
        for sel in ["div[data-id]", "div._1AtVbE", "div._13oc-S", "div.cPHDOP", "div.t56Fp5"]:
            containers = await page.query_selector_all(sel)
            if len(containers) > 2:
                break

        for r in containers:
            if len(items) >= 3:
                break
            try:
                txt = await r.inner_text()
                lines = [l.strip() for l in txt.split("\n") if l.strip()]
                if any(l.lower() == "sponsored" for l in lines[:3]):
                    continue

                title = None
                for sel in [".KzDlHZ", ".w752f", "._4rR01T", ".s1Q9rs", ".IRpwTa", "a[title]", "div.col-7-12 a", ".W22pG4"]:
                    el = await r.query_selector(sel)
                    if el:
                        t = (await el.inner_text()).strip()
                        if len(t) > 5:
                            title = t
                            break
                if not title:
                    for line in lines:
                        if not any(k in line.lower() for k in ["bestseller", "add to compare", "ratings", "reviews", "bank offer", "off", "sponsored"]):
                            title = line
                            break

                if not title or not is_valid_product(title, product):
                    continue

                price = None
                for sel in [".Nx9qKw", "._30jeq3", "._1_WHN1", "div._25b18c", "div.Nx9qKw", "._3tbVC0"]:
                    el = await r.query_selector(sel)
                    if el:
                        p_txt = (await el.inner_text()).strip()
                        if p_txt and ("₹" in p_txt or any(c.isdigit() for c in p_txt)):
                            price = p_txt
                            break
                if not price:
                    m = re.search(r"₹\s*[\d,]+", txt)
                    if m:
                        price = m.group(0)

                rating = "N/A"
                for sel in [".Xg-52r", "._3LWZlK", "._1lRcqv span"]:
                    el = await r.query_selector(sel)
                    if el:
                        r_txt = (await el.inner_text()).strip()[:10]
                        if r_txt:
                            rating = r_txt
                            break
                if rating == "N/A":
                    m = re.search(r"(\d\.\d)\s*[\d,]*\s*Ratings", txt)
                    if m:
                        rating = m.group(1)

                url_el = await r.query_selector("a[href]")
                link = await url_el.get_attribute("href") if url_el else None
                if link and not link.startswith("http"):
                    link = "https://www.flipkart.com" + link

                if title and price and len(title) > 5:
                    if not price.startswith("₹"):
                        price = "₹" + price.replace("₹", "").strip()
                    items.append({"title": title[:80], "price": price, "rating": rating, "delivery": "N/A", "url": link})
            except Exception:
                continue
    except Exception as e:
        print(f"Flipkart scrape error: {e}")
    return items[:3]

async def scrape_reliance_digital(page, product: str) -> list:
    items = []
    try:
        containers = []
        for sel in ["div.product-card-details", "div[class*='product-card']", "div.card-info-container", "div[class*='sp__product']"]:
            containers = await page.query_selector_all(sel)
            if len(containers) >= 2:
                break

        for r in containers:
            if len(items) >= 3:
                break
            try:
                title = None
                for sel in [".product-card-title", "p[class*='title']", "div[class*='title']", "a[title]", "p.sp__name"]:
                    el = await r.query_selector(sel)
                    if el:
                        t = (await el.inner_text()).strip()
                        if len(t) > 5:
                            title = t
                            break

                price = None
                for sel in ["span[class*='price']", "div[class*='price']", "span.sp__price"]:
                    el = await r.query_selector(sel)
                    if el:
                        p_txt = (await el.inner_text()).strip()
                        if p_txt and ("₹" in p_txt or any(c.isdigit() for c in p_txt)):
                            price = p_txt
                            break

                if not title or not price:
                    txt = await r.inner_text()
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    if not title and lines:
                        for l in lines:
                            if len(l) > 8 and not any(k in l.lower() for k in ["off", "mrp", "save", "unavailable", "₹", "sponsored"]):
                                title = l
                                break
                    if not price:
                        m = re.search(r"₹\s*[\d,]+(?:\.\d+)?", txt)
                        if m:
                            price = m.group(0)

                if not title or not is_valid_product(title, product):
                    continue

                url_el = await r.query_selector("a[href]")
                if not url_el:
                    parent = await r.query_selector("xpath=..")
                    url_el = await parent.query_selector("a[href]") if parent else None
                link = await url_el.get_attribute("href") if url_el else None
                if link and not link.startswith("http"):
                    link = "https://www.reliancedigital.in" + link

                if title and price and len(title) > 5:
                    if not price.startswith("₹"):
                        price = "₹" + price.replace("₹", "").strip()
                    price = price.split(".")[0]
                    items.append({"title": title[:80], "price": price, "rating": "N/A", "delivery": "N/A", "url": link})
            except Exception:
                continue
    except Exception as e:
        print(f"Reliance Digital scrape error: {e}")
    return items[:3]

async def run_agent(product: str, send_event):
    async def emit(etype, payload):
        try:
            await send_event({"type": etype, **payload})
        except Exception:
            pass

    all_results = []
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            await emit("status", {"message": "Launching browser...", "shop": None})

            browser = await p.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--start-maximized"]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            scrapers = {
                "Amazon": scrape_amazon,
                "Flipkart": scrape_flipkart,
                "Reliance Digital": scrape_reliance_digital,
            }

            for i, shop in enumerate(SHOPS):
                shop_name = shop["name"]
                url = shop["url"].format(query=product.replace(" ", "+"))

                await emit("status", {"message": f"Opening {shop_name}...", "shop": shop_name})

                try:
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(3)

                    await page.evaluate("window.scrollBy({top: 500, behavior: 'smooth'})")
                    await asyncio.sleep(1.5)

                    await emit("status", {"message": f"Reading {shop_name}...", "shop": shop_name})

                    scraper = scrapers.get(shop_name)
                    items = await scraper(page, product) if scraper else []

                    print(f"{shop_name}: found {len(items)} items")
                    for item in items:
                        print(f"  - {item['title'][:40]} | {item['price']}")

                    await emit("shop_done", {"shop": shop_name, "items": items, "count": len(items)})
                    all_results.append({"shop": shop_name, "items": items})

                except Exception as e:
                    print(f"Error on {shop_name}: {e}")
                    await emit("shop_done", {"shop": shop_name, "items": [], "count": 0})
                    all_results.append({"shop": shop_name, "items": []})

                await asyncio.sleep(0.5)

            await browser.close()

        # Find best deal
        best = None
        best_price = float("inf")
        for shop_data in all_results:
            for item in shop_data.get("items", []):
                numbers = re.findall(r"[\d]+", item.get("price", "").replace(",", ""))
                if numbers:
                    try:
                        price = float(numbers[0])
                        if price > 100 and price < best_price:
                            best_price = price
                            best = {"shop": shop_data["shop"], **item}
                    except Exception:
                        pass

        await emit("best", {"item": best})
        await emit("status", {"message": "Done!", "shop": None})
        await emit("done", {})

    except Exception as e:
        print(f"Agent error: {e}")
        await emit("error", {"message": str(e)})
        await emit("done", {})