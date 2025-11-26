import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any
from loader import loadconfig, loadsources, loadgroups, loadalias  # 导入数据加载
from processor import process_lines, convert_txt_to_m3u         # 导入核心处理
from exporter import export_m3u                               # 导入输出模块

def main():
    """主程序：加载→处理→输出完整流程"""
    print("🚀 Starting M3U Merger...")
    
    # === 1. 加载所有配置和数据 ===
    config = loadconfig()
    sources = loadsources()
    groups = loadgroups()
    aliasmap = loadalias()
    
    # 提取关键参数
    rules = groups.get('rules', {})           # 分组规则
    customchannels = groups.get('customchannels', [])  # 自定义频道
    blocklist = groups.get('blocklist', [])    # 黑名单
    grouporder = list(rules.keys())           # 分组排序
    
    keep_multiple_urls = config['keepmultipleurls']
    timeout = config['timeout']
    epg = config['epg']
    default_group = config['defaultgroup']
    
    # === 2. 配置日志系统 ===
    loglevel = getattr(logging, config.get('loglevel', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=loglevel, format='%(levelname)s %(message)s')
    
    channels: Dict[str, Any] = {}  # 最终去重结果 {规范名: {line, urls, group}}
    
    # === 3. 处理本地文件（主源，优先级最高） ===
    for fname in sources.get('local_files', []):
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            first_line = lines[0].lstrip().strip().upper() if lines else ''
            if not first_line.startswith('#EXTM3U'):  # TXT格式转换
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=True, source_name=f"📁{fname}", 
                         default_group=default_group)
        except Exception as e:
            logging.warning(f"✗ LOCAL ERROR {fname}: {e}")
    
    # === 4. 处理远程URL（自动重试3次） ===
    session = requests.Session()  # 复用连接池
    retry_strategy = Retry(total=config.get('max_retries', 3), backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    is_primary = True  # 第一个远程源也作为主源
    for src in sources.get('remote_urls', []):
        try:
            # 解析源配置，支持字符串URL和对象{url, include_channels}
            if isinstance(src, str):
                url = src
                include_channels = []
            else:
                url = src.get('url')
                include_channels = src.get('include_channels', [])
            
            headers = {'User-Agent': config['ua']}
            if config.get('referrer'):
                headers['Referer'] = config['referrer']
                
            resp = session.get(url, headers=headers, timeout=timeout)
            resp.raise_forstatus()  # HTTP错误抛异常
            
            # 智能解码
            try:
                text = resp.content.decode('utf-8', errors='ignore').strip()
            except Exception:
                text = resp.text.strip()
            
            if not text:
                logging.warning(f"✗ EMPTY RESPONSE: {url}")
                continue
                
            lines = text.splitlines()
            first_line = lines[0].lstrip().strip().upper() if lines else ''
            if not first_line.startswith('#EXTM3U'):
                lines = convert_txt_to_m3u(lines, default_group)
            
            process_lines(lines[1:], aliasmap, rules, blocklist, keep_multiple_urls, 
                         channels, primary=is_primary, source_name=f"🌐{url}", 
                         default_group=default_group, whitelist=include_channels)
            logging.info(f"✓ REMOTE OK: {url}")
            is_primary = False  # 后续远程源为次源
            
        except requests.exceptions.Timeout:
            logging.warning(f"⏰ TIMEOUT: {url}")
        except requests.exceptions.HTTPError as e:
            logging.warning(f"📡 HTTP {e.response.status_code}: {url}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"📡 REQUEST ERROR: {url} - {str(e)}")
        except Exception as e:
            logging.warning(f"💥 UNEXPECTED: {url} - {str(e)}")
    
    # === 5. 导出最终结果 ===
    export_m3u(channels, customchannels, grouporder, epg, keep_multiple_urls,
               outfile=config['outputfile'], generatedebugfile=config['generatedebugfile'],
               defaultgroup=default_group)
    
    total_channels = len(channels)
    logging.info(f"🎉 COMPLETED! Total: {total_channels} unique channels")

if __name__ == '__main__':
    main()
