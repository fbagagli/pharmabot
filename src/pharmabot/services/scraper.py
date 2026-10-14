import os
import random
import re
import time
from typing import Any, Optional, Sequence
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, delete
from pharmabot.models import BasketItem, Pharmacy, Offer, ProductCatalog

console = Console()

BROWSER_PROFILE_DIR = os.environ.get(
    "PHARMABOT_PROFILE_DIR",
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".browser_profile")
    ),
)


def get_browser_session(headless: bool = True):
    """Create and return a configured SeleniumBase session context manager with persistent profile."""
    from seleniumbase import SB

    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    return SB(
        uc=True,
        test=False,
        headless=headless,
        locale_code="it",
        user_data_dir=BROWSER_PROFILE_DIR,
    )


def clean_price(text: str) -> float:
    """Extracts '12,50' from string and returns 12.5 float."""
    if not text:
        return 0.0
    # Regex: Look for digits, optional comma, digits
    match = re.search(r"(\d+(?:,\d+)?)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return 0.0


def reset_browser_profile() -> None:
    """Remove the persistent browser profile directory to clear any poisoned cookies or state."""
    import shutil

    if os.path.exists(BROWSER_PROFILE_DIR):
        try:
            shutil.rmtree(BROWSER_PROFILE_DIR, ignore_errors=True)
            console.print("[green]✔ Browser session profile reset successfully.[/]")
        except Exception as e:
            console.print(f"[red]Error resetting browser profile: {e}[/]")
    else:
        console.print(
            "[yellow]Browser profile directory does not exist (already clean).[/]"
        )


def is_datadome_present(sb) -> bool:
    """Check if the current page contains a DataDome challenge or CAPTCHA."""
    try:
        if sb.is_element_present('iframe[title*="DataDome"]') or sb.is_element_present(
            'iframe[src*="captcha-delivery.com"]'
        ):
            return True
        source = sb.get_page_source().lower()
        if "captcha-delivery.com" in source or (
            "datadome" in source and "var dd=" in source
        ):
            return True
    except Exception:
        pass
    return False


def is_datadome_blocked(sb) -> bool:
    """Check if the current page is the permanent 403 block page."""
    try:
        source = sb.get_page_source().lower()
        if any(
            phrase in source
            for phrase in [
                "ci ha insospettiti",
                "velocità sovrumana",
                "accesso temporaneamente limitato",
                "accesso temporaneamente disabilitato",
                "un robot è sulla tua stessa rete",
            ]
        ):
            return True
    except Exception:
        pass
    return False


def check_and_handle_datadome(sb, wait_for_input: bool = True):
    """Checks if a DataDome 403 block or CAPTCHA puzzle is present.

    If blocked (403), clears the profile and raises an Exception.
    If a puzzle is present, waits up to 90 seconds for human-in-the-loop resolution.
    """
    if is_datadome_blocked(sb):
        console.print(
            "[bold red]⚠ Detected DataDome 403 block page! Session was poisoned.[/]"
        )
        reset_browser_profile()
        raise Exception(
            "Access blocked by DataDome (session poisoned). "
            "Profile was automatically cleared. Please retry."
        )

    if is_datadome_present(sb):
        console.print("[bold yellow]⚠ DataDome CAPTCHA challenge detected![/]")
        console.print(
            "[bold cyan]Please solve the puzzle in the Chrome window. "
            "Waiting for resolution (up to 90s)...[/]"
        )

        solved = False
        start_time = time.time()
        while time.time() - start_time < 90:
            sb.sleep(2)
            if is_datadome_blocked(sb):
                console.print("[bold red]⚠ Challenge failed; session was blocked.[/]")
                reset_browser_profile()
                raise Exception("DataDome challenge failed. Profile cleared.")
            if not is_datadome_present(sb):
                console.print(
                    "[bold green]✔ DataDome challenge resolved! Real page loaded.[/]"
                )
                solved = True
                break

        if not solved:
            if wait_for_input:
                console.print(
                    "[yellow]Press Enter after solving the CAPTCHA in the browser window...[/]"
                )
                try:
                    input("")
                except Exception:
                    pass
                if not is_datadome_present(sb) and not is_datadome_blocked(sb):
                    solved = True

            if not solved:
                raise Exception("DataDome CAPTCHA was not resolved within timeout.")


def step_1_open_site(sb, wait_for_input: bool = True):
    console.print(Panel("Step 1: Connecting...", style="cyan"))
    url = "https://www.trovaprezzi.it/"
    try:
        current_url = sb.get_current_url()
        if (
            "trovaprezzi" in current_url
            and not is_datadome_present(sb)
            and not is_datadome_blocked(sb)
        ):
            console.print("[green]✔ Already on Trovaprezzi, reusing page[/]")
            return
    except Exception:
        pass

    sb.activate_cdp_mode(url)
    sb.sleep(random.uniform(1.5, 2.5))
    check_and_handle_datadome(sb, wait_for_input=wait_for_input)

    if "trovaprezzi" in sb.get_current_url() and not is_datadome_blocked(sb):
        console.print("[green]✔ Homepage Loaded[/]")
    else:
        raise Exception("Navigation Failed or Blocked")


def step_2_accept_cookies(sb):
    console.print(Panel("Step 2: Cookies...", style="magenta"))
    cookie_btn = ".iubenda-cs-accept-btn"
    try:
        # Give the cookie banner up to 3 seconds to render if not already accepted
        try:
            sb.wait_for_element_visible(cookie_btn, timeout=3)
            sb.sleep(random.uniform(0.4, 0.8))
            sb.click(cookie_btn)
            console.print("[green]✔ Cookies Accepted[/]")
            sb.sleep(random.uniform(0.5, 1.0))
        except Exception:
            console.print(
                "[yellow]✔ Cookie banner not present (already accepted or not shown)[/]"
            )
    except Exception as e:
        console.print(f"[yellow]⚠ Cookie check: {e}[/]")


def step_3_search(sb, query: str, wait_for_input: bool = True):
    search_input = 'input[type="search"], input[name="q"]'
    sb.wait_for_element(search_input, timeout=10)

    # Human-like delay before clicking the search box
    sb.sleep(random.uniform(0.3, 0.7))
    sb.click(search_input)
    sb.sleep(random.uniform(0.2, 0.4))

    # Clear input if previous search text remains
    try:
        sb.clear(search_input)
    except Exception:
        pass
    try:
        from selenium.webdriver.common.keys import Keys

        sb.send_keys(search_input, Keys.CONTROL + "a")
        sb.send_keys(search_input, Keys.BACKSPACE)
    except Exception:
        pass

    console.print(f"[grey50]Typing query at human speed: {query}...[/]")
    sb.press_keys(search_input, query)

    # Natural hesitation before pressing Enter
    sb.sleep(random.uniform(0.5, 1.2))
    sb.send_keys(search_input, "\n")

    console.print("[grey50]Waiting for results or disambiguation...[/]")
    loaded = False
    start_time = time.time()
    while time.time() - start_time < 8:
        if is_datadome_blocked(sb) or is_datadome_present(sb):
            check_and_handle_datadome(sb, wait_for_input=wait_for_input)
            break
        if sb.is_text_visible("€") or sb.is_element_visible("div.listing_item"):
            console.print("[green]✔ Results loaded directly[/]")
            loaded = True
            break
        if step_3_is_disambiguation_page(sb):
            console.print("[yellow]✔ Disambiguation page loaded[/]")
            loaded = True
            break
        sb.sleep(0.5)

    if not loaded and not step_3_is_disambiguation_page(sb):
        console.print("[yellow] Results missing, go to check for other actions[/]")
        sb.save_screenshot("search_fail.png")


def step_3_is_disambiguation_page(sb):
    """Returns True if the page contains disambiguation elements or categories.

    Args:
        sb: The SeleniumBase sb fixture/object
    """
    try:
        return (
            sb.is_element_visible("div.disambiguation")
            or sb.is_element_visible("a.relevant_item")
            or sb.is_element_visible(".disambiguation_items")
        )
    except Exception:
        return False


def click_category_with_most_offers(sb):
    """Finds the category with the most offers and navigates to its URL.

    Navigating via sb.open(href) avoids synthetic DOM click events (isTrusted: false)
    monitored by DataDome.
    """
    from selenium.webdriver.common.by import By

    console.print("[grey50]Searching for category with most offers...[/]")

    driver = sb.driver
    items = driver.find_elements(By.CSS_SELECTOR, "a.relevant_item")

    console.print(f"[grey50]Found {len(items)} relevant categories.[/]")

    max_offers = -1
    best_item = None
    target_url = None

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
                    best_item = item
                    target_url = item.get_attribute("href")

        except Exception as e:
            console.print(f"[yellow]Skipping item {i} due to error: {e}[/]")
            continue

    if target_url:
        if target_url.startswith("/"):
            target_url = f"https://www.trovaprezzi.it{target_url}"
        console.print(
            f"[green]Navigating via href to category with {max_offers} offers: {target_url}[/]"
        )
        sb.sleep(random.uniform(0.6, 1.2))
        sb.open(target_url)
    elif best_item:
        console.print(
            f"[yellow]No href found, falling back to click for {max_offers} offers.[/]"
        )
        best_item.click()
    else:
        console.print("[yellow]No offers found to click.[/]")


def step_3_disambiguate(sb, wait_for_input: bool = True):
    if wait_for_input:
        console.print(
            "[bold yellow]Found disambiguation page![/]\n"
            "[cyan]You can manually click the desired category in the browser window.\n"
            "Waiting up to 10 seconds before auto-selecting category with most offers...[/]"
        )
        start_time = time.time()
        while time.time() - start_time < 10:
            sb.sleep(1)
            # If the user clicked manually, the disambiguation page will disappear
            if not step_3_is_disambiguation_page(sb):
                console.print("[green]✔ Category selected manually![/]")
                return

    # Auto-select the category with most offers
    click_category_with_most_offers(sb)


def step_3_load_all_results(sb):
    """Responsibilities:
    1. Scroll to the bottom to trigger lazy loading.
    2. Find the "Vedi più offerte" button.
    3. Click it repeatedly until all offers are loaded.
    """
    console.print(Panel("Step 3b: Loading all offers...", style="yellow"))

    load_more_btn = ".more_offers.button"

    # Safety limit to prevent infinite loops (e.g., if there are 5000 results)
    max_clicks = 10
    clicks = 0

    while clicks < max_clicks:
        try:
            if is_datadome_blocked(sb):
                console.print("[bold red]⚠ Blocked during pagination.[/]")
                break

            # 1. Scroll gently towards bottom to trigger lazy loading
            sb.sleep(random.uniform(0.8, 1.5))
            sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sb.sleep(random.uniform(1.0, 1.8))

            # 2. Check if button exists and is visible
            if sb.is_element_visible(load_more_btn):
                console.print(
                    f"[grey50]Found 'Load More' button (Click {clicks + 1})...[/]"
                )

                # Scroll directly to element to avoid "Element not interactable"
                sb.scroll_to(load_more_btn)
                sb.sleep(random.uniform(1.2, 2.5))

                # Click it
                sb.click(load_more_btn)

                # 3. Wait for new items to appear with natural pause
                sb.sleep(random.uniform(2.5, 4.0))

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


def _execute_scrape_steps(sb, query: str, wait_for_input: bool = True):
    step_1_open_site(sb, wait_for_input=wait_for_input)
    sb.sleep(random.uniform(1.0, 1.8))
    step_2_accept_cookies(sb)
    console.print(Panel(f"Step 3: Searching {query}...", style="yellow"))
    step_3_search(sb, query, wait_for_input=wait_for_input)
    sb.sleep(random.uniform(1.5, 2.5))
    check_and_handle_datadome(sb, wait_for_input=wait_for_input)
    if step_3_is_disambiguation_page(sb):
        step_3_disambiguate(sb, wait_for_input=wait_for_input)
        check_and_handle_datadome(sb, wait_for_input=wait_for_input)
    else:
        console.print("[green]load all results and go to parsing...[/]")
    step_3_load_all_results(sb)
    sb.sleep(random.uniform(1.0, 2.0))
    offers = step_4_extract_results(sb)
    return offers


def scrape_product(
    query: str = "012745168",
    headless: bool = True,
    wait_for_input: bool = True,
    sb: Optional[Any] = None,
):
    """Execute all steps to gather prices information for a single product."""
    if sb is not None:
        try:
            return _execute_scrape_steps(sb, query, wait_for_input=wait_for_input)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return []
    else:
        try:
            with get_browser_session(headless=headless) as new_sb:
                return _execute_scrape_steps(
                    new_sb, query, wait_for_input=wait_for_input
                )
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return []


def clear_database(session: Session):
    """
    Clear Offer and Pharmacy tables.
    """
    console.print("[yellow]Clearing existing offers and pharmacies...[/]")
    session.exec(delete(Offer))
    session.exec(delete(Pharmacy))
    session.commit()
    console.print("[green]✔ Database cleared.[/]")


def scrape_basket(session: Session, headless: bool = True, wait_for_input: bool = True):
    """
    1. Iterate over all basket items.
    2. Filter items not yet scraped.
    3. Open a single browser session with persistent profile.
    4. Scrape offers for each product with human delay (jitter).
    5. Populate DB with Pharmacy and Offer records.
    """
    console.print(Panel("Starting Basket Scraping...", style="bold magenta"))

    # 1. Get Basket Items
    basket_items = session.exec(select(BasketItem)).all()
    if not basket_items:
        console.print("[red]Basket is empty. Nothing to scrape.[/]")
        return

    # 2. Filter items needing scraping
    items_to_scrape = []
    for item in basket_items:
        product = session.get(ProductCatalog, item.product_id)
        if not product:
            console.print(f"[red]Product for basket item {item.id} not found.[/]")
            continue

        existing_offer = session.exec(
            select(Offer).where(Offer.product_id == product.id)
        ).first()
        if existing_offer:
            console.print(
                f"[yellow]Skipping {product.name} (already has offers in DB).[/]"
            )
            continue

        items_to_scrape.append((item, product))

    if not items_to_scrape:
        console.print("[green]All items in basket are already scraped.[/]")
        return

    console.print(
        f"[cyan]Found {len(items_to_scrape)} item(s) to scrape. Starting browser session...[/]"
    )

    # 3. Single browser session for the entire basket
    with get_browser_session(headless=headless) as sb:
        for idx, (item, product) in enumerate(items_to_scrape):
            search_query = product.minsan if product.minsan else product.name

            console.print(
                f"\n[bold cyan][{idx + 1}/{len(items_to_scrape)}] Scraping: {product.name} (Query: {search_query})[/]"
            )

            # Scrape reusing sb
            offers_data = scrape_product(
                query=search_query,
                headless=headless,
                wait_for_input=wait_for_input,
                sb=sb,
            )

            if not offers_data:
                console.print(f"[yellow]No offers found for {product.name}[/]")
            else:
                console.print(
                    f"[green]Found {len(offers_data)} offers for {product.name}. Saving to DB...[/]"
                )

                # Save to DB
                for offer_data in offers_data:
                    pharmacy_name = offer_data["pharmacy"]

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

                    offer = Offer(
                        price=offer_data["price"],
                        pharmacy_id=pharmacy.id,
                        product_id=product.id,
                    )
                    session.add(offer)

                session.commit()

            # 4. Human jitter between items
            if idx < len(items_to_scrape) - 1:
                pause_duration = random.uniform(2.5, 4.5)
                console.print(
                    f"[grey50]Pausing for {pause_duration:.1f}s before next product...[/]"
                )
                time.sleep(pause_duration)

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
