import logging, requests
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

    # ===== 统计信息 =====
    stats = {
        "added": 0,
        "appended": 0,
        "skipped": 0,
        "blocked": 0,
        "filtered": 0,
        "missing_url": 0
    }

    # ===== 本地源 =====
    for fname in sources.get("local_files", []):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
                if not first_line.startswith("#EXTM3U") and not first_line.startswith("EXTM3U"):
                    # TXT 转换时传入 default_group
                    lines = convert_txt_to_m3u(lines, default_group)
                # 🚨 保留首行，不再跳过
                process_lines(lines, alias_map, rules, blocklist,
                              keep_multiple_urls, channels,
                              primary=True, source_name=f"本地:{fname}",
                              default_group=default_group,
                              stats=stats)
            logging.info(f"[INFO] 成功读取本地文件: {fname}")
        except Exception as e:
            logging.warning(f"[WARN] 本地文件 {fname} 读取失败: {e}")

    # ===== 远程源 =====
    for src in sources.get("remote_urls", []):
        try:
            if isinstance(src, str):
                url = src
                include_channels = []
                primary_flag = True  # 默认字符串源视为主源
            else:
                url = src.get("url")
                include_channels = src.get("include_channels", [])
                primary_flag = src.get("primary", False)

            headers = {"User-Agent": config["ua"]}
            if config["referrer"]:
                headers["Referer"] = config["referrer"]

            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()

            # 🚨 尝试多种解码，避免 BOM/GBK 问题
            try:
                text = resp.content.decode("utf-8-sig").strip()
            except Exception:
                try:
                    text = resp.content.decode("gbk", errors="ignore").strip()
                except Exception:
                    text = resp.text.strip()

            if not text:
                logging.warning(f"[WARN] {url} 返回空内容")
                continue

            lines = text.splitlines()
            first_line = lines[0].lstrip("\ufeff").strip().upper() if lines else ""
            if not first_line.startswith("#EXTM3U"):
                logging.warning(f"[WARN] {url} 首行不是标准 M3U，尝试转换")
                # TXT 转换时传入 default_group
                lines = convert_txt_to_m3u(lines, default_group)

            # 🚨 保留首行，不再跳过
            process_lines(lines, alias_map, rules, blocklist,
                          keep_multiple_urls, channels,
                          primary=primary_flag, source_name=f"远程:{url}",
                          default_group=default_group,
                          whitelist=include_channels,
                          stats=stats)
            logging.info(f"[INFO] 成功读取远程文件: {url}")
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

    # ===== 输出统计 =====
    logging.info("[SUMMARY] 分组统计：")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
    logging.info(f"[SUMMARY] 新增频道数: {stats['added']}")
    logging.info(f"[SUMMARY] 追加URL数: {stats['appended']}")
    logging.info(f"[SUMMARY] 缺URL跳过数: {stats['missing_url']}")
    logging.info(f"[SUMMARY] 被过滤数: {stats['filtered']}")
    logging.info(f"[SUMMARY] 被屏蔽数: {stats['blocked']}")
    logging.info(f"[SUMMARY] 跳过数: {stats['skipped']}")

if __name__ == "__main__":
    main()
