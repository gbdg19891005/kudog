import logging
import yaml
import os

def load_config(config_file="config.yaml"):
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def export_m3u(channels, custom_channels, group_order, epg,
               config_file="config.yaml"):
    """
    导出 M3U 文件，支持通过 config.yaml 控制哪些远程源保留多个 URL
    """
    config = load_config(config_file)

    multi_source_indexes = config.get("multi_source_indexes", [0])  # 默认第一个远程
    outfile = config.get("output_file", "kudog.m3u")
    generate_debug_file = config.get("generate_debug_file", False)
    default_group = config.get("default_group", "综合")

    merged = [f'#EXTM3U x-tvg-url="{epg}"']

    # 自定义频道置顶
    for ch in custom_channels:
        group_name = ch.get("group", default_group) or default_group
        merged.append(
            f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
            f'group-title="{group_name}",{ch["name"]}'
        )
        merged.append(ch["url"])

    # 按 group_order 排序输出
    group_counts = {}
    for group in group_order + [default_group]:
        for idx, (name, ch) in enumerate(channels.items()):
            if ch.get("group") == group:
                group_name = ch.get("group", default_group) or default_group
                merged.append(
                    f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
                    f'group-title="{group_name}",{ch["name"]}'
                )

                # 判断当前远程源是否在 multi_source_indexes 里
                if idx in multi_source_indexes:
                    urls = ch["urls"]  # 保留多个
                else:
                    urls = [ch["urls"][0]]  # 只取第一个

                merged.extend(urls)
                group_counts[group] = group_counts.get(group, 0) + 1

    # 写主输出文件
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(merged))
    logging.info(f"[DONE] 已生成主输出文件: {outfile}")

    # 可选：生成调试文件
    if generate_debug_file:
        debug_file = "merged.m3u"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(merged))
        logging.info(f"[DEBUG] 已生成调试文件: {debug_file}")

    # 分组统计
    logging.info("[SUMMARY] 分组统计：")
    for group, count in group_counts.items():
        logging.info(f"  {group}: {count} 个频道")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
