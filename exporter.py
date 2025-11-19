import logging

def export_m3u(channels, custom_channels, group_order, epg, keep_multiple_urls,
               outfile="kudog.m3u", generate_debug_file=False, default_group="综合",
               header_lines=None):
    merged = []
    if header_lines:
        merged.extend(header_lines)
        logging.info(f"[INFO] 已保留远程源首行信息，共 {len(header_lines)} 条")
    else:
        merged.append(f'#EXTM3U x-tvg-url="{epg}"')

    for ch in custom_channels:
        merged.append(
            f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
            f'group-title="{ch.get("group", default_group)}",{ch["name"]}'
        )
        merged.append(ch["url"])

    group_counts = {}
    for group in group_order + [default_group]:
        for name, ch in channels.items():
            if ch.get("group") == group:
                merged.append(ch["line"])
                urls = ch["urls"] if keep_multiple_urls else [ch["urls"][0]]
                merged.extend(urls)
                group_counts[group] = group_counts.get(group, 0) + 1

    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(merged))
    logging.info(f"[DONE] 已生成主输出文件: {outfile}")

    if generate_debug_file:
        debug_file = "merged.m3u"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(merged))
        logging.info(f"[DEBUG] 已生成调试文件: {debug_file}")

    logging.info("[SUMMARY] 分组统计：")
    for group, count in group_counts.items():
        logging.info(f"  {group}: {count} 个频道")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
