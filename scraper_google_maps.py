from pathlib import Path

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SEARCH_KEYWORD = "Cafe di Purwakarta"
OUTPUT_DIR = Path("output")
CSV_OUTPUT_FILE = OUTPUT_DIR / "google_maps_places.csv"
JSON_OUTPUT_FILE = OUTPUT_DIR / "google_maps_places.json"
PLACE_LINK_SELECTOR = 'a[href*="/maps/place/"]'
PLACE_CARD_SELECTOR = "xpath=ancestor::div[contains(@class, 'Nv2PK')][1]"
NAME_SELECTOR = ".qBF1Pd"
RATING_SELECTOR = ".MW4etd"
REVIEWS_SELECTOR = ".UY7F9"
CATEGORY_ROW_SELECTOR = ".W4Efsd"
DETAIL_PANEL_SELECTOR = 'div[role="main"]'
ADDRESS_SELECTORS = [
    'button[data-item-id="address"]',
    'button[aria-label^="Address:"]',
    'button[aria-label^="Alamat:"]',
]
HOURS_SELECTORS = [
    '[data-item-id="oh"]',
    '[aria-label*="Hours"]',
    '[aria-label*="Jam"]',
]
PHONE_SELECTORS = [
    'button[data-item-id^="phone:tel:"]',
    'button[aria-label^="Phone:"]',
    'button[aria-label^="Telepon:"]',
]
MENU_SELECTORS = [
    'a[aria-label*="Menu"]',
    'button[aria-label*="Menu"]',
    'a[href*="menu"]',
    'a[data-item-id*="menu"]',
    'button[data-item-id*="menu"]',
]
SCROLL_PAUSE_MS = 1500
DETAIL_RENDER_WAIT_MS = 2500
MAX_SCROLL_ATTEMPTS = 100
MAX_IDLE_SCROLLS = 3
EXPORT_COLUMNS = [
    "nama_tempat",
    "rating",
    "jumlah_ulasan",
    "kategori",
    "alamat_lengkap",
    "jam_operasional",
    "nomor_telepon",
    "menu",
    "tautan_google_maps",
]


def get_place_links(results_panel) -> set[str]:
    return set(
        results_panel.locator(PLACE_LINK_SELECTOR).evaluate_all(
            """links => links
                .map(link => link.href)
                .filter(Boolean)
            """
        )
    )


def scroll_results_until_end(page, results_panel) -> set[str]:
    place_links: set[str] = set()
    idle_scrolls = 0

    for attempt in range(1, MAX_SCROLL_ATTEMPTS + 1):
        current_links = get_place_links(results_panel)
        new_links = current_links - place_links

        if new_links:
            place_links.update(new_links)
            idle_scrolls = 0
            print(
                f"Scroll {attempt}: ditemukan {len(new_links)} tempat baru "
                f"(total {len(place_links)})."
            )
        else:
            idle_scrolls += 1
            print(
                f"Scroll {attempt}: tidak ada tempat baru "
                f"({idle_scrolls}/{MAX_IDLE_SCROLLS})."
            )

        if idle_scrolls >= MAX_IDLE_SCROLLS:
            print("Batas akhir daftar tercapai.")
            break

        panel_box = results_panel.bounding_box()
        if panel_box:
            page.mouse.move(
                panel_box["x"] + panel_box["width"] / 2,
                panel_box["y"] + panel_box["height"] / 2,
            )
            page.mouse.wheel(0, panel_box["height"])

        results_panel.evaluate(
            """panel => {
                panel.scrollBy(0, panel.scrollHeight);
            }"""
        )
        page.wait_for_timeout(SCROLL_PAUSE_MS)
    else:
        print(
            "Scroll dihentikan karena mencapai MAX_SCROLL_ATTEMPTS. "
            "Naikkan nilainya jika daftar masih berlanjut."
        )

    return place_links


def get_text_or_empty(locator, timeout: int = 1000) -> str:
    try:
        text = locator.first.inner_text(timeout=timeout).strip()
        return text
    except Exception:
        return ""


