def process_lines(lines: list, alias_map: dict, rules: dict, blocklist: list,
                  keep_multiple_urls: bool, channels: dict,
                  primary=False, source_name="未知源", default_group="🗑️综合"):
    """
    处理 M3U 行，归并频道、分组、去重
    """
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            url_line = lines[i+1] if i+1 < len(lines) else ""

            # 修复可能的错误字段
            line = line.replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")

            # 提取频道名
            m = re.search(r'tvg-name="([^"]+)"', line)
            if m:
                raw_name = m.group(1).strip()
            else:
                parts = line.split(",", 1)
                if len(parts) > 1 and parts[1].strip():
                    raw_name = parts[1].strip()
                else:
                    m2 = re.search(r'tvg-id="([^"]+)"', line)
                    raw_name = m2.group(1).strip() if m2 else "未知频道"

            # 别名归并
            norm_name = normalize_name(raw_name, alias_map)

            # 屏蔽检查
            if is_blocked(norm_name, blocklist):
                logging.info(f"[BLOCKED][{source_name}] {raw_name} → {norm_name}")
                i += 2
                continue

            # 分组
            group = assign_group(norm_name, rules, default_group)

            # 强制补全 tvg-id
            if 'tvg-id="' not in line:
                line = re.sub(r'tvg-name="([^"]+)"',
                              f'tvg-id="{norm_name}" tvg-name="\\1"', line)

            # 强制统一 group-title 在属性区
            if "group-title" in line:
                line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
            else:
                if "," in line:
                    parts = line.split(",", 1)
                    line = parts[0] + f' group-title="{group}",' + parts[1]
                else:
                    line = line + f' group-title="{group}"'

            # 归并逻辑
            if norm_name not in channels:
                channels[norm_name] = {"line": line, "urls": [url_line], "group": group}
                logging.debug(f"[ADD][{source_name}] {raw_name} → {norm_name} → {group}")
            else:
                if primary and url_line and url_line not in channels[norm_name]["urls"]:
                    if keep_multiple_urls:
                        channels[norm_name]["urls"].append(url_line)
                        logging.debug(f"[APPEND][{source_name}] {raw_name} → {norm_name} 新增URL")
                    else:
                        logging.debug(f"[IGNORE][{source_name}] {raw_name} → {norm_name} 保留首个URL")
                else:
                    logging.debug(f"[SKIP][{source_name}] {raw_name} → {norm_name}")

            i += 2
        else:
            i += 1
