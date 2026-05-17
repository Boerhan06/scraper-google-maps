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
    def __init__(self, log_placeholder, leads_placeholder):
        self.log_placeholder = log_placeholder
        self.leads_placeholder = leads_placeholder
        self.logs = []
        self.total_leads = 0
        self.total_wa = 0
        
    def update_leads(self, count):
        self.total_leads = count
        self.leads_placeholder.markdown(f"""
        <div class="extracted-leads-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px;">
                <div style="font-size: 0.8rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px;">Extracted Leads</div>
                <div style="background-color: #1E1F38; color: #818CF8; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">💼</div>
            </div>
            <div style="font-size: 3.5rem; font-weight: 800; color: #FFFFFF; line-height: 1; margin-bottom: 8px;">{self.total_leads}</div>
            <div style="font-size: 0.8rem; font-weight: 600; color: #6366F1;">Total businesses found</div>
        </div>
        """, unsafe_allow_html=True)
        
    def update_wa(self, count):
        self.total_wa = count
        self.info(f"WhatsApp numbers parsed: {count}")
        
    def info(self, msg: str):
        self.logs.append(f"[INFO] {msg}")
        self.log_placeholder.code("\n".join(self.logs[-12:]))
        
    def success(self, msg: str):
        self.logs.append(f"[SUCCESS] {msg}")
        self.log_placeholder.code("\n".join(self.logs[-12:]))
        
    def error(self, msg: str):
        self.logs.append(f"[ERROR] {msg}")
        self.log_placeholder.code("\n".join(self.logs[-12:]))


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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
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
    background-color: #05050A !important;
}

/* ── Pull page content up by reducing top gap ── */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 95% !important;
}

/* ── Streamlit Container Card Override ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #0B0C16 !important;
    border: 1px solid #1A1C30 !important;
    border-radius: 20px !important;
    padding: 32px !important;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5) !important;
    transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.4s ease, box-shadow 0.4s ease !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #6366F1 !important;
    transform: translateY(-4px) scale(1.005);
    box-shadow: 0 20px 40px rgba(99, 102, 241, 0.25), 0 0 30px rgba(99, 102, 241, 0.1) !important;
}

/* ── Sidebar overrides ── */
[data-testid="stSidebar"] {
    background-color: #080812 !important;
    border-right: 1px solid #161726 !important;
}
[data-testid="stSidebar"] label {
    color: #E2E8F0 !important;
    font-weight: 500;
}
.sidebar-title {
    font-size: 0.7rem;
    font-weight: 600;
    color: #818CF8 !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    display: block;
}
.sidebar-note {
    font-size: 0.82rem;
    color: #94A3B8;
    line-height: 1.65;
}

/* ── Custom CSS Animations & Micro-Interactions ── */
@keyframes pulse {
    0% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(99,102,241,0.3)); }
    50% { transform: scale(1.1); filter: drop-shadow(0 0 16px rgba(99,102,241,0.8)); }
    100% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(99,102,241,0.3)); }
}
.pulse-logo {
    animation: pulse 3s infinite ease-in-out;
}

@keyframes beacon {
    0% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { transform: scale(1.2); opacity: 0.3; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
    100% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background-color: #10B981;
    border-radius: 50%;
    animation: beacon 2s infinite;
}

/* ── Interactive Hover Lighting ── */
.nav-link-hover {
    transition: all 0.3s ease !important;
}
.nav-link-hover:hover {
    color: #818CF8 !important;
    text-shadow: 0 0 12px rgba(99, 102, 241, 0.8) !important;
}

.status-container-hover {
    transition: all 0.3s ease !important;
}
.status-container-hover:hover {
    border-color: #6366F1 !important;
    box-shadow: 0 0 15px rgba(99, 102, 241, 0.5) !important;
}

.pro-btn-hover {
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.pro-btn-hover:hover {
    transform: scale(1.05) !important;
    box-shadow: 0 0 25px rgba(255, 255, 255, 0.6) !important;
}

/* ── Textarea styling override ── */
.stTextArea textarea {
    background-color: #05050A !important;
    border: 1px solid #1A1C30 !important;
    border-radius: 12px !important;
    color: #FFFFFF !important;
    padding: 16px !important;
    font-size: 14px !important;
    transition: all 0.2s ease !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5) !important;
}
.stTextArea textarea:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* ── Launch Engine Button styling override ── */
.stButton > button {
    background-color: #4F46E5 !important;
    color: #FFFFFF !important;
    border: none !important;
    height: 48px !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: 0.5px !important;
    padding: 0 32px !important;
    box-shadow: 0 4px 15px rgba(79, 70, 229, 0.4) !important;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    width: auto !important;
}
.stButton > button:hover {
    background-color: #5850EC !important;
    box-shadow: 0 0 30px rgba(79, 70, 229, 0.95), 0 0 10px rgba(99, 102, 241, 0.5) !important;
    transform: translateY(-2px) scale(1.02);
}
.stButton > button:active {
    transform: translateY(0);
}

/* ── Download/Action pill button ── */
.stDownloadButton > button {
    background-color: #6366F1 !important;
    color: #FFFFFF !important;
    border: none !important;
    height: 44px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px !important;
    padding: 0 24px !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2) !important;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    width: 100% !important;
}
.stDownloadButton > button:hover {
    background-color: #4F46E5 !important;
    box-shadow: 0 0 25px rgba(99, 102, 241, 0.8) !important;
    transform: translateY(-2px) scale(1.02);
}

