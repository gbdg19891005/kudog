import logging, requests, time
from loader import load_config, load_sources, load_groups, load_alias
from processor import process_lines, convert_txt_to_m3u
from exporter import export_m3u

def main():
    # ===== 加载配置 =====
    config = load_config()
    sources = load_sources()
    groups = load_groups()
    alias_map = load_alias()

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
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    channels = {}

    # ===== 本地源 =====
    for fname in sources.get("local_files", []):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
                if not first_line.startswith("#EXTM3U") and not first_line.startswith("EXTM3U"):
                    # TXT 转换时传入 default_group
                    lines = convert_txt_to_m3u(lines, default_group)
                process_lines(lines[1:], alias_map, rules, blocklist,
                              keep_multiple_urls, channels,
                              primary=True, source_name=f"本地:{fname}",
                              default_group=default_group)
            logging.info(f"[INFO] 成功读取本地文件: {fname}")
        except Exception as e:
            logging.warning(f"[WARN] 本地文件 {fname} 读取失败: {e}")

    # ===== 远程源 =====
    is_primary = True
    for src in sources.get("remote_urls", []):
        try:
            if isinstance(src, str):
                url = src
                include_channels = []
            else:
                url = src.get("url")
                include_channels = src.get("include_channels", [])

            # 增强请求头
            headers = {
                "User-Agent": config["ua"],
                "Referer": config.get("referrer", "https://bc.188766.xyz/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
            }

            # 加随机参数避免缓存
            url_with_ts = f"{url}&ts={int(time.time())}"

            resp = requests.get(url_with_ts, headers=headers, timeout=timeout)
            resp.raise_for_status()

            try:
                text = resp.content.decode("utf-8", errors="ignore").strip()
            except Exception:
                text = resp.text.strip()

            if not text:
                logging.warning(f"[WARN] {url} 返回空内容")
                continue

            lines = text.splitlines()
            first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
            if not first_line.startswith("#EXTM3U") and not first_line.startswith("EXTM3U"):
                logging.warning(f"[WARN] {url} 首行不是标准 M3U，尝试转换")
                # TXT 转换时传入 default_group
                lines = convert_txt_to_m3u(lines, default_group)

            process_lines(lines[1:], alias_map, rules, blocklist,
                          keep_multiple_urls, channels,
                          primary=is_primary, source_name=f"远程:{url}",
                          default_group=default_group,
                          whitelist=include_channels)
            logging.info(f"[INFO] 成功读取远程文件: {url}")
            is_primary = False
        except Exception as e:
            logging.warning(f"[WARN] 远程文件 {url} 读取失败: {e}")

    # ===== 输出 M3U =====
    export_m3u(
        channels,
        custom_channels,
        group_order,
        epg,
        keep_multiple_urls,
        outfile=config["output_file"],
        generate_debug_file=config["generate_debug_file"],
        default_group=default_group
    )

if __name__ == "__main__":
    main()
