import logging
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loader import load_config, load_sources, load_groups, load_alias
from processor import process_lines, convert_txt_to_m3u
from exporter import export_m3u


def get_session_with_retries(retries=3):
    """创建带重试机制的 requests session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def check_prerequisites():
    """检查运行前置条件"""
    import os
    import json
    import yaml
    
    required_files = ["config.yaml", "sources.json", "groups.json"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        raise FileNotFoundError(
            f"缺少必需文件: {', '.join(missing_files)}\n"
            "请确保配置文件存在于当前目录"
        )
    
    # 检查配置文件格式
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"config.yaml 格式错误: {e}")
    
    try:
        with open("sources.json", "r", encoding="utf-8") as f:
            json.load(f)
        with open("groups.json", "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 文件格式错误: {e}")
    
    logging.info("[CHECK] ✓ 前置检查通过")


def validate_url(url: str) -> bool:
    """验证 URL 合法性"""
    from urllib.parse import urlparse
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False


def fetch_remote_source(src, config, session, alias_map, rules, blocklist, 
                       keep_multiple_urls, default_group, source_index):
    """
    线程安全的远程源获取函数
    返回: (source_index, channels_dict, success, url, error_msg)
    """
    try:
        if isinstance(src, str):
            url = src
            include_channels = []
        else:
            url = src.get("url")
            include_channels = src.get("include_channels", [])

        # URL 验证
        if not validate_url(url):
            return (source_index, {}, False, url, "非法URL")

        headers = {"User-Agent": config["ua"]}
        if config["referrer"]:
            headers["Referer"] = config["referrer"]

        logging.info(f"[→] 正在获取远程文件: {url}")
        resp = session.get(url, headers=headers, timeout=config["timeout"])
        resp.raise_for_status()

        try:
            text = resp.content.decode("utf-8", errors="ignore").strip()
        except Exception:
            text = resp.text.strip()

        if not text:
            return (source_index, {}, False, url, "返回空内容")

        lines = text.splitlines()
        first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
        if not first_line.startswith("#EXTM3U") and not first_line.startswith("EXTM3U"):
            logging.warning(f"[!] {url} 首行不是标准 M3U，尝试转换")
            lines = convert_txt_to_m3u(lines, default_group)

        # 每个线程独立处理，返回频道字典
        temp_channels = {}
        process_lines(lines[1:], alias_map, rules, blocklist,
                     keep_multiple_urls, temp_channels,
                     primary=False, source_name=f"远程:{url}",
                     default_group=default_group,
                     whitelist=include_channels)
        
        return (source_index, temp_channels, True, url, None)

    except requests.exceptions.Timeout:
        return (source_index, {}, False, url, "请求超时")
    except requests.exceptions.ConnectionError:
        return (source_index, {}, False, url, "连接失败")
    except requests.exceptions.HTTPError as e:
        return (source_index, {}, False, url, f"HTTP错误 {e.response.status_code}")
    except Exception as e:
        return (source_index, {}, False, url, str(e))


def merge_channels(target, source, is_primary, keep_multiple_urls):
    """
    合并频道字典（保持原有逻辑）
    :param target: 目标频道字典
    :param source: 源频道字典
    :param is_primary: 是否为主源
    :param keep_multiple_urls: 是否保留多URL
    """
    from processor import are_urls_similar
    
    for name, ch in source.items():
        if name not in target:
            # 新频道直接添加
            target[name] = ch
        else:
            # 已存在频道，处理URL合并
            if is_primary:
                for url in ch["urls"]:
                    # 检查URL是否已存在（智能去重）
                    is_duplicate = any(are_urls_similar(url, existing) 
                                      for existing in target[name]["urls"])
                    
                    if not is_duplicate:
                        if keep_multiple_urls:
                            target[name]["urls"].append(url)
                        # 如果不保留多URL，忽略后续URL
                    # 如果是重复URL，忽略


def main():
    start_time = time.time()
    
    # ===== 前置检查 =====
    try:
        check_prerequisites()
    except Exception as e:
        print(f"错误: {e}")
        return
    
    # ===== 加载配置 =====
    try:
        config = load_config()
        sources = load_sources()
        groups = load_groups()
        alias_map = load_alias()
    except Exception as e:
        print(f"配置加载失败: {e}")
        return

    rules = groups["rules"]
    custom_channels = groups["custom_channels"]
    blocklist = groups.get("blocklist", [])
    group_order = list(rules.keys())

    keep_multiple_urls = config["keep_multiple_urls"]
    timeout = config["timeout"]
    epg = config["epg"]
    default_group = config["default_group"]

    # ===== 日志配置 =====
    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=log_level, 
        format="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    channels = {}
    session = get_session_with_retries()

    # ===== 本地源 =====
    local_count = 0
    for fname in sources.get("local_files", []):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
                if not first_line.startswith("#EXTM3U") and not first_line.startswith("EXTM3U"):
                    lines = convert_txt_to_m3u(lines, default_group)
                process_lines(lines[1:], alias_map, rules, blocklist,
                              keep_multiple_urls, channels,
                              primary=True, source_name=f"本地:{fname}",
                              default_group=default_group)
            logging.info(f"[✓] 成功读取本地文件: {fname}")
            local_count += 1
        except FileNotFoundError:
            logging.error(f"[✗] 本地文件不存在: {fname}")
        except Exception as e:
            logging.warning(f"[✗] 本地文件 {fname} 读取失败: {e}")

    # ===== 远程源并发下载 =====
    remote_sources = sources.get("remote_urls", [])
    remote_count = 0
    
    if remote_sources:
        # 并发配置
        max_workers = min(config.get("max_concurrent_downloads", 5), len(remote_sources))
        logging.info(f"[INFO] 使用 {max_workers} 个线程并发下载 {len(remote_sources)} 个远程源")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有下载任务
            futures = {}
            for idx, src in enumerate(remote_sources):
                future = executor.submit(
                    fetch_remote_source, src, config, session, 
                    alias_map, rules, blocklist, keep_multiple_urls, 
                    default_group, idx
                )
                futures[future] = idx
            
            # 按完成顺序处理结果，但按索引顺序合并（保持原有优先级逻辑）
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
            
            # 按源索引排序（保持原有顺序逻辑）
            results.sort(key=lambda x: x[0])
            
            # 按顺序合并频道
            for source_index, temp_channels, success, url, error_msg in results:
                if success:
                    # 第一个成功的源作为主源（如果没有本地源）
                    is_primary = (local_count == 0 and remote_count == 0)
                    merge_channels(channels, temp_channels, is_primary, keep_multiple_urls)
                    logging.info(f"[✓] 成功读取远程文件: {url}")
                    remote_count += 1
                else:
                    logging.error(f"[✗] 远程文件读取失败: {url} - {error_msg}")

    # ===== 输出 M3U =====
    if not channels:
        logging.error("[✗] 没有可用的频道数据，无法生成输出文件")
        return
    
    export_m3u(
        channels,
        custom_channels,
        group_order,
        epg,
        keep_multiple_urls,
        outfile=config["output_file"],
        generate_debug_file=config["generate_debug_file"],
        default_group=default_group,
        groups_config=groups
    )
    
    # ===== 性能统计 =====
    elapsed_time = time.time() - start_time
    logging.info(f"[PERFORMANCE] 总耗时: {elapsed_time:.2f}秒")
    if elapsed_time > 0:
        logging.info(f"[PERFORMANCE] 处理速度: {len(channels)/elapsed_time:.1f} 频道/秒")
    logging.info(f"[SUMMARY] 成功读取 {local_count} 个本地源，{remote_count} 个远程源")


if __name__ == "__main__":
    main()
