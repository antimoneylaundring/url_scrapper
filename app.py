import streamlit as st
import csv
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import random
import pandas as pd
import io


EXCLUDE_DOMAINS = [
    "youtube.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "justdial.com", "quora.com", "reddit.com", "telegram.org"
]


# Strong Normalizer (Important!)
def normalize_url_for_compare(url):
    url = str(url).strip().lower()
    
    # remove protocol
    if url.startswith("http://"):
        url = url.replace("http://", "", 1)
    elif url.startswith("https://"):
        url = url.replace("https://", "", 1)
    
    # remove path/query/hash
    url = url.split('/')[0].split('?')[0].split('#')[0]
    
    # remove leading www.
    if url.startswith("www."):
        url = url[4:]
    
    # remove port if exists
    if ":" in url:
        url = url.split(":")[0]
    
    return url.strip()


def scrape_google_search(keyword, pages, progress_placeholder):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    except Exception as e:
        st.error(f"Error: Could not initialize Chrome driver. Make sure Chrome is installed. Details: {e}")
        return []
    
    driver.set_page_load_timeout(15)
    results = []
    
    for page in range(pages):
        start = page * 10
        search_url = f'https://www.google.com/search?q="{urllib.parse.quote_plus(keyword)}"&start={start}'
        
        progress_placeholder.info(f"📄 Loading page {page+1}/{pages} for '{keyword}'...")
        
        try:
            driver.get(search_url)
        except Exception as e:
            progress_placeholder.warning(f"⚠️ Timeout or error on page {page+1}: {e}")
            break
        
        time.sleep(random.randint(5, 8))
        
        page_source = driver.page_source
        if ("unusual traffic" in page_source or "detected unusual traffic" in page_source or 
            "captcha" in page_source or "To continue, please type the characters below" in page_source):
            progress_placeholder.error(f"❌ Blocked by Google on keyword: {keyword}, page: {page+1}")
            break
        
        search_results = driver.find_elements(By.CSS_SELECTOR, 'a')
        found = 0
        
        for result in search_results:
            href = result.get_attribute('href')
            if (href and href.startswith("http") and 
                "google." not in href and 
                "webcache.googleusercontent.com" not in href):
                
                domain = urllib.parse.urlparse(href).netloc.lower()
                
                if any(excluded in domain for excluded in EXCLUDE_DOMAINS):
                    continue
                
                results.append({
                    "Domain": domain,
                    "URL": href
                })
                found += 1
        
        if found == 0:
            break
    
    driver.quit()
    return results


def main():
    st.set_page_config(page_title="Google Search Web Scraper", page_icon="🔍", layout="wide")
    
    st.title("🔍 Google Search Web Scraper")
    st.markdown("---")
    
    # Instructions
    with st.expander("ℹ️ How to use this app", expanded=False):
        st.markdown("""
        **Option 1: Upload Keywords File**
        1. Upload an Excel file (`.xlsx`) with a 'Keywords' column
        
        **Option 2: Enter Keywords Manually**
        1. Enter keywords in the text area (one per line)
        
        2. Configure scraping options
        3. Click 'Start Scraping'
        4. Download results as CSV
        
        **Note**: Each page contains approximately 10 search results.
        """)
    
    # Sidebar Configuration
    st.sidebar.header("⚙️ Configuration")
    pages = st.sidebar.slider("Number of pages to scrape:", 1, 50, 3, help="Each page has ~10 results")
    
    st.sidebar.markdown("---")
    st.sidebar.info("📊 **Excluded Domains**: YouTube, Twitter, Instagram, LinkedIn, Quora, Reddit, Telegram, JustDial")
    
    # Main Content - Tabs for different input methods
    tab1, tab2 = st.tabs(["📁 Upload File", "✏️ Manual Input"])
    
    keywords = []
    
    # TAB 1: Upload File
    with tab1:
        st.subheader("📁 Upload Keywords File")
        uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx", label_visibility="collapsed")
        
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                if 'Keywords' not in df.columns:
                    st.error("❌ Error: Excel file must contain a 'Keywords' column")
                else:
                    keywords = df['Keywords'].dropna().tolist()
                    st.success(f"✅ Loaded {len(keywords)} keywords")
                    
                    with st.expander("👀 View Keywords"):
                        st.write(keywords)
            
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
        else:
            st.info("👆 Upload an Excel file (.xlsx) with a 'Keywords' column to begin")
    
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
                st.write(keywords)
        else:
            st.info("👆 Enter keywords in the text area above to begin")
    
    # Scraping Section (Common for both tabs)
    st.markdown("---")
    
    if keywords:
        if st.button("🚀 Start Scraping", key="scrape_btn", use_container_width=True):
            all_results = []
            total_found = 0
            
            with st.status("🔄 Scraping in progress...", expanded=True) as status:
                for kw in keywords:
                    st.write(f"🔎 Scraping: **{kw}**")
                    result = scrape_google_search(kw, pages, st.empty())
                    total_found += len(result)
                    st.write(f"   ✓ Found {len(result)} URLs")
                    all_results.extend(result)
                
                # Remove duplicate domains
                st.write("🔄 Removing duplicates...")
                unique = {}
                for item in all_results:
                    parsed = urllib.parse.urlparse(item["URL"])
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    unique[base_url] = {
                        "Domain": item["Domain"],
                        "URL": base_url
                    }
                all_results = list(unique.values())
                
                status.update(label="✅ Scraping completed!", state="complete")
            
            # Results Section
            st.markdown("---")
            st.subheader("📊 Results")
            
            results_col1, results_col2, results_col3 = st.columns(3)
            with results_col1:
                st.metric("Keywords Scraped", len(keywords))
            with results_col2:
                st.metric("Total URLs Found (Before Dedup)", total_found)
            with results_col3:
                st.metric("Unique Domains", len(all_results))
            
            # Display Results Table
            if all_results:
                st.dataframe(
                    pd.DataFrame(all_results),
                    use_container_width=True,
                    height=400
                )
                
                # Download Button
                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=["Domain", "URL"])
                writer.writeheader()
                writer.writerows(all_results)
                csv_content = csv_buffer.getvalue()
                
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv_content,
                    file_name="scraped_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ No results found after filtering.")
    else:
        st.info("👆 Use either tab above to provide keywords for scraping")


if __name__ == "__main__":
    main()