import os
import re
import base64
import requests
from bs4 import BeautifulSoup

def download_and_encode_fonts(css_content):
    urls = set(re.findall(r'url\((https://[^)]+)\)', css_content))
    for url in urls:
        # Some URLs might have quotes around them
        clean_url = url.strip("'\"")
        print(f"Downloading font: {clean_url}")
        resp = requests.get(clean_url)
        if resp.status_code == 200:
            encoded = base64.b64encode(resp.content).decode('utf-8')
            mime = 'font/woff2' if clean_url.endswith('.woff2') else 'font/woff'
            data_url = f"data:{mime};charset=utf-8;base64,{encoded}"
            css_content = css_content.replace(url, data_url)
            # Also replace the unquoted version if the original had quotes
            css_content = css_content.replace(f"'{clean_url}'", data_url)
            css_content = css_content.replace(f'"{clean_url}"', data_url)
    return css_content

def main():
    input_file = 'OneFile-PDF-Merger.html'
    output_file = 'OneFile-Offline.html'
    
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Process Stylesheets
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href')
        if href and href.startswith('http'):
            print(f"Fetching CSS: {href}")
            resp = requests.get(href)
            if resp.status_code == 200:
                css_text = resp.text
                css_text = download_and_encode_fonts(css_text)
                new_style = soup.new_tag('style')
                new_style.string = css_text
                link.replace_with(new_style)

    # Remove preconnect links
    for link in soup.find_all('link', rel='preconnect'):
        link.decompose()

    # 2. Process Scripts
    for script in soup.find_all('script'):
        src = script.get('src')
        if src and src.startswith('http'):
            print(f"Fetching JS: {src}")
            resp = requests.get(src)
            if resp.status_code == 200:
                new_script = soup.new_tag('script')
                new_script.string = resp.text
                script.replace_with(new_script)

    # 3. Handle the Worker Hack
    html_str = str(soup)
    
    # regex to find pdfjsLib.GlobalWorkerOptions.workerSrc = '...';
    worker_pattern = r"pdfjsLib\.GlobalWorkerOptions\.workerSrc\s*=\s*(['\"])(.*?)\1;"
    match = re.search(worker_pattern, html_str)
    
    if match:
        worker_url = match.group(2)
        print(f"Fetching Worker: {worker_url}")
        resp = requests.get(worker_url)
        if resp.status_code == 200:
            worker_code = resp.text
            # Escape backticks and standard escapes
            worker_code = worker_code.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
            
            worker_hack = f"""
  // --- INLINE WORKER HACK ---
  const workerCode = `{worker_code}`;
  const workerBlob = new Blob([workerCode], {{ type: 'text/javascript' }});
  const workerUrl = URL.createObjectURL(workerBlob);
  pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;
            """
            html_str = html_str[:match.start()] + worker_hack + html_str[match.end():]
        else:
            print("Failed to fetch worker")
    else:
        print("Worker config not found.")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_str)
        
    print(f"Successfully created {output_file}")

if __name__ == '__main__':
    main()
