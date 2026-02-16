import re
from typing import Optional, Sequence
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, delete
from pharmabot.models import BasketItem, Pharmacy, Offer, ProductCatalog
from pharmabot.exceptions import PharmaBotMissingCookieBanner
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

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


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=5),
    retry=retry_if_exception_type(PharmaBotMissingCookieBanner),
    reraise=True,
)
def step_2_accept_cookies(sb):
    console.print(Panel("Step 2: Cookies...", style="magenta"))
    cookie_btn = ".iubenda-cs-accept-btn"
    if sb.is_element_visible(cookie_btn):
        sb.click(cookie_btn)
        console.print("[green]✔ Cookies Accepted[/]")
    else:
        console.print("[yellow]⚠ No cookie banner (Skipping)[/]")
        raise PharmaBotMissingCookieBanner("no cookie banner found")


def step_3_search(sb, query):
    search_input = 'input[type="search"], input[name="q"]'
    sb.wait_for_element(search_input, timeout=5)
    sb.click(search_input)
    sb.type(search_input, query + "\n")

    console.print("[grey50]Waiting for results...[/]")
    try:
        sb.wait_for_text("€", timeout=5)
        console.print("[green]✔ Results loaded[/]")
    except Exception:
        console.print("[yellow] Results missing, go to check for other actions[/]")
        sb.save_screenshot("search_fail.png")


def step_3_is_disambiguation_page(sb):
    """
    Returns True if the page contains the 'disambiguation no_products' div.

    Args:
        sb: The SeleniumBase sb fixture/object
    """
    return sb.is_element_visible("div.disambiguation.no_products")


def click_category_with_most_offers(sb):
    """
    Robust function using the raw driver to avoid object wrapper conflicts.
    """
    from selenium.webdriver.common.by import By

    print("Starting search for offers...")

    driver = sb.driver
    items = driver.find_elements(By.CSS_SELECTOR, "a.relevant_item")

    print(f"Found {len(items)} relevant categories.")

    max_offers = -1
    element_to_click = None

    for i, item in enumerate(items):
        try:
            counter_el = item.find_element(By.CSS_SELECTOR, ".counter")
            text_value = counter_el.text.strip()

            print(f"Item {i}: '{text_value}'")

            match = re.search(r"(\d+)", text_value)
            if match:
                count = int(match.group(1))
                if count > max_offers:
                    max_offers = count
                    element_to_click = item

        except Exception as e:
            print(f"Skipping item {i} due to error: {e}")
            continue

    if element_to_click:
        print(f"Clicking category with {max_offers} offers.")
        element_to_click.click()
    else:
        print("No offers found to click.")


def step_3_disambiguate(sb):
    click_category_with_most_offers(sb)


def step_3_load_all_results(sb):
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
    from bs4 import BeautifulSoup

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


def scrape_product(
    query: str = "012745168", headless: bool = True, wait_for_input: bool = True
):
    """Execute all steps to gather prices information for a single product."""
    from seleniumbase import SB

    with SB(uc=True, test=True, headless=headless, locale_code="it") as sb:
        try:
            step_1_open_site(sb)
            sb.sleep(2)
            step_2_accept_cookies(sb)
            console.print(Panel(f"Step 3: Searching {query}...", style="yellow"))
            step_3_search(sb, query)
            sb.sleep(2)
            if step_3_is_disambiguation_page(sb):
                # console.print("[yellow]Found disambiguation, try to fix...[/]")
                # step_3_disambiguate(sb)
                # sb.sleep(2)
                if wait_for_input:
                    console.print(
                        "[yellow]Found disambiguation, select item and then press enter...[/]"
                    )
                    input("")
                else:
                    console.print(
                        "[yellow]Found disambiguation, skipping user input (wait_for_input=False)...[/]"
                    )
            else:
                console.print("[green]load all results and go to parsing...[/]")
            step_3_load_all_results(sb)
            sb.sleep(2)
            offers = step_4_extract_results(sb)
            return offers

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return []


def scrape_basket(
    session: Session, headless: bool = True, wait_for_input: bool = True
):
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

        search_query = product.minsan if product.minsan else product.name

        console.print(
            f"\n[bold cyan]Scraping product: {product.name} (Query: {search_query})[/]"
        )

        # Scrape
        offers_data = scrape_product(
            query=search_query, headless=headless, wait_for_input=wait_for_input
        )

        if not offers_data:
            console.print(f"[yellow]No offers found for {product.name}[/]")
            continue

        console.print(
            f"[green]Found {len(offers_data)} offers for {product.name}. Saving to DB...[/]"
        )

        # 4. Save to DB
        for offer_data in offers_data:
            pharmacy_name = offer_data["pharmacy"]

            # Check if Pharmacy exists
            # We check by name
            pharmacy = session.exec(
                select(Pharmacy).where(Pharmacy.name == pharmacy_name)
            ).first()
            if not pharmacy:
                pharmacy = Pharmacy(
                    name=pharmacy_name,
                    base_shipping_cost=offer_data["shipping_price"],
                    free_shipping_threshold=offer_data["free_shipping_over"],
                )
                session.add(pharmacy)
                session.commit()
                session.refresh(pharmacy)

            # Create Offer
            offer = Offer(
                price=offer_data["price"],
                pharmacy_id=pharmacy.id,
                product_id=product.id,
            )
            session.add(offer)

        session.commit()

    console.print(Panel("Basket Scraping Complete!", style="bold green"))


def list_offers(
    session: Session,
    product_id: Optional[int] = None,
    pharmacy_id: Optional[int] = None,
) -> Sequence[Offer]:
    """
    List offers with optional filtering by product or pharmacy.
    """
    statement = (
        select(Offer)
        .join(ProductCatalog)
        .join(Pharmacy)
        .options(joinedload(Offer.product), joinedload(Offer.pharmacy))
    )

    if product_id:
        statement = statement.where(Offer.product_id == product_id)
    if pharmacy_id:
        statement = statement.where(Offer.pharmacy_id == pharmacy_id)

    # Order by Product Name then Price
    statement = statement.order_by(ProductCatalog.name, Offer.price)

    results = session.exec(statement).all()
    return results


def list_pharmacies(
    session: Session, name_filter: Optional[str] = None
) -> Sequence[Pharmacy]:
    """
    List all pharmacies from the database with optional name filtering (case-insensitive).
    """
    statement = select(Pharmacy)
    if name_filter:
        statement = statement.where(Pharmacy.name.ilike(f"%{name_filter}%"))
    statement = statement.order_by(Pharmacy.name)
    results = session.exec(statement).all()
    return results
