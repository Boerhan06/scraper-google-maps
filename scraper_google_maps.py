import os
import re
import pandas as pd
import requests
import streamlit as st
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# --- KONFIGURASI DAN DIRECTORY ---
OUTPUT_DIR = Path("output")
CSV_OUTPUT_FILE = OUTPUT_DIR / "google_maps_places.csv"
JSON_OUTPUT_FILE = OUTPUT_DIR / "google_maps_places.json"

PLACE_LINK_SELECTOR = 'a[href*="/maps/place/"]'
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
WEBSITE_SELECTORS = [
    'a[data-item-id="authority"]',
    'a[aria-label^="Website:"]',
    'a[aria-label^="Situs Web:"]',
    'a[aria-label^="Situs web:"]',
]
MENU_SELECTORS = [
    'a[aria-label*="Menu"]',
    'button[aria-label*="Menu"]',
    'a[href*="menu"]',
    'a[data-item-id*="menu"]',
    'button[data-item-id*="menu"]',
]
SCROLL_PAUSE_MS = 1500

EXPORT_COLUMNS = [
    "nama_tempat",
    "rating",
    "jumlah_ulasan",
    "kategori",
    "alamat_lengkap",
    "nomor_telepon",
    "jam_operasional",
    "website",
    "instagram",
    "tiktok",
    "whatsapp",
    "menu",
    "review_teratas",
    "tautan_google_maps",
]


def get_top_reviews(page) -> str:
    try:
        reviews_locator = page.locator("span.wiI7ee")
        texts = []
        for i in range(min(reviews_locator.count(), 3)):
            t = reviews_locator.nth(i).inner_text(timeout=1000).strip()
            if t:
                texts.append(f'"{t}"')
        return " | ".join(texts)
    except Exception:
        return ""


# --- STATUS / LOGGER UNTUK STREAMLIT ---
class UIStatus:
    def __init__(self, log_placeholder, leads_placeholder, wa_placeholder):
        self.log_placeholder = log_placeholder
        self.leads_placeholder = leads_placeholder
        self.wa_placeholder = wa_placeholder
        self.logs = []
        self.total_leads = 0
        self.total_wa = 0
        
    def update_leads(self, count):
        self.total_leads = count
        self.leads_placeholder.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-top-row">
                <div class="kpi-icon-badge">📁</div>
                <span class="kpi-badge-green">Live Scraped</span>
            </div>
            <div class="kpi-label-text">Total Tempat Ditemukan</div>
            <div class="kpi-value-text">{self.total_leads}</div>
        </div>
        """, unsafe_allow_html=True)
        
    def update_wa(self, count):
        self.total_wa = count
        self.wa_placeholder.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-top-row">
                <div class="kpi-icon-badge">📞</div>
                <span class="kpi-badge-green">Live Active</span>
            </div>
            <div class="kpi-label-text">Nomor WA Didapat</div>
            <div class="kpi-value-text">{self.total_wa}</div>
        </div>
        """, unsafe_allow_html=True)
        
    def info(self, msg: str):
        self.logs.append(f"ℹ️ {msg}")
        self.log_placeholder.code("\n".join(self.logs[-15:]))
        
    def success(self, msg: str):
        self.logs.append(f"✅ {msg}")
        self.log_placeholder.code("\n".join(self.logs[-15:]))
        
    def error(self, msg: str):
        self.logs.append(f"❌ {msg}")
        self.log_placeholder.code("\n".join(self.logs[-15:]))


# --- UTILITIES ---
def get_place_links(results_panel) -> set[str]:
    try:
        return set(
            results_panel.locator(PLACE_LINK_SELECTOR).evaluate_all(
                """links => links
                    .map(link => link.href)
                    .filter(Boolean)
                """
            )
        )
    except Exception:
        return set()


