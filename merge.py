import logging, requests
from loader import load_config, load_sources, load_groups, load_alias
from processor import process_lines, convert_txt_to_m3u
from exporter import export_m3u

def main():
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

    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    channels = {}
    stats = {"added": 0, "appended": 0, "skipped": 0,
             "blocked": 0, "filtered": 0, "missing_url": 0}
    header_lines = []

    # ===== 本地文件 =====
    for fname in sources.get("local_files", []):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                first_line = lines[0].lstrip("\ufeff").strip() if lines else ""
                if not first_line.startswith("#EXTM3U"):
                    lines = convert_txt_to_m3u(lines, default_group)
                else:
                    header_lines.append(first_line)
                process_lines(lines, alias_map, rules, blocklist,
                              keep_multiple_urls, channels,
                              primary=True, source_name=f"本地:{fname}",
                              default_group=default_group, stats=stats)
            logging.info(f"[INFO] 成功读取本地文件: {fname}")
        except Exception as e:
            logging.error(f"[ERROR] 读取本地文件失败 {fname}: {e}")

    # ===== 远程文件 =====
    headers = {"User-Agent": config["ua"]}
    if config["referrer"]:
        headers["Referer"] = config["referrer"]

    for src in sources.get("remote_urls", []):
        url = src["url"]
        primary_flag = src.get("primary", False)
        include_channels = src.get("include_channels", [])
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
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
            first_line = lines[0].lstrip("\ufeff").strip() if lines else ""
            if not first_line.startswith("#EXTM3U"):
                logging.warning(f"[WARN] {url} 首行不是标准 M3U，尝试转换")
                lines = convert_txt_to_m3u(lines, default_group)
            else:
                header_lines.append(first_line)

            process_lines(lines, alias_map, rules, blocklist,
                          keep_multiple_urls, channels,
                          primary=primary_flag, source_name=f"远程:{url}",
                          default_group=default_group,
                          whitelist=include_channels,
                          stats=stats)
            logging.info(f"[INFO] 成功读取远程文件: {url}")
        except Exception as e:
            logging.error(f"[ERROR] 读取远程文件失败 {url}: {e}")

    # ===== 导出 =====
    export_m3u(
        channels,
        custom_channels,
        group_order,
        epg,
        keep_multiple_urls,
        outfile=config["output_file"],
        generate_debug_file=config["generate_debug_file"],
        default_group=default_group,
        header_lines=header_lines
    )

    # ===== 总结 =====
    logging.info("[SUMMARY] 处理结果：")
    for k, v in stats.items():
        logging.info(f"  {k}: {v}")

if __name__ == "__main__":
    main()
