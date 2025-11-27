import streamlit as st
import pandas as pd
import io
import time
from playwright.sync_api import sync_playwright, TimeoutError
import urllib.parse


EXCLUDE_DOMAINS = [
    "youtube.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "justdial.com", "quora.com", "reddit.com", "telegram.org"
]


@st.cache_resource
def get_playwright_browser():
    """Initialize Playwright browser (cached for reuse)"""
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        return browser, playwright
    except Exception as e:
        st.error(f"❌ Failed to initialize Playwright: {str(e)}")
        return None, None


def scrape_google_search(keyword, pages=2, progress_placeholder=None):
    """Scrape Google Search results using Playwright"""
    browser, playwright_obj = get_playwright_browser()
    
    if browser is None:
        return []
    
    results = []
    
    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        for page_num in range(pages):
            try:
                start = page_num * 10
                search_url = f'https://www.google.com/search?q="{urllib.parse.quote_plus(keyword)}"&start={start}'
                
                if progress_placeholder:
                    progress_placeholder.info(f"📄 Loading page {page_num+1}/{pages} for '{keyword}'...")
                
                # Navigate with timeout
                page.goto(search_url, wait_until="networkidle", timeout=15000)
                time.sleep(2)  # Additional wait for rendering
                
                # Check for blocking
                page_content = page.content().lower()
                if any(x in page_content for x in ["unusual traffic", "captcha", "detected unusual traffic"]):
                    if progress_placeholder:
                        progress_placeholder.error(f"❌ Google blocked page {page_num+1}")
                    break
                
                # Extract search results
                search_results = page.query_selector_all('a')
                found = 0
                
                for result in search_results:
                    try:
                        href = result.get_attribute('href')
                        if not href or not href.startswith("http"):
                            continue
                        
                        if any(x in href for x in ["google.", "webcache.googleusercontent.com"]):
                            continue
                        
                        domain = urllib.parse.urlparse(href).netloc.lower()
                        
                        if any(excluded in domain for excluded in EXCLUDE_DOMAINS):
                            continue
                        
                        # Get link text as title
                        title = result.text_content().strip()[:80]
                        
                        results.append({
                            "Domain": domain,
                            "URL": href,
                            "Title": title if title else domain
                        })
                        found += 1
                    except Exception as e:
                        continue
                
                if found == 0:
                    if progress_placeholder:
                        progress_placeholder.warning(f"⚠️ No results on page {page_num+1}")
                    break
                else:
                    if progress_placeholder:
                        progress_placeholder.info(f"   ✓ Found {found} URLs")
                
            except TimeoutError:
                if progress_placeholder:
                    progress_placeholder.warning(f"⚠️ Timeout on page {page_num+1}")
                break
            except Exception as e:
                if progress_placeholder:
                    progress_placeholder.warning(f"⚠️ Error on page {page_num+1}: {str(e)}")
                break
        
        context.close()
        return results
    
    except Exception as e:
        st.error(f"❌ Scraping error: {str(e)}")
        return []