def scroll_results_until_end(page, results_panel, max_scroll_attempts, max_idle_scrolls, ui_status) -> set[str]:
    place_links: set[str] = set()
    idle_scrolls = 0

    for attempt in range(1, max_scroll_attempts + 1):
        current_links = get_place_links(results_panel)
        new_links = current_links - place_links

        if new_links:
            place_links.update(new_links)
            idle_scrolls = 0
            ui_status.info(f"[Scroll {attempt:02d}] Menemukan {len(new_links)} tempat baru (Total: {len(place_links)})")
        else:
            idle_scrolls += 1
            ui_status.info(f"[Scroll {attempt:02d}] Tidak ada data baru (Idle: {idle_scrolls}/{max_idle_scrolls})")

        if idle_scrolls >= max_idle_scrolls:
            ui_status.success("Batas akhir daftar pencarian Google Maps tercapai.")
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
        ui_status.info(f"Scroll dihentikan karena mencapai batas maksimal ({max_scroll_attempts}).")

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


def parse_rating_and_reviews(page) -> tuple[str, str]:
    rating = ""
    reviews = ""
    try:
        span = page.locator('div.F7nice span[aria-label*="bintang"], div.F7nice span[aria-label*="star"]').first
        if span.count() > 0:
            aria_label = span.get_attribute("aria-label") or ""
            rating_match = re.search(r"^([\d,.]+)", aria_label)
            if rating_match:
                rating = rating_match.group(1).replace(",", ".")
            reviews_match = re.search(r"([0-9., ]+) *(?:Ulasan|ulasan|Reviews|reviews|Review|review)", aria_label)
            if reviews_match:
                reviews = reviews_match.group(1).strip().replace(".", "").replace(",", "")
                
        if not rating or not reviews:
            f7nice = page.locator("div.F7nice").first
            if f7nice.count() > 0:
                text = f7nice.inner_text().strip()
                text = text.replace("\n", "").replace(" ", "")
                match = re.search(r"([\d,.]+)\(([\d.,]+)\)", text)
                if match:
                    if not rating:
                        rating = match.group(1).replace(",", ".")
                    if not reviews:
                        reviews = match.group(2).replace(".", "").replace(",", "")
                elif not rating:
                    rating = text.replace(",", ".")
    except Exception:
        pass
        
    return rating, reviews


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


def get_website_url(page) -> str:
    for selector in WEBSITE_SELECTORS:
        locator = page.locator(selector)
        if locator.count() > 0:
            href = locator.first.get_attribute("href")
            if href:
                return href.strip()
    return ""


def extract_socials_from_website(url: str, extract_whatsapp=True, extract_socials=True) -> dict[str, str]:
    socials = {"instagram": "", "tiktok": "", "whatsapp": ""}
    if not url:
        return socials
        
    url_lower = url.lower()
    if extract_socials and "instagram.com" in url_lower:
        socials["instagram"] = url
        return socials
    if extract_socials and "tiktok.com" in url_lower:
        socials["tiktok"] = url
        return socials
    if extract_whatsapp and ("wa.me" in url_lower or "api.whatsapp.com" in url_lower):
        socials["whatsapp"] = url
        return socials

    if not extract_whatsapp and not extract_socials:
        return socials

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=3, allow_redirects=True)
        if response.status_code == 200:
            html = response.text
            
            if extract_socials:
                insta_match = re.search(r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.-]+', html, re.IGNORECASE)
                if insta_match:
                    socials["instagram"] = insta_match.group(0)
                    
                tiktok_match = re.search(r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.-]+', html, re.IGNORECASE)
                if tiktok_match:
                    socials["tiktok"] = tiktok_match.group(0)
                
            if extract_whatsapp:
                wa_match = re.search(r'https?://(?:wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com)/[a-zA-Z0-9_.+-]+', html, re.IGNORECASE)
                if wa_match:
                    socials["whatsapp"] = wa_match.group(0)
                else:
                    wa_href_match = re.search(r'href=["\'](?:tel:|https://wa\.me/)?(\+?62[\d-]{8,15})["\']', html)
                    if wa_href_match:
                        num = wa_href_match.group(1).replace("-", "").replace(" ", "")
                        socials["whatsapp"] = f"https://wa.me/{num}"
    except Exception:
        pass
        
    return socials


