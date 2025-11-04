import logging
import yaml
import os

def load_config(config_file="config.yaml"):
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def export_m3u(channels, custom_channels, group_order, epg,
               keep_multiple_urls=None,
               outfile=None, generate_debug_file=None, default_group=None,
               config_file="config.yaml"):
    """
    导出 M3U 文件
    兼容旧参数调用，同时支持 config.yaml 配置
    """
    config = load_config(config_file)

    # 新增的多源控制
    multi_source_indexes = config.get("multi_source_indexes", [0])

    # 兼容旧参数：如果 merge.py 传了，就覆盖配置文件里的
    outfile = outfile or config.get("output_file", "kudog.m3u")
    generate_debug_file = generate_debug_file if generate_debug_file is not None else config.get("generate_debug_file", False)
    default_group = default_group or config.get("default_group", "综合")

    # 如果还在用 keep_multiple_urls，就转成 multi_source_indexes
    if keep_multiple_urls is not None:
        if keep_multiple_urls:
            # 等价于所有远程都保留多个
            multi_source_indexes = list(range(len(channels)))
        else:
            # 等价于所有远程只取第一个
            multi_source_indexes = []

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
