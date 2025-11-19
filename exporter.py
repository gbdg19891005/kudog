import logging

def export_m3u(channels, custom_channels, group_order, epg, keep_multiple_urls,
               outfile="kudog.m3u", generate_debug_file=False,
               default_group="综合", header_lines=None):
    merged = []

    # 只输出一条头：优先使用捕获的 header_lines 中的第一条，否则用配置 epg
    if header_lines and any(h.strip().startswith("#EXTM3U") for h in header_lines):
        # 去掉重复，只保留第一条
        for h in header_lines:
            if h.strip().startswith("#EXTM3U"):
                merged.append(h.strip())
                break
    else:
        merged.append(f'#EXTM3U url-tvg="{epg}"')

    # 添加自定义频道（如果 groups.json 有定义）
    for ch in custom_channels:
        merged.append(
            f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
            f'group-title="{ch.get("group", default_group)}",{ch["name"]}'
        )
        merged.append(ch["url"])

    # 按分组顺序输出频道
    group_counts = {}
    for group in group_order + [default_group]:
        for name, ch in channels.items():
            if ch.get("group") == group:
                merged.append(ch["line"])
                urls = ch["urls"] if keep_multiple_urls else [ch["urls"][0]]
                merged.extend(urls)
                group_counts[group] = group_counts.get(group, 0) + 1

    # 写入主输出文件
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(merged))
    logging.info(f"[DONE] 已生成主输出文件: {outfile}")

    # 写入调试文件（可选）
    if generate_debug_file:
        debug_file = "merged.m3u"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(merged))
        logging.info(f"[DEBUG] 已生成调试文件: {debug_file}")

    # 输出分组统计
    logging.info("[SUMMARY] 分组统计：")
    for group, count in group_counts.items():
        logging.info(f"  {group}: {count} 个频道")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