# --- CORE SCRAPER RUNNER (HEADLESS) ---
def run_scraping_process(
    keywords,
    max_scroll_attempts,
    max_idle_scrolls,
    ui_status,
    headless=True,
    request_delay=2,
    max_leads=50,
    extract_whatsapp=True,
    extract_socials=True,
    extract_reviews=False
) -> list[dict]:
    global_places = []
    wa_count = 0
    
    ui_status.info(f"Memulai browser chromium Playwright (Headless={headless})...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            # Tab utama
            page = browser.new_page()
            
            # Tab detail dengan resource blocking
            ui_status.info("Mempersiapkan tab detail dengan Resource Blocking (Gambar/Media)...")
            detail_page = browser.new_page()
            def block_resources(route):
                if route.request.resource_type in ["image", "media", "font"]:
                    route.abort()
                else:
                    route.continue_()
            detail_page.route("**/*", block_resources)

            for kw_idx, keyword in enumerate(keywords, start=1):
                ui_status.info(f"[{kw_idx}/{len(keywords)}] Mencari kata kunci: '{keyword}'...")
                page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
                page.wait_for_timeout(request_delay * 1000)

                search_box = page.locator("input#searchboxinput, input.UGojuc, input[role='combobox']").first
                try:
                    search_box.wait_for(state="visible", timeout=15000)
                except PlaywrightTimeoutError:
                    search_box = page.locator("input").first
                    search_box.wait_for(state="visible", timeout=15000)

                search_box.fill(keyword)
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")

                results_panel = page.locator('div[role="feed"]')

                try:
                    results_panel.wait_for(state="visible", timeout=25000)
                    results_panel.locator(PLACE_LINK_SELECTOR).first.wait_for(
                        state="visible",
                        timeout=25000,
                    )
                    ui_status.success(f"Panel hasil untuk '{keyword}' berhasil termuat.")
                except PlaywrightTimeoutError:
                    ui_status.error(f"Panel hasil '{keyword}' tidak muncul. Melewati...")
                    continue

                ui_status.info("Melakukan scrolling halaman hasil pencarian secara dinamis...")
                place_links_set = scroll_results_until_end(page, results_panel, max_scroll_attempts, max_idle_scrolls, ui_status)
                place_links = list(place_links_set)
                
                # Limit leads
                if max_leads > 0:
                    place_links = place_links[:max_leads]
                    
                ui_status.success(f"Ditemukan {len(place_links)} tempat unik untuk '{keyword}'.")

                ui_status.info(f"Memulai pengambilan detail tempat ({len(place_links)} total)...")
                for index, link in enumerate(place_links, start=1):
                    url_part = link.split('/place/')[1].split('/')[0].replace('+', ' ') if '/place/' in link else 'Tempat'
                    ui_status.info(f"[{index}/{len(place_links)}] Mengunjungi: {url_part}")
                    page.wait_for_timeout(request_delay * 1000)
                    try:
                        detail_page.goto(link, wait_until="domcontentloaded")
                        
                        h1_locator = detail_page.locator("h1")
                        h1_locator.wait_for(state="visible", timeout=15000)
                        
                        name = h1_locator.inner_text().strip()
                        rating, reviews = parse_rating_and_reviews(detail_page)
                        
                        category = ""
                        cat_btn = detail_page.locator("button[jsaction*='.category']").first
                        if cat_btn.count() > 0:
                            category = cat_btn.inner_text().strip()
                        
                        alamat = get_detail_value(detail_page, ADDRESS_SELECTORS)
                        jam = get_detail_value(detail_page, HOURS_SELECTORS)
                        telepon = get_detail_value(detail_page, PHONE_SELECTORS)
                        menu = get_menu_info(detail_page)
                        
                        # Ekstrak website & sosmed
                        website = get_website_url(detail_page)
                        instagram = ""
                        tiktok = ""
                        whatsapp = ""
                        
                        if website and (extract_socials or extract_whatsapp):
                            ui_status.info(f"  🌐 Scanning sosmed website: {website}")
                            socials = extract_socials_from_website(website, extract_whatsapp, extract_socials)
                            instagram = socials["instagram"]
                            tiktok = socials["tiktok"]
                            whatsapp = socials["whatsapp"]
                        
                        # Ekstrak review teratas
                        review_teratas = ""
                        if extract_reviews:
                            review_teratas = get_top_reviews(detail_page)
                            
                        place = {
                            "nama_tempat": name,
                            "rating": rating,
                            "jumlah_ulasan": reviews,
                            "kategori": category,
                            "alamat_lengkap": alamat,
                            "nomor_telepon": telepon,
                            "jam_operasional": jam,
                            "website": website,
                            "instagram": instagram,
                            "tiktok": tiktok,
                            "whatsapp": whatsapp,
                            "menu": menu,
                            "review_teratas": review_teratas,
                            "tautan_google_maps": link,
                        }
                        
                        if name:
                            global_places.append(place)
                            ui_status.update_leads(len(global_places))
                            if whatsapp:
                                wa_count += 1
                                ui_status.update_wa(wa_count)
                            ui_status.success(f"  ✓ {name} (⭐ {rating or '-'} / {reviews or '0'} ulasan)")
                        
                    except Exception as e:
                        ui_status.error(f"  × Gagal mengekstrak {url_part}: {e}")
            
            browser.close()
        except Exception as e:
            ui_status.error(f"Terjadi kegagalan sistem: {e}")
            try:
                browser.close()
            except Exception:
                pass
                
    return global_places


# ──────────────────────────────────────────────────────────────
# STREAMLIT UI
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Maps Scraper — Data Extraction Platform",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
/* ── Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hide default Streamlit developer chrome, keep sidebar toggle ── */
[data-testid="stDeployButton"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: transparent !important;
}

/* ── Background Main Page ── */
.stApp {
    background-color: #F8F9FA !important;
}

/* ── Streamlit Container Card Override ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    padding: 24px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
}

/* ── Sidebar overrides ── */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}

