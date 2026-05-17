from pathlib import Path
import os

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# --- KONFIGURASI DAN ORNAMEN TERMINAL (ANSI COLORS) ---
# Trik mengaktifkan ANSI escape sequence di terminal Windows (PowerShell/CMD)
os.system('')

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_MAGENTA = '\033[95m'
C_BLUE = '\033[94m'
C_BOLD = '\033[1m'
C_RESET = '\033[0m'

# Font besar (ASCII Art) dinamis 5x5 untuk mempercantik judul pencarian
BLOCK_FONT = {
    'A': ["  █  ", " █ █ ", "█████", "█   █", "█   █"],
    'B': ["████ ", "█   █", "████ ", "█   █", "████ "],
    'C': [" ███ ", "█    ", "█    ", "█    ", " ███ "],
    'D': ["████ ", "█   █", "█   █", "█   █", "████ "],
    'E': ["█████", "█    ", "███  ", "█    ", "█████"],
    'F': ["█████", "█    ", "███  ", "█    ", "█    "],
    'G': [" ███ ", "█    ", "█  ██", "█   █", " ███ "],
    'H': ["█   █", "█   █", "█████", "█   █", "█   █"],
    'I': ["███", " █ ", " █ ", " █ ", "███"],
    'J': ["  ███", "    █", "    █", "█   █", " ███ "],
    'K': ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    'L': ["█    ", "█    ", "█    ", "█    ", "█████"],
    'M': ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    'N': ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    'O': [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    'P': ["████ ", "█   █", "████ ", "█    ", "█    "],
    'Q': [" ███ ", "█   █", "█ █ █", "█  █ ", " ████"],
    'R': ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    'S': [" ████", "█    ", " ███ ", "    █", "████ "],
    'T': ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    'U': ["█   █", "█   █", "█   █", "█   █", " ███ "],
    'V': ["█   █", "█   █", " █ █ ", " █ █ ", "  █  "],
    'W': ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    'X': ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    'Y': ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    'Z': ["█████", "   █ ", "  █  ", " █   ", "█████"],
    ' ': ["     ", "     ", "     ", "     ", "     "],
}

def print_large_word(word: str) -> None:
    """Mencetak sebuah kata dengan huruf blok ASCII besar 5x5."""
    word = "".join(c for c in word.upper() if c in BLOCK_FONT)
    if not word:
        return
        
    # Ambil maksimal 8 huruf agar tidak melebihi batas lebar terminal
    word = word[:8]
    
    lines = ["", "", "", "", ""]
    for char in word:
        char_lines = BLOCK_FONT.get(char, ["█████"] * 5)
        for i in range(5):
            lines[i] += char_lines[i] + "  "
            
    print(f"{C_MAGENTA}{C_BOLD}")
    for line in lines:
        print(f"  {line}")
    print(f"{C_RESET}")

def print_banner(keyword: str) -> None:
    """Mencetak hiasan ornamen terminal dan teks besar kata kunci utama."""
    # Bersihkan layar
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Ambil kata kunci utama (kata pertama)
    first_word = keyword.split()[0] if keyword else "SCRAPER"
    
    border = "⚡" * 38
    print(f"\n{C_CYAN}{border}{C_RESET}")
    print(f"{C_CYAN}  ✨ INTI PENCARIAN DIREKTORI DITEMUKAN ✨{C_RESET}")
    
    # Cetak teks besar
    print_large_word(first_word)
    
    print(f"{C_CYAN}  📌 Target    : {C_BOLD}{C_YELLOW}{keyword.upper()}{C_RESET}")
    print(f"{C_CYAN}  🚀 Status    : {C_BOLD}{C_GREEN}MEMULAI PROSES SCRAPING...{C_RESET}")
    print(f"{C_CYAN}{border}\n{C_RESET}")

SEARCH_KEYWORD = ""
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
                f"{C_GREEN}[🔄 Scroll {attempt:02d}]{C_RESET} Ditemukan "
                f"{C_YELLOW}{C_BOLD}{len(new_links)}{C_RESET} tempat baru "
                f"(Total: {C_CYAN}{len(place_links)}{C_RESET})"
            )
        else:
            idle_scrolls += 1
            print(
                f"{C_YELLOW}[⏳ Scroll {attempt:02d}]{C_RESET} Tidak ada tempat baru "
                f"(Idle: {idle_scrolls}/{MAX_IDLE_SCROLLS})"
            )

        if idle_scrolls >= MAX_IDLE_SCROLLS:
            print(f"\n{C_MAGENTA}🏁 [INFO] Batas akhir daftar tempat telah tercapai.{C_RESET}")
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
            f"\n{C_RED}⚠️ [PERINGATAN] Scroll dihentikan karena mencapai MAX_SCROLL_ATTEMPTS ({MAX_SCROLL_ATTEMPTS})."
            f" Naikkan nilainya jika daftar masih berlanjut.{C_RESET}"
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
    print(f"\n{C_CYAN}⭐ Memulai Pengumpulan Detail Tempat ({len(places)} total tempat)...{C_RESET}\n")
    for index, place in enumerate(places):
        print(
            f"{C_BLUE}[🔍 Detail {index + 1}/{len(places)}]{C_RESET} "
            f"Mengekstrak: {C_BOLD}{C_YELLOW}{place['nama_tempat']}{C_RESET}"
        )

        try:
            open_place_detail(page, results_panel, place, index)

            place["alamat_lengkap"] = get_detail_value(page, ADDRESS_SELECTORS)
            place["jam_operasional"] = get_detail_value(page, HOURS_SELECTORS)
            place["nomor_telepon"] = get_detail_value(page, PHONE_SELECTORS)
            place["menu"] = get_menu_info(page)
        except Exception as error:
            print(f"  {C_RED}❌ Gagal mengekstrak panel detail ke-{index + 1}: {error}{C_RESET}")
            place["alamat_lengkap"] = ""
            place["jam_operasional"] = ""
            place["nomor_telepon"] = ""
            place["menu"] = ""
        finally:
            if index < len(places) - 1:
                back_to_results(page, results_panel)


