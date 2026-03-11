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
        "name": "Croma",
        "url": "https://www.croma.com/searchB?q={query}",
    },
]

async def scrape_amazon(page, product: str) -> list:
    items = []
    try:
        results = await page.query_selector_all("div[data-component-type='s-search-result']")
        for r in results[:5]:
            try:
                # Title - try multiple selectors
                title = None
                for sel in ["h2 span", "h2 a span", ".a-text-normal"]:
                    el = await r.query_selector(sel)
                    if el:
                        title = (await el.inner_text()).strip()
                        if title:
                            break

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

                if title and price:
                    price = price.replace("\n", "").split("₹")[-1]
                    price = "₹" + price.strip().split("\n")[0]
                    items.append({"title": title[:80], "price": price, "rating": rating, "delivery": "N/A"})
            except Exception:
                continue
    except Exception as e:
        print(f"Amazon scrape error: {e}")
    return items[:3]

async def scrape_flipkart(page, product: str) -> list:
    items = []
    try:
        # Try multiple container selectors
        containers = []
        for sel in ["div._1AtVbE", "div._13oc-S", "div.cPHDOP", "div[data-id]"]:
            containers = await page.query_selector_all(sel)
            if len(containers) > 2:
                break

        for r in containers[:8]:
            try:
                title = None
                for sel in ["._4rR01T", ".s1Q9rs", ".IRpwTa", "a[title]", "div.col-7-12 a"]:
                    el = await r.query_selector(sel)
                    if el:
                        title = (await el.inner_text()).strip()
                        if len(title) > 5:
                            break

                price = None
                for sel in ["._30jeq3", "._1_WHN1", "div._25b18c ._30jeq3", "._3tbVC0"]:
                    el = await r.query_selector(sel)
                    if el:
                        price = (await el.inner_text()).strip()
                        if price:
                            break

                rating = "N/A"
                for sel in ["._3LWZlK", "._1lRcqv span"]:
                    el = await r.query_selector(sel)
                    if el:
                        rating = (await el.inner_text()).strip()[:10]
                        if rating:
                            break

                if title and price and len(title) > 5:
                    if not price.startswith("₹"):
                        price = "₹" + price.replace("₹","").strip()
                    items.append({"title": title[:80], "price": price, "rating": rating, "delivery": "N/A"})
            except Exception:
                continue
    except Exception as e:
        print(f"Flipkart scrape error: {e}")
    return items[:3]

async def scrape_croma(page, product: str) -> list:
    items = []
    try:
        for sel in [".cp-product", "li.product", ".product-item", "article"]:
            containers = await page.query_selector_all(sel)
            if len(containers) > 1:
                for r in containers[:5]:
                    try:
                        title = None
                        for ts in ["h3", ".product-title", "a.product-title", "h4"]:
                            el = await r.query_selector(ts)
                            if el:
                                title = (await el.inner_text()).strip()
                                if len(title) > 5:
                                    break

                        price = None
                        for ps in [".amount", ".new-price", "span.amount", "[class*='price']"]:
                            el = await r.query_selector(ps)
                            if el:
                                price = (await el.inner_text()).strip()
                                if price and any(c.isdigit() for c in price):
                                    break

                        if title and price:
                            if not price.startswith("₹"):
                                price = "₹" + price.replace("₹","").strip()
                            items.append({"title": title[:80], "price": price, "rating": "N/A", "delivery": "N/A"})
                    except Exception:
                        continue
                if items:
                    break
    except Exception as e:
        print(f"Croma scrape error: {e}")
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
                "Croma": scrape_croma,
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