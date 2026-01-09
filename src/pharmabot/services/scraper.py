import re
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from seleniumbase import SB
from sqlmodel import Session, select, delete
from pharmabot.models import BasketItem, Pharmacy, Offer, ProductCatalog

console = Console()


def clean_price(text: str) -> float:
    """Extracts '12,50' from string and returns 12.5 float."""
    if not text:
        return 0.0
    # Regex: Look for digits, optional comma, digits
    match = re.search(r"(\d+(?:,\d+)?)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return 0.0


def step_1_open_site(sb):
    console.print(Panel("Step 1: Connecting...", style="cyan"))
    url = "https://www.trovaprezzi.it/"
    sb.activate_cdp_mode(url)
    if "trovaprezzi" in sb.get_current_url():
        console.print("[green]✔ Homepage Loaded[/]")
    else:
        raise Exception("Navigation Failed")


def step_2_accept_cookies(sb):
    console.print(Panel("Step 2: Cookies...", style="magenta"))
    # The robust class selector we agreed on
    cookie_btn = ".iubenda-cs-accept-btn"
    if sb.is_element_visible(cookie_btn):
        sb.click(cookie_btn)
        sb.wait_for_element_not_visible(cookie_btn, timeout=3)
        console.print("[green]✔ Cookies Accepted[/]")
    else:
        console.print("[yellow]⚠ No cookie banner (Skipping)[/]")


def step_3_search(sb, minsan):
    console.print(Panel(f"Step 3: Searching {minsan}...", style="yellow"))
    search_input = 'input[type="search"], input[name="q"]'
    sb.wait_for_element(search_input, timeout=5)
    sb.click(search_input)
    sb.type(search_input, minsan + "\n")

    console.print("[grey50]Waiting for results...[/]")
    try:
        sb.wait_for_text("€", timeout=10)
        console.print("[green]✔ Results loaded[/]")
    except Exception:
        sb.save_screenshot("search_fail.png")
        raise Exception("Search Timeout")


def step_3b_load_all_results(sb):
    """
    Responsibilities:
    1. Scroll to the bottom to trigger lazy loading.
    2. Find the "Vedi più offerte" button.
    3. Click it repeatedly until all offers are loaded.
    """
    console.print(Panel("Step 3b: Loading all offers...", style="yellow"))

    # The selector for the button you found:
    # <a class="more_offers button ...">Vedi più offerte</a>
    load_more_btn = ".more_offers.button"

    # Safety limit to prevent infinite loops (e.g., if there are 5000 results)
    max_clicks = 10
    clicks = 0

    while clicks < max_clicks:
        try:
            # 1. Scroll to the bottom to make sure the button is in view
            sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sb.sleep(1)  # Wait for animation

            # 2. Check if button exists and is visible
            if sb.is_element_visible(load_more_btn):
                console.print(
                    f"[grey50]Found 'Load More' button (Click {clicks + 1})...[/]"
                )

                # Scroll directly to element to avoid "Element not interactable"
                sb.scroll_to(load_more_btn)

                # Click it
                sb.click(load_more_btn)

                # 3. Wait for new items to appear.
                # Trovaprezzi adds a loader class or just inserts new HTML.
                # A simple sleep is safest here because DOM changes are complex to track.
                sb.sleep(3)

                clicks += 1
            else:
                # No button found? We are done.
                console.print(
                    "[green]✔ No more 'Load More' buttons found. List is complete.[/]"
                )
                break

        except Exception as e:
            console.print(f"[red]Error during pagination:[/red] {e}")
            break

    if clicks == max_clicks:
        console.print(
            "[yellow]⚠ Reached max click limit. Proceeding with current data.[/]"
        )


# --- STEP 4: EXTRACT (PYTHON) ---
def step_4_extract_results(sb):
    console.print(Panel("Step 4: Parsing (Python/BS4)...", style="green"))

    html = sb.get_page_source()
    soup = BeautifulSoup(html, "html.parser")

    # FIX: Use CSS selector instead of find_all with strict tag
    # This captures <li class="listing_item"> AND <div class="listing_item">
    items = soup.select(".listing_item")

    results = []

    for item in items:
        try:
            # 1. Pharmacy Name
            name = "Unknown"
            # Your file shows: <span class="merchant_name">Farmacia Loreto</span>
            name_el = item.select_one(".merchant_name")
            if name_el:
                name = name_el.get_text(strip=True)
            else:
                # Fallback to image alt
                img_el = item.select_one(".merchant_logo")
                if img_el:
                    name = img_el.get("alt")

            # 2. Price
            # Your file shows: <div class="item_basic_price"> 12,24 € </div>
            price = 0.0
            price_el = item.select_one(".item_basic_price")
            if price_el:
                price = clean_price(price_el.get_text())

            # 3. Shipping
            # Your file shows: <div class="item_delivery_price"> + Sped. 3,99 € </div>
            ship_price = 0.0
            ship_el = item.select_one(".item_delivery_price")
            if ship_el:
                txt = ship_el.get_text(strip=True).lower()
                if "gratis" in txt or "gratuita" in txt:
                    ship_price = 0.0
                else:
                    ship_price = clean_price(txt)

            # 4. Free Threshold
            # Your file shows: <div class="free_shipping_threshold">...<span class="block_price">49,90 €</span>
            free_over = None
            thresh_el = item.select_one(".free_shipping_threshold .block_price")
            if thresh_el:
                free_over = clean_price(thresh_el.get_text())

            results.append(
                {
                    "pharmacy": name,
                    "price": price,
                    "shipping_price": ship_price,
                    "free_shipping_over": free_over,
                }
            )

        except Exception:
            continue

    return results


def scrape_product(minsan: str = "982473682", headless: bool = True):
    """Execute all steps to gather prices information for a single product."""
    with SB(uc=True, test=True, headless=headless, locale_code="it") as sb:
        try:
            step_1_open_site(sb)
            sb.sleep(1)
            step_2_accept_cookies(sb)
            step_3_search(sb, minsan)
            sb.sleep(2)  # Allow DOM to settle
            step_3b_load_all_results(sb)
            sb.sleep(1)  # Allow DOM to settle
            offers = step_4_extract_results(sb)
            return offers

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return []


def scrape_basket(session: Session):
    """
    1. Clear Offer and Pharmacy tables.
    2. Iterate over all basket items.
    3. Scrape offers for each product.
    4. Populate DB with Pharmacy and Offer records.
    """
    console.print(Panel("Starting Basket Scraping...", style="bold magenta"))

    # 1. Clear Tables
    console.print("[yellow]Clearing existing offers and pharmacies...[/]")
    session.exec(delete(Offer))
    session.exec(delete(Pharmacy))
    session.commit()

    # 2. Get Basket Items
    basket_items = session.exec(select(BasketItem)).all()
    if not basket_items:
        console.print("[red]Basket is empty. Nothing to scrape.[/]")
        return

    # 3. Iterate and Scrape
    for item in basket_items:
        # Need to fetch the product to get the minsan
        product = session.get(ProductCatalog, item.product_id)
        if not product:
            console.print(f"[red]Product for basket item {item.id} not found.[/]")
            continue

        console.print(f"\n[bold cyan]Scraping product: {product.name} (Minsan: {product.minsan})[/]")

        # Scrape
        offers_data = scrape_product(minsan=product.minsan, headless=True)

        if not offers_data:
            console.print(f"[yellow]No offers found for {product.name}[/]")
            continue

        console.print(f"[green]Found {len(offers_data)} offers for {product.name}. Saving to DB...[/]")

        # 4. Save to DB
        for offer_data in offers_data:
            pharmacy_name = offer_data["pharmacy"]

            # Check if Pharmacy exists
            # We check by name
            pharmacy = session.exec(select(Pharmacy).where(Pharmacy.name == pharmacy_name)).first()
            if not pharmacy:
                pharmacy = Pharmacy(
                    name=pharmacy_name,
                    base_shipping_cost=offer_data["shipping_price"],
                    free_shipping_threshold=offer_data["free_shipping_over"]
                )
                session.add(pharmacy)
                session.commit()
                session.refresh(pharmacy)

            # Create Offer
            offer = Offer(
                price=offer_data["price"],
                pharmacy_id=pharmacy.id,
                product_id=product.id
            )
            session.add(offer)

        session.commit()

    console.print(Panel("Basket Scraping Complete!", style="bold green"))