/* Brand styling in sidebar */
.brand-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 32px;
    padding: 0 8px;
}
.brand-logo {
    background-color: #CC0000;
    color: #FFFFFF;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
}
.brand-name {
    font-weight: 700;
    color: #0F172A;
    font-size: 1.1rem;
    line-height: 1.15;
}
.brand-sub {
    font-size: 0.65rem;
    color: #94A3B8;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Sidebar navigation */
.sidebar-nav {
    margin-bottom: 32px;
    padding: 0 8px;
}
.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    border-radius: 8px;
    color: #64748B;
    font-size: 0.85rem;
    font-weight: 500;
    margin-bottom: 4px;
    transition: all 0.2s ease;
}
.nav-item:hover {
    background-color: #F8F9FA;
    color: #0F172A;
}
.nav-item.active {
    background-color: #FEF2F2;
    color: #CC0000;
    font-weight: 600;
    border-left: 3px solid #CC0000;
    border-radius: 0 8px 8px 0;
    margin-left: -24px;
    padding-left: 21px;
}

/* Pro Broadcast Sidebar Box */
.promo-box {
    background-color: #F8F9FA;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px;
    margin-top: 40px;
}
.promo-title {
    font-size: 0.7rem;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.promo-text {
    font-size: 0.8rem;
    color: #64748B;
    margin-bottom: 16px;
    line-height: 1.4;
}
.promo-btn {
    background-color: #CC0000;
    color: white !important;
    text-align: center;
    display: block;
    padding: 10px;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 600;
    text-decoration: none !important;
    transition: background-color 0.2s;
}
.promo-btn:hover {
    background-color: #B30000;
}

/* Top bar mock */
.topbar-mock {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 12px 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.search-mock {
    display: flex;
    align-items: center;
    gap: 8px;
    background-color: #F8F9FA;
    border: 1px solid #E5E7EB;
    border-radius: 9999px;
    padding: 8px 16px;
    width: 320px;
    color: #94A3B8;
    font-size: 0.85rem;
}
.user-profile-mock {
    display: flex;
    align-items: center;
    gap: 12px;
}
.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: #CC0000;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.85rem;
}

/* Main title section */
.main-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    padding: 0 4px;
}
.main-title-text {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin: 0 !important;
    letter-spacing: -0.5px;
}
.main-sub-text {
    font-size: 0.85rem;
    color: #64748B;
    margin: 4px 0 0 0;
}

