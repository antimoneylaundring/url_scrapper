from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from playwright.sync_api import sync_playwright
import urllib.parse
import time
import threading
import os
from datetime import datetime
import io
import csv

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

EXCLUDE_DOMAINS = [
    "youtube.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "justdial.com", "quora.com", "reddit.com", "telegram.org"
]

# Global variable to store scraping progress
scraping_progress = {
    "status": "idle",
    "current_keyword": "",
    "keyword_index": 0,
    "total_keywords": 0,
    "results_found": 0,
    "message": ""
}


def normalize_url(url):
    """Normalize URL for comparison"""
    url = str(url).strip().lower()
    if url.startswith("http://"):
        url = url.replace("http://", "", 1)
    elif url.startswith("https://"):
        url = url.replace("https://", "", 1)
    url = url.split('/')[0].split('?')[0].split('#')[0]
    if url.startswith("www."):
        url = url[4:]
    if ":" in url:
        url = url.split(":")[0]
    return url.strip()


def scrape_google_search(keyword, max_pages=2):
    """Scrape Google Search using Playwright"""
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            page.set_default_timeout(15000)
            
            for page_num in range(max_pages):
                try:
                    start = page_num * 10
                    search_url = f'https://www.google.com/search?q="{urllib.parse.quote_plus(keyword)}"&start={start}'
                    
                    page.goto(search_url, wait_until="networkidle")
                    time.sleep(2)
                    
                    # Check for blocking
                    page_content = page.content().lower()
                    if any(x in page_content for x in ["unusual traffic", "captcha", "detected unusual traffic"]):
                        break
                    
                    # Extract links
                    links = page.query_selector_all('a')
                    found = 0
                    
                    for link in links:
                        try:
                            href = link.get_attribute('href')
                            if not href or not href.startswith("http"):
                                continue
                            if any(x in href for x in ["google.", "webcache.googleusercontent.com"]):
                                continue
                            
                            domain = urllib.parse.urlparse(href).netloc.lower()
                            if any(excluded in domain for excluded in EXCLUDE_DOMAINS):
                                continue
                            
                            title = link.text_content().strip()[:100]
                            results.append({
                                "Domain": domain,
                                "URL": href,
                                "Title": title if title else domain
                            })
                            found += 1
                        except:
                            continue
                    
                    if found == 0:
                        break
                
                except Exception as e:
                    break
            
            context.close()
            browser.close()
    
    except Exception as e:
        print(f"Error: {e}")
    
    return results


def scrape_keywords_background(keywords, max_pages, old_urls_set):
    """Scrape keywords in background thread"""
    global scraping_progress
    
    scraping_progress["status"] = "running"
    scraping_progress["total_keywords"] = len(keywords)
    all_results = []
    
    try:
        for idx, keyword in enumerate(keywords):
            scraping_progress["current_keyword"] = keyword
            scraping_progress["keyword_index"] = idx + 1
            scraping_progress["message"] = f"Scraping '{keyword}'..."
            
            results = scrape_google_search(keyword, max_pages)
            all_results.extend(results)
            scraping_progress["results_found"] = len(all_results)
            
            if idx < len(keywords) - 1:
                time.sleep(2)
        
        # Remove duplicates
        unique = {}
        for item in all_results:
            parsed = urllib.parse.urlparse(item["URL"])
            domain = parsed.netloc.lower()
            if domain not in unique:
                unique[domain] = {
                    "Domain": domain,
                    "URL": f"{parsed.scheme}://{parsed.netloc}",
                    "Title": item.get("Title", domain)
                }
        
        # Filter old URLs
        if old_urls_set:
            filtered = []
            for item in unique.values():
                cleaned = normalize_url(item["URL"])
                if cleaned not in old_urls_set:
                    filtered.append(item)
            final_results = filtered
        else:
            final_results = list(unique.values())
        
        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraper_results_{timestamp}.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        df = pd.DataFrame(final_results)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        scraping_progress["status"] = "completed"
        scraping_progress["message"] = f"Completed! {len(final_results)} results saved"
        scraping_progress["filename"] = filename
    
    except Exception as e:
        scraping_progress["status"] = "error"
        scraping_progress["message"] = f"Error: {str(e)}"


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """Start scraping"""
    global scraping_progress
    
    try:
        # Get form data
        keywords_input = request.form.get('keywords', '').strip()
        keywords_file = request.files.get('keywords_file')
        max_pages = int(request.form.get('max_pages', 2))
        
        # Get keywords
        if keywords_file:
            df = pd.read_excel(keywords_file)
            keywords = df['Keywords'].dropna().astype(str).tolist()
        else:
            keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
        
        if not keywords:
            return jsonify({"error": "No keywords provided"}), 400
        
        # Get old URLs
        old_urls_set = set()
        old_urls_file = request.files.get('old_urls_file')
        if old_urls_file:
            df = pd.read_excel(old_urls_file)
            old_urls = df.iloc[:, 0].dropna().astype(str).tolist()
            old_urls_set = {normalize_url(url) for url in old_urls}
        
        # Reset progress
        scraping_progress = {
            "status": "running",
            "current_keyword": "",
            "keyword_index": 0,
            "total_keywords": len(keywords),
            "results_found": 0,
            "message": "Starting scrape..."
        }
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=scrape_keywords_background,
            args=(keywords, max_pages, old_urls_set)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({"status": "started"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/progress', methods=['GET'])
def api_progress():
    """Get scraping progress"""
    return jsonify(scraping_progress)


@app.route('/api/download/<filename>')
def api_download(filename):
    """Download results"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔍 Google Search Web Scraper - Flask App")
    print("="*60)
    print("\n✅ Starting server at http://localhost:5000")
    print("📝 Open your browser and go to: http://localhost:5000\n")
    app.run(debug=True, host='0.0.0.0', port=5000)