def get_attribute_or_empty(locator, attribute: str, timeout: int = 1000) -> str:
    try:
        value = locator.first.get_attribute(attribute, timeout=timeout)
        return value.strip() if value else ""
    except Exception:
        return ""


def clean_reviews_text(text: str) -> str:
    return text.replace("(", "").replace(")", "").strip()


def clean_labeled_text(text: str) -> str:
    if ":" not in text:
        return text.strip()

    return text.split(":", 1)[1].strip()


def extract_category_from_card(card) -> str:
    try:
        rows = card.locator(CATEGORY_ROW_SELECTOR).all()
        for row in rows:
            row_text = row.inner_text(timeout=1000).strip()
            if "\u00b7" not in row_text:
                continue

            parts = [part.strip() for part in row_text.split("\u00b7") if part.strip()]
            for part in parts:
                if any(char.isdigit() for char in part):
                    continue
                if part.lower() in {"buka", "tutup", "open", "closed"}:
                    continue
                return part
    except Exception:
        return ""

    return ""


def extract_places_data(results_panel) -> list[dict[str, str]]:
    places: list[dict[str, str]] = []
    processed_links: set[str] = set()
    place_links = results_panel.locator(PLACE_LINK_SELECTOR)

    for index in range(place_links.count()):
        link = place_links.nth(index)
        href = get_attribute_or_empty(link, "href")

        if href in processed_links:
            continue

        processed_links.add(href)

        try:
            card = link.locator(PLACE_CARD_SELECTOR)

            name = get_attribute_or_empty(link, "aria-label")
            if not name:
                name = get_text_or_empty(card.locator(NAME_SELECTOR))

            rating = get_text_or_empty(card.locator(RATING_SELECTOR))
            reviews = clean_reviews_text(get_text_or_empty(card.locator(REVIEWS_SELECTOR)))
            category = extract_category_from_card(card)

            places.append(
                {
                    "nama_tempat": name,
                    "rating": rating,
                    "jumlah_ulasan": reviews,
                    "kategori": category,
                    "alamat_lengkap": "",
                    "jam_operasional": "",
                    "nomor_telepon": "",
                    "menu": "",
                    "tautan_google_maps": href,
                }
            )
        except Exception as error:
            print(f"Gagal mengekstrak kartu ke-{index + 1}: {error}")
            places.append(
                {
                    "nama_tempat": "",
                    "rating": "",
                    "jumlah_ulasan": "",
                    "kategori": "",
                    "alamat_lengkap": "",
                    "jam_operasional": "",
                    "nomor_telepon": "",
                    "menu": "",
                    "tautan_google_maps": href,
                }
            )

    return places


def wait_for_detail_panel(page) -> None:
    try:
        page.locator(DETAIL_PANEL_SELECTOR).wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        print("Panel detail belum terdeteksi, lanjut setelah jeda tambahan.")

    page.wait_for_timeout(DETAIL_RENDER_WAIT_MS)


def get_detail_value(page, selectors: list[str]) -> str:
    for selector in selectors:
        locator = page.locator(selector)

        value = get_attribute_or_empty(locator, "aria-label")
        if value:
            return clean_labeled_text(value)

        value = get_text_or_empty(locator)
        if value:
            return clean_labeled_text(value)

    return ""


def get_menu_info(page) -> str:
    for selector in MENU_SELECTORS:
        locator = page.locator(selector)

        href = get_attribute_or_empty(locator, "href")
        if href:
            return href

        label = get_attribute_or_empty(locator, "aria-label")
        if label:
            return label

        text = get_text_or_empty(locator)
        if text:
            return text

    return ""


