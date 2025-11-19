import logging

def export_m3u(channels, custom_channels, group_order, epg, keep_multiple_urls,
               outfile="kudog.m3u", generate_debug_file=False, default_group="综合",
               header_lines=None):
    """
    导出 M3U 文件
    :param channels: 频道字典
    :param custom_channels: 自定义频道列表
    :param group_order: 分组顺序
    :param epg: EPG 地址（来自 config.yaml）
    :param keep_multiple_urls: 是否保留多个 URL
    :param outfile: 主输出文件名
    :param generate_debug_file: 是否生成调试文件
    :param default_group: 默认分组
    :param header_lines: 来自远程源的首行列表（可选）
    """
    merged = []

    # ===== 首行处理 =====
    if header_lines:
        # 合并多个远程源首行，避免丢失 EPG/catchup 信息
        merged.extend(header_lines)
        logging.info(f"[INFO] 已保留远程源首行信息，共 {len(header_lines)} 条")
    else:
        # 如果没有远程首行，就用 config.yaml 的 epg
        merged.append(f'#EXTM3U x-tvg-url="{epg}"')

    # ===== 自定义频道置顶 =====
    for ch in custom_channels:
        merged.append(
            f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
            f'group-title="{ch.get("group", default_group)}",{ch["name"]}'
        )
        merged.append(ch["url"])

    # ===== 按 group_order 排序输出 =====
    group_counts = {}
    for group in group_order + [default_group]:
        for name, ch in channels.items():
            if ch.get("group") == group:
                merged.append(ch["line"])
                urls = ch["urls"] if keep_multiple_urls else [ch["urls"][0]]
                merged.extend(urls)
                group_counts[group] = group_counts.get(group, 0) + 1

    # ===== 写主输出文件 =====
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(merged))
    logging.info(f"[DONE] 已生成主输出文件: {outfile}")

    # ===== 可选：生成调试文件 =====
    if generate_debug_file:
        debug_file = "merged.m3u"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(merged))
        logging.info(f"[DEBUG] 已生成调试文件: {debug_file}")

    # ===== 分组统计 =====
    logging.info("[SUMMARY] 分组统计：")
    for group, count in group_counts.items():
        logging.info(f"  {group}: {count} 个频道")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