def main():
    st.set_page_config(
        page_title="Playwright Web Scraper",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Playwright Web Scraper (Google Search)")
    st.markdown("---")
    
    # Instructions
    with st.expander("ℹ️ How to use this app", expanded=False):
        st.markdown("""
        ### Features:
        - ⚡ **Faster than Selenium** (40-50% faster)
        - 🚀 **Modern architecture** (WebSocket-based)
        - 📦 **Simpler setup** (no complex drivers)
        - 🤖 **Auto-wait** (intelligent element waiting)
        - 💚 **Lower memory** (efficient resource usage)
        
        ### Usage:
        1. Upload keywords file (Excel with 'Keywords' column) or enter manually
        2. Configure scraping options
        3. Click 'Start Scraping'
        4. Download results as CSV/Excel
        
        **Note**: Each page has ~10 results. Google may block after 3-5 pages.
        """)
    
    # Sidebar Configuration
    st.sidebar.header("⚙️ Configuration")
    pages = st.sidebar.slider(
        "Number of pages to scrape:",
        min_value=1,
        max_value=10,
        value=2,
        help="Limit to avoid Google blocks"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("📊 **Excluded Domains**: YouTube, Twitter, Instagram, LinkedIn, Quora, Reddit, Telegram")
    st.sidebar.warning("⚠️ **Note**: Google may block after 3-5 pages")
    
    # Main Content - Tabs
    tab1, tab2 = st.tabs(["📁 Upload File", "✏️ Manual Input"])
    
    keywords = []
    
    # TAB 1: Upload File
    with tab1:
        st.subheader("📁 Upload Keywords File")
        uploaded_file = st.file_uploader(
            "Choose an Excel file (.xlsx)",
            type="xlsx",
            label_visibility="collapsed"
        )
        
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                if 'Keywords' not in df.columns:
                    st.error("❌ Error: Excel file must contain a 'Keywords' column")
                else:
                    keywords = df['Keywords'].dropna().astype(str).tolist()
                    st.success(f"✅ Loaded {len(keywords)} keywords")
                    
                    with st.expander("👀 View Keywords"):
                        for i, kw in enumerate(keywords, 1):
                            st.write(f"{i}. {kw}")
            
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
        else:
            st.info("👆 Upload an Excel file (.xlsx) with a 'Keywords' column")
    
    # TAB 2: Manual Input
    with tab2:
        st.subheader("✏️ Enter Keywords Manually")
        keyword_text = st.text_area(
            "Enter keywords (one per line):",
            placeholder="Example:\naml detection\nanti money laundering\nfraud detection",
            height=150
        )
        
        if keyword_text.strip():
            keywords = [kw.strip() for kw in keyword_text.split('\n') if kw.strip()]
            st.success(f"✅ Ready to scrape {len(keywords)} keywords")
            
            with st.expander("👀 View Keywords"):
                for i, kw in enumerate(keywords, 1):
                    st.write(f"{i}. {kw}")
        else:
            st.info("👆 Enter keywords in the text area above")
    
    # Scraping Section
    st.markdown("---")
    
    if keywords:
        if st.button("🚀 Start Scraping", key="scrape_btn", use_container_width=True):
            all_results = []
            total_found = 0
            
            with st.status("🔄 Scraping with Playwright...", expanded=True) as status:
                for idx, kw in enumerate(keywords, 1):
                    st.write(f"🔎 [{idx}/{len(keywords)}] Scraping: **{kw}**")
                    result = scrape_google_search(kw, pages, st.empty())
                    total_found += len(result)
                    all_results.extend(result)
                    
                    # Small delay between keywords
                    if idx < len(keywords):
                        time.sleep(1)
                
                # Remove duplicate domains
                st.write("🔄 Removing duplicates...")
                unique = {}
                for item in all_results:
                    url = item.get("URL", "")
                    domain = urllib.parse.urlparse(url).netloc if url else ""
                    
                    if domain not in unique:
                        unique[domain] = item
                
                all_results = list(unique.values())
                status.update(label="✅ Scraping completed!", state="complete")
            
            # Results Section
            st.markdown("---")
            st.subheader("📊 Results")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Keywords Scraped", len(keywords))
            with col2:
                st.metric("Total URLs Found (Before Dedup)", total_found)
            with col3:
                st.metric("Unique Domains", len(all_results))
            
            # Display Results Table
            if all_results:
                display_df = pd.DataFrame(all_results)[["Domain", "Title", "URL"]]
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    height=400
                )
                
                # Download as CSV
                csv_buffer = io.StringIO()
                display_df.to_csv(csv_buffer, index=False)
                csv_content = csv_buffer.getvalue()
                
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv_content,
                    file_name=f"scraped_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # Download as Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    display_df.to_excel(writer, sheet_name='Results', index=False)
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Results as Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"scraped_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ No results found. Google may have blocked the request.")
    else:
        st.info("👆 Use either tab above to provide keywords for scraping")


if __name__ == "__main__":
    main()