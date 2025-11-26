import logging
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any
from loader import loadconfig, loadsources, loadgroups, loadalias
from processor import process_lines, convert_txt_to_m3u
from exporter import export_m3u

def main():
    print("🚀 Starting M3U Merger...")
    
    # 1. 加载配置
    config = loadconfig()
    sources = loadsources()
    groups = loadgroups()
    aliasmap = loadalias()
    
    rules = groups.get('rules', {})
    customchannels = groups.get('customchannels', [])
    blocklist = groups.get('blocklist', [])
    grouporder = list(rules.keys())
    
    keep_multiple_urls = config['keepmultipleurls']
    timeout = config['timeout']
    epg = config['epg']
    default_group = config['defaultgroup']
    
    # 2. 配置日志
    loglevel = getattr(logging, config.get('loglevel', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=loglevel, format='%(levelname)s %(message)s')
    
    channels: Dict[str, Any] = {}
    
    # 3. 处理本地文件
    for fname in sources.get('local_files', []):
        if not os.path.exists(fname):
            logging.warning(f"❌ LOCAL FILE NOT FOUND: {fname}")
            continue
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            if not lines:
                logging.warning(f"❌ EMPTY FILE: {fname}")
                continue
            first_line = lines[0].lstrip().strip().upper()
            if not first_line.startswith('#EXTM3U'):
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=True, source_name=f"📁{fname}", 
                         default_group=default_group)
            logging.info(f"✓ PROCESSED LOCAL: {fname}")
        except Exception as e:
            logging.warning(f"✗ LOCAL ERROR {fname}: {e}")
    
    # 4. 处理远程URL（修复版）
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    for src in sources.get('remote_urls', []):
        try:
            # 解析源配置
            if isinstance(src, str):
                url = src.strip()
                include_channels = []
            else:
                url = src.get('url', '').strip()
                include_channels = src.get('include_channels', [])
                if not url:
                    logging.warning("❌ EMPTY URL in sources.json")
                    continue
            
            headers = {'User-Agent': config['ua']}
            if config.get('referrer'):
                headers['Referer'] = config['referrer']
            
            # ✅ 修复：使用session.get()
            resp = session.get(url, headers=headers, timeout=timeout)
            resp.raise_forstatus()  # 检查HTTP状态码
            
            text = resp.text.strip()
            if not text:
                logging.warning(f"❌ EMPTY RESPONSE: {url}")
                continue
                
            lines = text.splitlines()
            first_line = lines[0].lstrip().strip().upper() if lines else ''
            if not first_line.startswith('#EXTM3U'):
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=False, source_name=f"🌐{url}", 
                         default_group=default_group, whitelist=include_channels)
            logging.info(f"✓ PROCESSED REMOTE: {url}")
            
        except requests.exceptions.Timeout:
            logging.warning(f"⏰ TIMEOUT: {url}")
        except requests.exceptions.HTTPError as e:
            logging.warning(f"📡 HTTP {e.response.status_code}: {url}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"📡 REQUEST ERROR: {url} - {str(e)}")
        except Exception as e:
            logging.warning(f"💥 UNEXPECTED: {url} - {str(e)}")
    
    # 5. 导出结果
    export_m3u(channels, customchannels, grouporder, epg, keep_multiple_urls,
               outfile=config['outputfile'], generatedebugfile=config['generatedebugfile'],
               defaultgroup=default_group)
    
    total = len(channels)
    logging.info(f"🎉 COMPLETED! {total} unique channels → {config['outputfile']}")

if __name__ == '__main__':
    main()
