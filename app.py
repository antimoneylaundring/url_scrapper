import streamlit as st
import pandas as pd
import io
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


EXCLUDE_DOMAINS = [
    "youtube.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "justdial.com", "quora.com", "reddit.com", "telegram.org"
]


def search_google(keyword, api_key, search_engine_id, num_results=10):
    """Search using Google Custom Search API"""
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        
        request = service.cse().list(
            q=keyword,
            cx=search_engine_id,
            num=min(num_results, 10),
            startIndex=1
        )
        
        response = request.execute()
        
        if 'items' not in response:
            return []
        
        results = []
        for item in response['items']:
            url = item.get('link', '')
            domain = url.split('/')[2].lower() if url else ''
            
            # Filter excluded domains
            if any(excluded in domain for excluded in EXCLUDE_DOMAINS):
                continue
            
            results.append({
                "Domain": domain,
                "URL": url,
                "Title": item.get('title', '')[:80],  # Limit title length
                "Snippet": item.get('snippet', '')[:150]  # Limit snippet length
            })
        
        return results
    
    except HttpError as e:
        st.error(f"❌ Google Search API Error: {e}")
        return []
    except Exception as e:
        st.error(f"❌ Error during search: {str(e)}")
        return []


def main():
    st.set_page_config(
        page_title="Google Search API Scraper",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Google Custom Search API Scraper")
    st.markdown("---")
    
    # Instructions
    with st.expander("ℹ️ How to Set Up", expanded=False):
        st.markdown("""
        ### Setup Steps:
        
        **1. Get Google API Key:**
        - Go to [Google Cloud Console](https://console.cloud.google.com/)
        - Create a new project
        - Enable "Custom Search API"
        - Go to "Credentials" → Create "API Key"
        
        **2. Get Search Engine ID:**
        - Go to [Google Programmable Search](https://programmablesearch.google.com/)
        - Create a new search engine (search entire web)
        - Copy the Search Engine ID (cx)
        
        **3. Free Tier:** 100 queries/day
        
        **4. No Blocking:** Google won't block API calls
        """)
    
    # Sidebar Configuration
    st.sidebar.header("⚙️ Configuration")
    
    # Try to get secrets from Streamlit, fallback to input
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY", "")
        search_engine_id = st.secrets.get("SEARCH_ENGINE_ID", "")
    except:
        api_key = ""
        search_engine_id = ""
    
    # If secrets not available, show input fields
    if not api_key:
        api_key = st.sidebar.text_input(
            "Google API Key",
            type="password",
            help="Get from Google Cloud Console"
        )
    
    if not search_engine_id:
        search_engine_id = st.sidebar.text_input(
            "Search Engine ID",
            help="Get from Programmable Search Engine"
        )
    
    # Results per keyword
    results_per_keyword = st.sidebar.slider(
        "Results per keyword:",
        min_value=1,
        max_value=10,
        value=10,
        help="Max 10 per API call"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("📊 **Excluded**: YouTube, Twitter, Instagram, LinkedIn, Quora, Reddit, Telegram")
    st.sidebar.warning("⚠️ **Free Tier**: 100 queries/day")
    
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
            st.info("👆 Upload Excel file with 'Keywords' column")
    
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
            st.success(f"✅ Ready to search {len(keywords)} keywords")
            
            with st.expander("👀 View Keywords"):
                for i, kw in enumerate(keywords, 1):
                    st.write(f"{i}. {kw}")
        else:
            st.info("👆 Enter keywords in text area")
    
    # Search Section
    st.markdown("---")
    
    if keywords:
        if st.button("🚀 Start Search", key="search_btn", use_container_width=True):
            # Validate credentials
            if not api_key or not search_engine_id:
                st.error("❌ Please provide both API Key and Search Engine ID")
                return
            
            all_results = []
            total_found = 0
            
            with st.status("🔄 Searching...", expanded=True) as status:
                for idx, kw in enumerate(keywords, 1):
                    st.write(f"🔎 [{idx}/{len(keywords)}] Searching: **{kw}**")
                    
                    result = search_google(kw, api_key, search_engine_id, results_per_keyword)
                    total_found += len(result)
                    all_results.extend(result)
                    
                    st.write(f"   ✓ Found {len(result)} results")
                
                # Remove duplicate domains
                st.write("🔄 Removing duplicates...")
                unique = {}
                for item in all_results:
                    url = item.get("URL", "")
                    domain = url.split('/')[2] if url else ""
                    
                    if domain not in unique:
                        unique[domain] = item
                
                all_results = list(unique.values())
                status.update(label="✅ Search completed!", state="complete")
            
            # Results Section
            st.markdown("---")
            st.subheader("📊 Results")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Keywords Searched", len(keywords))
            with col2:
                st.metric("Total Results (Before Dedup)", total_found)
            with col3:
                st.metric("Unique Domains", len(all_results))
            
            # Display Results
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
                    file_name=f"search_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
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
                    file_name=f"search_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ No results found.")
    else:
        st.info("👆 Use tabs above to provide keywords")


if __name__ == "__main__":
    main()