/* ── Extracted Leads Card ── */
.extracted-leads-card {
    background-color: transparent;
}

/* ── Code / Terminal Override ── */
code, pre {
    background-color: #05050A !important;
    border: 1px solid #1A1C30 !important;
    border-radius: 12px !important;
    color: #10B981 !important;
    font-family: 'Courier New', Courier, monospace !important;
    font-size: 0.8rem !important;
    padding: 16px !important;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div class="brand-container" style="display: flex; align-items: center; gap: 12px; margin-bottom: 32px; padding: 0 8px;">
<div class="pulse-logo" style="font-size: 1.5rem; color: #6366F1;">⚡</div>
<div>
<div class="brand-name" style="color: #FFFFFF; font-weight: 700; font-size: 1.1rem; line-height: 1.15;">GeoScraper</div>
<div class="brand-sub" style="color: #818CF8; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Advanced Scraper</div>
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
<div class="promo-box" style="background-color: #0B0C16; border: 1px solid #1A1C30; border-radius: 12px; padding: 20px; margin-top: 40px;">
<div class="promo-title" style="color: #818CF8; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">PRO SCRAPER</div>
<div class="promo-text" style="color: #94A3B8; font-size: 0.8rem; margin-bottom: 16px; line-height: 1.4;">Upgrade to unlock rotating proxies & high-speed parallel scrapers.</div>
<a href="#" class="promo-btn" style="background-color: #4F46E5; color: white !important; text-align: center; display: block; padding: 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; text-decoration: none !important;">Upgrade Now</a>
</div>
""", unsafe_allow_html=True)


# ── TOP BAR (NAV) ───────────────────────────────────────────
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 8px; margin-bottom: 12px;">
<!-- Logo & Brand -->
<div style="display: flex; align-items: center; gap: 8px;">
<span class="pulse-logo" style="font-size: 1.5rem; display: inline-block;">🗺️</span>
<span style="font-weight: 800; color: #FFFFFF; font-size: 1.3rem; letter-spacing: -0.5px;">GeoScraper</span>
</div>

<!-- Nav Links (Dashboard Only) -->
<div style="display: flex; gap: 24px; align-items: center;">
<div class="nav-link-hover" style="font-size: 0.9rem; font-weight: 600; color: #FFFFFF; position: relative; padding-bottom: 6px; cursor: pointer;">
Dashboard
<div style="position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #6366F1, #818CF8); box-shadow: 0 0 8px #6366F1;"></div>
</div>
</div>

<!-- Right elements -->
<div style="display: flex; align-items: center; gap: 16px;">
<div class="status-container-hover" style="background-color: #0B0C16; border: 1px solid #1A1C30; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s;">
<span class="status-dot"></span>
</div>
<a href="#" class="pro-btn-hover" style="background-color: #FFFFFF; color: #05050A; font-size: 0.85rem; font-weight: 700; padding: 10px 24px; border-radius: 9999px; text-decoration: none; box-shadow: 0 4px 12px rgba(255,255,255,0.1); transition: all 0.3s; display: inline-block;">
Pro Access
</a>
</div>
</div>
""", unsafe_allow_html=True)


# ── MAIN ROW (COLUMNS) ───────────────────────────────────────
col_left, col_right = st.columns([2.1, 1.3])

with col_left:
    with st.container(border=True):
        st.markdown("""
<div style="margin-bottom: 20px;">
<span style="font-size: 0.65rem; font-weight: 700; color: #818CF8; background-color: #1E1F38; padding: 6px 12px; border-radius: 9999px; letter-spacing: 0.8px; text-transform: uppercase;">EXTRACTION ENGINE</span>
</div>
<h1 style="font-size: 3.2rem; font-weight: 800; color: #FFFFFF; line-height: 1.05; margin: 0 0 16px 0; letter-spacing: -1.5px;">Mass Data Extraction<br>Supercharged.</h1>
<p style="font-size: 0.95rem; color: #94A3B8; line-height: 1.5; margin-bottom: 32px; max-width: 90%;">Automate your lead generation. Extract business names, addresses, and phone numbers directly from Google Maps into CSV format at high speeds.</p>
""", unsafe_allow_html=True)

        search_query = st.text_area(
            "Keywords",
            value="Cafe di Purwakarta Kota\nCafe di Babakancikao",
            placeholder="Masukkan satu kata kunci per baris...",
            label_visibility="collapsed",
            height=130
        )

        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        start_btn = st.button("▷ Launch Engine")


