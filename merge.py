#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kudog M3U Merger - 终极稳定版
修复所有requests和sources.json格式问题
"""

import logging
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, List
from loader import loadconfig, loadsources, loadgroups, loadalias
from processor import process_lines, convert_txt_to_m3u
from exporter import export_m3u

def main():
    print("🚀 Kudog M3U Merger v2.0 - Starting...")
    
    # === 1. 加载所有配置 ===
    config = loadconfig()
    sources = loadsources()
    groups = loadgroups()
    aliasmap = loadalias()
    
    print(f"📋 Config: {config['outputfile']}")
    print(f"📊 Sources: {len(sources.get('local_files', []))} local, {len(sources.get('remote_urls', []))} remote")
    print(f"🔑 Aliases: {len(aliasmap)}")
    
    rules = groups.get('rules', {})
    customchannels = groups.get('customchannels', [])
    blocklist = groups.get('blocklist', [])
    grouporder = list(rules.keys())
    
    keep_multiple_urls = config['keepmultipleurls']
    timeout = config['timeout']
    epg = config['epg']
    default_group = config['defaultgroup']
    
    # === 2. 配置日志 ===
    loglevel = getattr(logging, config.get('loglevel', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=loglevel, format='%(levelname)s %(message)s')
    
    channels: Dict[str, Any] = {}
    
    # === 3. 处理本地文件 ===
    for fname in sources.get('local_files', []):
        if not isinstance(fname, str):
            logging.warning(f"❌ INVALID LOCAL FILE: {fname}")
            continue
        if not os.path.exists(fname):
            logging.warning(f"❌ FILE NOT FOUND: {fname}")
            continue
        try:
            with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().splitlines()
            if not lines:
                logging.warning(f"❌ EMPTY FILE: {fname}")
                continue
                
            first_line = lines[0].lstrip().strip().upper()
            if not first_line.startswith('#EXTM3U'):
                logging.info(f"🔄 Converting TXT to M3U: {fname}")
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=True, source_name=f"📁{fname}", 
                         default_group=default_group)
            logging.info(f"✓ LOCAL OK: {fname} ({len(lines)} lines)")
        except Exception as e:
            logging.error(f"✗ LOCAL ERROR {fname}: {type(e).__name__}: {e}")
    
    # === 4. 处理远程URL（终极修复） ===
    session = requests.Session()
    retry_strategy = Retry(
        total=3, 
        backoff_factor=1, 
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    processed_count = 0
    for idx, src in enumerate(sources.get('remote_urls', [])):
        try:
            # ✅ 兼容各种sources.json格式
            if isinstance(src, str):
                url = src.strip()
                include_channels: List[str] = []
            elif isinstance(src, dict):
                url = src.get('url', '').strip()
                include_channels = src.get('include_channels', [])
                if not url:
                    logging.warning(f"❌ EMPTY URL at index {idx}")
                    continue
            else:
                logging.warning(f"❌ INVALID SOURCE at index {idx}: {type(src)}")
                continue
            
            headers = {
                'User-Agent': config['ua'],
                'Accept': 'text/plain,*/*',
                'Connection': 'keep-alive'
            }
            if config.get('referrer'):
                headers['Referer'] = config['referrer']
            
            logging.info(f"🌐 Fetching ({idx+1}/{len(sources.get('remote_urls', []))}): {url}")
            
            # ✅ 终极修复：session.get() + 异常处理
            resp = session.get(url, headers=headers, timeout=timeout, stream=True)
            resp.raise_for_status()  # HTTP状态检查
            
            text = resp.text.strip()
            if not text:
                logging.warning(f"❌ EMPTY RESPONSE: {url}")
                continue
                
            lines = text.splitlines()
            if not lines:
                logging.warning(f"❌ NO LINES: {url}")
                continue
                
            first_line = lines[0].lstrip().strip().upper()
            if not first_line.startswith('#EXTM3U'):
                logging.info(f"🔄 Converting TXT: {url}")
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=False, source_name=f"🌐{url}", 
                         default_group=default_group, whitelist=include_channels)
            
            processed_count += 1
            logging.info(f"✓ REMOTE OK ({processed_count}): {url}")
            
        except requests.exceptions.Timeout:
            logging.warning(f"⏰ TIMEOUT ({idx+1}): {url}")
        except requests.exceptions.HTTPError as e:
            logging.warning(f"📡 HTTP {e.response.status_code} ({idx+1}): {url}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"📡 REQUEST ERROR ({idx+1}): {url} - {str(e)}")
        except Exception as e:
            logging.error(f"💥 CRITICAL ({idx+1}): {url} - {type(e).__name__}: {str(e)}")
    
    # === 5. 导出结果 ===
    export_m3u(channels, customchannels, grouporder, epg, keep_multiple_urls,
               outfile=config['outputfile'], 
               generatedebugfile=config['generatedebugfile'],
               defaultgroup=default_group)
    
    total = len(channels)
    print(f"\n🎉 SUCCESS! {total} unique channels → {config['outputfile']}")
    logging.info(f"📊 FINAL: {total} channels from {processed_count} sources")

if __name__ == '__main__':
    main()