def open_place_detail(page, results_panel, place: dict[str, str], index: int) -> None:
    href = place.get("tautan_google_maps", "")
    link = results_panel.locator(f'a[href="{href}"]').first if href else None

    if link:
        try:
            link.scroll_into_view_if_needed(timeout=5000)
            link.click(timeout=5000)
            wait_for_detail_panel(page)
            return
        except Exception as error:
            print(
                f"Gagal klik kartu ke-{index + 1}, buka lewat tautan. "
                f"Detail error: {error}"
            )

    if href:
        page.goto(href, wait_until="domcontentloaded")
        wait_for_detail_panel(page)


def back_to_results(page, results_panel) -> None:
    try:
        page.go_back(wait_until="domcontentloaded", timeout=10000)
        results_panel.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(1000)
    except Exception:
        pass


def enrich_places_with_detail_data(page, results_panel, places: list[dict[str, str]]) -> None:
    for index, place in enumerate(places):
        print(f"Membuka detail tempat {index + 1}/{len(places)}: {place['nama_tempat']}")

        try:
            open_place_detail(page, results_panel, place, index)

            place["alamat_lengkap"] = get_detail_value(page, ADDRESS_SELECTORS)
            place["jam_operasional"] = get_detail_value(page, HOURS_SELECTORS)
            place["nomor_telepon"] = get_detail_value(page, PHONE_SELECTORS)
            place["menu"] = get_menu_info(page)
        except Exception as error:
            print(f"Gagal mengekstrak panel detail ke-{index + 1}: {error}")
            place["alamat_lengkap"] = ""
            place["jam_operasional"] = ""
            place["nomor_telepon"] = ""
            place["menu"] = ""
        finally:
            if index < len(places) - 1:
                back_to_results(page, results_panel)


def print_places_data(places: list[dict[str, str]]) -> None:
    print("\nData tempat:")
    for number, place in enumerate(places, start=1):
        print(f"{number}. Nama Tempat   : {place['nama_tempat']}")
        print(f"   Rating        : {place['rating']}")
        print(f"   Jumlah Ulasan : {place['jumlah_ulasan']}")
        print(f"   Kategori      : {place['kategori']}")
        print(f"   Alamat        : {place.get('alamat_lengkap', '')}")
        print(f"   Jam           : {place.get('jam_operasional', '')}")
        print(f"   Telepon       : {place.get('nomor_telepon', '')}")
        print(f"   Menu          : {place.get('menu', '')}")
        print()


def export_places_data(places: list[dict[str, str]]) -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = []
    for place in places:
        data.append({column: place.get(column, "") for column in EXPORT_COLUMNS})

    df = pd.DataFrame(data, columns=EXPORT_COLUMNS)
    df.to_csv(CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    df.to_json(
        JSON_OUTPUT_FILE,
        orient="records",
        indent=2,
        force_ascii=False,
    )

    print(f"CSV berhasil dibuat : {CSV_OUTPUT_FILE}")
    print(f"JSON berhasil dibuat: {JSON_OUTPUT_FILE}")
    return df


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", wait_until="domcontentloaded")

        search_box = page.locator("input#searchboxinput")
        search_box.wait_for(state="visible", timeout=30000)
        search_box.fill(SEARCH_KEYWORD)
        search_box.press("Enter")

        results_panel = page.locator('div[role="feed"]')

        try:
            results_panel.wait_for(state="visible", timeout=30000)
            results_panel.locator(PLACE_LINK_SELECTOR).first.wait_for(
                state="visible",
                timeout=30000,
            )
            print(f"Panel hasil untuk '{SEARCH_KEYWORD}' sudah termuat.")
        except PlaywrightTimeoutError:
            print("Panel hasil belum termuat dalam batas waktu yang ditentukan.")
            raise

        place_links = scroll_results_until_end(page, results_panel)
        print(f"Total tempat yang berhasil dimuat: {len(place_links)}")

        places = extract_places_data(results_panel)
        print(f"Total data tempat yang berhasil diekstrak: {len(places)}")
        enrich_places_with_detail_data(page, results_panel, places)
        print_places_data(places)
        export_places_data(places)

        input("Tekan Enter untuk menutup browser...")
        browser.close()


if __name__ == "__main__":
    main()