with col_right:
    # 1. Extracted Leads Card
    with st.container(border=True):
        leads_placeholder = st.empty()
        leads_placeholder.markdown("""
<div class="extracted-leads-card">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px;">
<div style="font-size: 0.8rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px;">Extracted Leads</div>
<div style="background-color: #1E1F38; color: #818CF8; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">💼</div>
</div>
<div style="font-size: 3.5rem; font-weight: 800; color: #FFFFFF; line-height: 1; margin-bottom: 8px;">0</div>
<div style="font-size: 0.8rem; font-weight: 600; color: #6366F1;">Total businesses found</div>
</div>
""", unsafe_allow_html=True)

    # 2. Live Terminal Card
    with st.container(border=True):
        st.markdown("""
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 16px;">
<span style="width: 8px; height: 8px; background-color: #EF4444; border-radius: 50%; display: inline-block;"></span>
<span style="width: 8px; height: 8px; background-color: #F59E0B; border-radius: 50%; display: inline-block;"></span>
<span style="width: 8px; height: 8px; background-color: #10B981; border-radius: 50%; display: inline-block;"></span>
<span style="font-size: 0.65rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px; margin-left: 8px;">Live Terminal</span>
</div>
""", unsafe_allow_html=True)
        
        lottie_placeholder = st.empty()
        log_placeholder = st.empty()
        log_placeholder.code("Waiting for engine launch...")


# ── EXECUTION & RESULTS ──────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
results_container = st.container()

if start_btn:
    if search_query.strip():
        keywords = [k.strip() for k in search_query.split("\n") if k.strip()]

        ui_status = UIStatus(log_placeholder, leads_placeholder)

        # Injeksi Lottie Loader animasi radar jika tersedia
        lottie_json = None
        try:
            import requests
            res = requests.get("https://lottie.host/8dd0a9c8-dfb8-4dfb-8a8b-fdfc2b1869cc/F6MvXoX5pP.json", timeout=3)
            if res.status_code == 200:
                lottie_json = res.json()
        except Exception:
            pass

        try:
            if lottie_json:
                from streamlit_lottie import st_lottie
                with lottie_placeholder:
                    st_lottie(lottie_json, height=130, key="scraping_radar")
        except Exception:
            pass

        with st.spinner("Executing Playwright crawler..."):
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

        # Clear Lottie Loader setelah selesai
        lottie_placeholder.empty()

        if results:
            df = pd.DataFrame(results)
            df = df[df["nama_tempat"] != ""]

            total_before = len(df)
            df.drop_duplicates(subset=["nama_tempat"], keep="first", inplace=True)
            df.drop_duplicates(subset=["tautan_google_maps"], keep="first", inplace=True)
            total_after = len(df)

            with results_container:
                st.success(f"Successfully extracted {total_after} unique business records!")
                
                with st.container(border=True):
                    st.markdown("<div style='font-size: 1.05rem; font-weight: 700; color: #FFFFFF; margin-bottom: 12px;'>Data Preview & Export</div>", unsafe_allow_html=True)
                    st.dataframe(df, use_container_width=True)

                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    
                    df.to_csv(CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
                    df.to_json(JSON_OUTPUT_FILE, orient="records", indent=4, force_ascii=False)
                    
                    try:
                        import io
                        excel_buffer = io.BytesIO()
                        df.to_excel(excel_buffer, index=False, header=True)
                        excel_buffer.seek(0)
                        excel_data = excel_buffer.getvalue()
                    except Exception:
                        excel_data = None

                    st.markdown("<div style='font-size: 0.85rem; color: #94A3B8; margin-bottom: 16px;'>Export your gathered data to these enterprise formats:</div>", unsafe_allow_html=True)
                    col_csv, col_xlsx, col_json = st.columns(3)
                    
                    with col_csv:
                        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button(
                            label="Download CSV",
                            data=csv_bytes,
                            file_name="google_maps_places.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                        
                    with col_xlsx:
                        if excel_data:
                            st.download_button(
                                label="Download Excel",
                                data=excel_data,
                                file_name="google_maps_places.xlsx",
                                mime="application/vnd.ms-excel",
                                use_container_width=True
                            )
                        else:
                            st.button("Excel Export Disabled", disabled=True, use_container_width=True)
                            
                    with col_json:
                        json_str = df.to_json(orient="records", indent=4, force_ascii=False)
                        st.download_button(
                            label="Download JSON",
                            data=json_str,
                            file_name="google_maps_places.json",
                            mime="application/json",
                            use_container_width=True
                        )
        else:
            st.error("No results returned. Try adjusting your query or delays.")
    else:
        st.warning("Please enter at least one keyword.")