def print_places_data(places: list[dict[str, str]]) -> None:
    print(f"\n{C_MAGENTA}╔═══════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_MAGENTA}║               🌟 HASIL EKSTRAKSI DATA TEMPAT 🌟               ║{C_RESET}")
    print(f"{C_MAGENTA}╚═══════════════════════════════════════════════════════════════╝{C_RESET}\n")
    
    for number, place in enumerate(places, start=1):
        rating_star = f"⭐ {place['rating']}" if place['rating'] else "-"
        reviews_count = f"({place['jumlah_ulasan']} ulasan)" if place['jumlah_ulasan'] else ""
        
        print(f"  {C_CYAN}┌───────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"  {C_CYAN}│{C_RESET} {C_BOLD}{C_GREEN}{number:02d}. {place['nama_tempat']}{C_RESET}")
        print(f"  {C_CYAN}├───────────────────────────────────────────────────────────┤{C_RESET}")
        print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Rating{C_RESET}      : {C_YELLOW}{rating_star} {reviews_count}{C_RESET}")
        print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Kategori{C_RESET}    : {place['kategori']}")
        print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Alamat{C_RESET}      : {place.get('alamat_lengkap', '-')}")
        print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Telepon{C_RESET}     : {place.get('nomor_telepon', '-')}")
        print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Jam Buka{C_RESET}    : {place.get('jam_operasional', '-')}")
        if place.get('menu'):
            print(f"  {C_CYAN}│{C_RESET}  👉 {C_BOLD}Menu{C_RESET}        : {C_BLUE}{place.get('menu')}{C_RESET}")
        print(f"  {C_CYAN}└───────────────────────────────────────────────────────────┘{C_RESET}\n")


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

    print(f"🎉 {C_GREEN}{C_BOLD}[BERHASIL EXPORT]{C_RESET} Data disimpan:")
    print(f"   💾 CSV  : {C_CYAN}{CSV_OUTPUT_FILE}{C_RESET}")
    print(f"   💾 JSON : {C_CYAN}{JSON_OUTPUT_FILE}{C_RESET}\n")
    return df


def main() -> None:
    global SEARCH_KEYWORD
    
    # Judul pembuka interaktif yang rapi
    print(f"\n{C_MAGENTA}╔═══════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_MAGENTA}║               🗺️  GOOGLE MAPS PLAYWRIGHT SCRAPER              ║{C_RESET}")
    print(f"{C_MAGENTA}║                     Premium CLI Edition                       ║{C_RESET}")
    print(f"{C_MAGENTA}╚═══════════════════════════════════════════════════════════════╝{C_RESET}\n")
    
    print(f"  {C_CYAN}💬 Halo bos! Selamat datang di asisten scraper Google Maps.{C_RESET}")
    print(f"  {C_CYAN}💬 Masukkan apa saja yang ingin bos cari di bawah ini.{C_RESET}\n")
    
    # Input interaktif
    user_input = input(f"  {C_BOLD}{C_YELLOW}[?] Mau cari apa boss?{C_RESET} {C_CYAN}👉{C_RESET} ").strip()
    if not user_input:
        user_input = "Hotel di Purwakarta"
        print(f"  {C_YELLOW}⚠️  Input kosong. Menggunakan default: '{user_input}'{C_RESET}")
        
    SEARCH_KEYWORD = user_input
    
    # Tampilkan banner besar dengan ornamen
    print_banner(SEARCH_KEYWORD)
    
    print(f"{C_BLUE}[🚀 PROSES] Membuka browser Playwright...{C_RESET}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print(f"{C_BLUE}[🚀 PROSES] Masuk ke Google Maps...{C_RESET}")
        page.goto("https://www.google.com/maps", wait_until="domcontentloaded")

        # Coba beberapa selector kotak pencarian yang umum
        search_box = page.locator("input#searchboxinput, input.UGojuc, input[role='combobox']").first
        try:
            search_box.wait_for(state="visible", timeout=15000)
            print(f"{C_GREEN}[✔ SUKSES]{C_RESET} Kotak pencarian Google Maps siap.")
        except PlaywrightTimeoutError:
            print(f"{C_YELLOW}[⚠️ INFO]{C_RESET} Mencoba selector alternatif...")
            search_box = page.locator("input").first
            search_box.wait_for(state="visible", timeout=15000)

        print(f"{C_BLUE}[🚀 PROSES] Mengetik kata kunci: '{SEARCH_KEYWORD}'...{C_RESET}")
        search_box.fill(SEARCH_KEYWORD)
        page.wait_for_timeout(1000)   # Tunggu sebentar setelah mengetik agar stabil
        page.keyboard.press("Enter")   # Kirim tombol Enter secara global untuk menghindari element detachment

        results_panel = page.locator('div[role="feed"]')

        try:
            print(f"{C_BLUE}[🚀 PROSES] Menunggu hasil pencarian dimuat...{C_RESET}")
            results_panel.wait_for(state="visible", timeout=30000)
            results_panel.locator(PLACE_LINK_SELECTOR).first.wait_for(
                state="visible",
                timeout=30000,
            )
            print(f"{C_GREEN}[✔ SUKSES]{C_RESET} Panel hasil untuk '{SEARCH_KEYWORD}' berhasil termuat.\n")
        except PlaywrightTimeoutError:
            print(f"{C_RED}❌ [ERROR] Panel hasil belum termuat dalam batas waktu yang ditentukan.{C_RESET}")
            raise

        print(f"{C_CYAN}⭐ Memulai auto-scrolling untuk memuat semua data tempat...{C_RESET}")
        place_links = scroll_results_until_end(page, results_panel)
        print(f"\n{C_GREEN}[✔ SELESAI]{C_RESET} Berhasil memuat total {C_YELLOW}{C_BOLD}{len(place_links)}{C_RESET} tempat.")

        print(f"\n{C_CYAN}⭐ Memulai ekstraksi ringkasan data awal...{C_RESET}")
        places = extract_places_data(results_panel)
        print(f"{C_GREEN}[✔ SELESAI]{C_RESET} Berhasil mengekstrak ringkasan dari {C_YELLOW}{C_BOLD}{len(places)}{C_RESET} tempat.")
        
        enrich_places_with_detail_data(page, results_panel, places)
        print_places_data(places)
        export_places_data(places)

        print(f"{C_MAGENTA}✨ Proses Scraping Selesai dengan Sempurna! ✨{C_RESET}")
        input(f"\n{C_BOLD}{C_YELLOW}[💻 INPUT] Tekan Enter untuk menutup browser...{C_RESET}")
        browser.close()


if __name__ == "__main__":
    main()
