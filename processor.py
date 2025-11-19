import logging

def process_lines(lines, alias_map, rules, blocklist,
                  keep_multiple_urls, channels,
                  primary=True, source_name="未知源",
                  default_group="综合", whitelist=None,
                  stats=None):
    """
    处理 M3U/TXT 文件的行
    :param lines: 文件行列表
    :param alias_map: 别名映射
    :param rules: 分组规则
    :param blocklist: 屏蔽列表
    :param keep_multiple_urls: 是否保留多个 URL
    :param channels: 频道字典
    :param primary: 是否主源
    :param source_name: 源名称
    :param default_group: 默认分组
    :param whitelist: 白名单频道
    :param stats: 统计信息字典
    """
    if stats is None:
        stats = {"added": 0, "appended": 0, "skipped": 0,
                 "blocked": 0, "filtered": 0, "missing_url": 0}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # 提取频道名
            try:
                name = line.split(",")[-1].strip()
            except Exception:
                name = "未知频道"

            # 白名单过滤
            if whitelist and not any(w in name for w in whitelist):
                stats["filtered"] += 1
                i += 2
                continue

            # 屏蔽列表过滤
            if any(b in name for b in blocklist):
                logging.warning(f"[BLOCKED][{source_name}] {line}")
                stats["blocked"] += 1
                i += 2
                continue

            # URL 行容错处理
            url_line = ""
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                # 如果下一行是空行、注释或另一个 #EXTINF，则认为缺失 URL
                if not url_line or url_line.startswith("#") or url_line.startswith("#EXTINF"):
                    url_line = ""

            if not url_line:
                logging.warning(f"[MISSING URL][{source_name}] {line}")
                stats["missing_url"] += 1
                i += 1
                continue

            # 别名映射
            if name in alias_map:
                name = alias_map[name]

            # 分组匹配
            group = default_group
            for g, keywords in rules.items():
                if any(k in name for k in keywords):
                    group = g
                    break

            # 添加到频道字典
            if name not in channels:
                channels[name] = {
                    "line": line,
                    "urls": [url_line],
                    "group": group
                }
                stats["added"] += 1
            else:
                if primary and keep_multiple_urls and url_line not in channels[name]["urls"]:
                    channels[name]["urls"].append(url_line)
                    stats["appended"] += 1
                else:
                    stats["skipped"] += 1

            i += 2
        else:
            i += 1