/* KPI cards styling */
.kpi-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    transition: transform 0.2s, box-shadow 0.2s;
    height: 100%;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
.kpi-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.kpi-icon-badge {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background-color: #FEF2F2;
    color: #CC0000;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
}
.kpi-badge-green {
    background-color: #ECFDF5;
    color: #059669;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
}
.kpi-badge-red {
    background-color: #FEF2F2;
    color: #DC2626;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
}
.kpi-label-text {
    font-size: 0.7rem;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.kpi-value-text {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0F172A;
    margin: 4px 0 0 0;
}

/* Streamlit Input Override */
.stTextInput input {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    color: #0F172A !important;
    height: 46px !important;
    padding: 0 16px !important;
    font-size: 14px !important;
    transition: all 0.2s ease !important;
}
.stTextInput input:focus {
    border-color: #CC0000 !important;
    box-shadow: 0 0 0 3px rgba(204,0,0,0.08) !important;
}

/* Primary pill button (Export style) */
.stButton > button {
    background-color: #0F172A !important;
    color: #FFFFFF !important;
    border: none !important;
    height: 44px !important;
    border-radius: 9999px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.5px !important;
    padding: 0 32px !important;
    box-shadow: 0 4px 10px rgba(15, 23, 42, 0.15) !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background-color: #1E293B !important;
    box-shadow: 0 6px 12px rgba(15, 23, 42, 0.25) !important;
    transform: translateY(-1px);
}
.stButton > button:active {
    transform: translateY(0);
}

/* Download/Action pill button */
.stDownloadButton > button {
    background-color: #CC0000 !important;
    color: #FFFFFF !important;
    border: none !important;
    height: 40px !important;
    border-radius: 9999px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px !important;
    padding: 0 24px !important;
    box-shadow: 0 2px 4px rgba(204, 0, 0, 0.1) !important;
    transition: all 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background-color: #B30000 !important;
    box-shadow: 0 4px 8px rgba(204, 0, 0, 0.2) !important;
    transform: translateY(-1px);
}

.sidebar-title {
    font-size: 0.7rem;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    display: block;
}
.sidebar-note {
    font-size: 0.82rem;
    color: #64748B;
    line-height: 1.65;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="brand-container">
        <div class="brand-logo">⚡</div>
        <div>
            <div class="brand-name">GeoScraper Pro</div>
            <div class="brand-sub">Advanced Google Maps Scraper</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<span class='sidebar-title'>Advanced Settings</span>", unsafe_allow_html=True)

    # 1. Mode Operasi (Headless Toggle)
    show_browser = st.checkbox("Tampilkan Browser", value=False, help="Aktifkan untuk melihat langsung bot bekerja. Matikan (Headless) untuk kecepatan maksimal.")

    st.sidebar.divider()
    
    # 2. Proteksi Anti-Ban (Jeda Waktu)
    request_delay = st.slider("Request Delay (Seconds)", 1, 5, 2, step=1, help="Jeda waktu per kunjungan tempat untuk menghindari deteksi Google.")

    st.sidebar.divider()
    
    # 3. Limitasi Data
    max_leads = st.slider("Max Leads per Keyword", 5, 200, 50, step=5, help="Batas maksimal tempat unik yang diekstrak per kata kunci.")

    # Scroll depth limit in background
    max_scroll = st.sidebar.slider("Depth Limit (Scrolls)", 5, 150, 50, step=5)
    idle_limit = st.sidebar.slider("Idle Timeout", 1, 10, 3, step=1)

    st.sidebar.divider()
    
    # 4. Opsi Ekstraksi Lanjutan
    st.markdown("<span class='sidebar-title'>Opsi Ekstraksi Lanjutan</span>", unsafe_allow_html=True)
    extract_whatsapp = st.checkbox("Ekstrak Nomor WhatsApp", value=True)
    extract_socials = st.checkbox("Ambil Tautan Instagram/TikTok", value=True)
    extract_reviews = st.checkbox("Ambil Data Review Teratas", value=False, help="Dapat memperlambat proses pencarian karena bot harus memindai ulasan tempat.")

    st.sidebar.divider()
    
    st.markdown("""
    <div class="promo-box">
        <div class="promo-title">PRO SCRAPER</div>
        <div class="promo-text">Upgrade to unlock rotating proxies & high-speed parallel scrapers.</div>
        <a href="#" class="promo-btn">Upgrade Now</a>
    </div>
    """, unsafe_allow_html=True)


# ── MAIN CONTENT ─────────────────────────────────────────────
# 1. Top bar mock
st.markdown("""
<div class="topbar-mock">
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 1.3rem;">🌍</span>
        <span style="font-weight: 700; color: #0F172A; font-size: 1.15rem; letter-spacing: -0.3px;">GeoScraper Pro</span>
    </div>
    <div style="display: flex; align-items: center; gap: 20px;">
        <span style="font-size: 0.8rem; font-weight: 600; color: #059669; background-color: #ECFDF5; padding: 6px 12px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 6px;">
            <span style="width: 8px; height: 8px; background-color: #10B981; border-radius: 50%; display: inline-block;"></span> System Online / Proxy Active
        </span>
        <a href="https://github.com/Boerhan06/scraper-google-maps#readme" target="_blank" style="font-size: 0.85rem; color: #64748B; text-decoration: none; font-weight: 500; display: flex; align-items: center; gap: 4px;">
            <span>❓</span> Docs & Help
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Hero Section (Prolog)
st.markdown("""
<div class="main-header-row">
    <div>
        <h1 class="main-title-text">Ekstraksi Data Bisnis Google Maps Secara Massal</h1>
        <p class="main-sub-text">Cari ribuan prospek bisnis lengkap dengan telepon, email, whatsapp, instagram, dan tiktok secara otomatis.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# 3. Four KPI metric cards in a row
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    leads_placeholder = st.empty()
    leads_placeholder.markdown("""
    <div class="kpi-card">
        <div class="kpi-top-row">
            <div class="kpi-icon-badge">📁</div>
            <span class="kpi-badge-green">Ready</span>
        </div>
        <div class="kpi-label-text">Total Tempat Ditemukan</div>
        <div class="kpi-value-text">0</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi2:
    wa_placeholder = st.empty()
    wa_placeholder.markdown("""
    <div class="kpi-card">
        <div class="kpi-top-row">
            <div class="kpi-icon-badge">📞</div>
            <span class="kpi-badge-green">Ready</span>
        </div>
        <div class="kpi-label-text">Nomor WA Didapat</div>
        <div class="kpi-value-text">0</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi3:
    st.markdown("""
    <div class="kpi-card">
        <div class="kpi-top-row">
            <div class="kpi-icon-badge">⚡</div>
            <span class="kpi-badge-green">-0.8s</span>
        </div>
        <div class="kpi-label-text">AVERAGE EXTRACTION RATE</div>
        <div class="kpi-value-text">2.4s / site</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi4:
    st.markdown("""
    <div class="kpi-card">
        <div class="kpi-top-row">
            <div class="kpi-icon-badge">🎯</div>
            <span class="kpi-badge-green">+0.5%</span>
        </div>
        <div class="kpi-label-text">ENGINE SUCCESS ACCURACY</div>
        <div class="kpi-value-text">99.2%</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── TARGET CONFIG SECTION ───────────────────────────────────────────
with st.container(border=True):
    st.markdown("<div style='font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 4px;'>Konfigurasi Target Pencarian</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 0.8rem; color: #64748B; margin-bottom: 16px;'>Masukkan satu atau banyak kata kunci pencarian (satu per baris) untuk memulai proses ekstraksi massal.</div>", unsafe_allow_html=True)

    search_query = st.text_area(
        "Keywords (Satu per baris)",
        value="Cafe di Purwakarta Kota\nCafe di Babakancikao",
        placeholder="e.g.\nCafe di Bandung\nHotel di Jakarta\nApotek di Bogor",
        label_visibility="collapsed",
        height=120
    )

    col_btn, col_space = st.columns([1, 3])
    with col_btn:
        start_btn = st.button("Mulai Ekstraksi")

st.markdown("<br>", unsafe_allow_html=True)

# ── EXECUTION ────────────────────────────────────────────────
log_container = st.container()

if start_btn:
    if search_query.strip():
        # Parse keywords separated by newlines
        keywords = [k.strip() for k in search_query.split("\n") if k.strip()]

        with log_container:
            with st.container(border=True):
                st.markdown("<span class='sidebar-title'>Live Console Log</span>", unsafe_allow_html=True)
                log_placeholder = st.empty()

        ui_status = UIStatus(log_placeholder, leads_placeholder, wa_placeholder)

        with st.spinner("Ekstraksi data sedang berjalan — silakan pantau progress..."):
            results = run_scraping_process(
                keywords,
                max_scroll,
                idle_limit,
                ui_status,
                headless=not show_browser,
                request_delay=request_delay,
                max_leads=max_leads,
                extract_whatsapp=extract_whatsapp,
                extract_socials=extract_socials,
                extract_reviews=extract_reviews
            )

        if results:
            df = pd.DataFrame(results)
            df = df[df["nama_tempat"] != ""]

            total_before = len(df)
            df.drop_duplicates(subset=["nama_tempat"], keep="first", inplace=True)
            df.drop_duplicates(subset=["tautan_google_maps"], keep="first", inplace=True)
            total_after = len(df)

            st.success(
                f"Ekstraksi Selesai — {total_after} records unik berhasil dikumpulkan, "
                f"{total_before - total_after} duplikat dibuang."
            )

            st.markdown("<br>", unsafe_allow_html=True)
            
            with st.container(border=True):
                st.markdown("<div style='font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 12px;'>Data Preview & Export</div>", unsafe_allow_html=True)
                st.dataframe(df, use_container_width=True)

                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                
                # Export files
                df.to_csv(CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
                df.to_json(JSON_OUTPUT_FILE, orient="records", indent=4, force_ascii=False)
                
                try:
                    import io
                    # Export excel
                    excel_buffer = io.BytesIO()
                    df.to_excel(excel_buffer, index=False, header=True)
                    excel_buffer.seek(0)
                    excel_data = excel_buffer.getvalue()
                except Exception:
                    excel_data = None

                st.markdown("<div style='font-size: 0.8rem; color: #64748B; margin-bottom: 12px;'>Ekspor data ke format pilihan Anda:</div>", unsafe_allow_html=True)
                col_csv, col_xlsx, col_json = st.columns(3)
                
                with col_csv:
                    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    st.download_button(
                        label="Download CSV Data",
                        data=csv_bytes,
                        file_name="google_maps_places.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                with col_xlsx:
                    if excel_data:
                        st.download_button(
                            label="Download Excel Data",
                            data=excel_data,
                            file_name="google_maps_places.xlsx",
                            mime="application/vnd.ms-excel",
                            use_container_width=True
                        )
                    else:
                        st.button("Excel Export Disabled (Install openpyxl)", disabled=True, use_container_width=True)
                        
                with col_json:
                    json_str = df.to_json(orient="records", indent=4, force_ascii=False)
                    st.download_button(
                        label="Download JSON Data",
                        data=json_str,
                        file_name="google_maps_places.json",
                        mime="application/json",
                        use_container_width=True
                    )
        else:
            st.error("Ekstraksi tidak mengembalikan hasil. Silakan periksa kembali kata kunci pencarian Anda.")
    else:
        st.warning("Harap masukkan setidaknya satu kata kunci untuk memulai.")


