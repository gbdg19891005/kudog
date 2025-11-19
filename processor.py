import re, logging

def normalize_name(name: str, alias_map: dict) -> str:
    """根据 alias.txt 归一化频道名"""
    for alias, main in alias_map.items():
        if alias.startswith("re:"):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():
            return main
    return name


def assign_group(name: str, rules: dict, default_group="综合") -> str:
    """根据 groups.json 的规则分组"""
    for group, keywords in rules.items():
        for kw in keywords:
            try:
                if re.search(kw, name, re.IGNORECASE):
                    return group
            except re.error:
                if kw.lower() in name.lower():
                    return group
    return default_group


def is_blocked(name: str, blocklist: list) -> bool:
    """判断频道是否在 blocklist 中"""
    clean_name = name.strip()
    if not clean_name:
        return True
    for kw in blocklist:
        if not kw:
            continue
        try:
            if re.search(re.escape(kw.strip()), clean_name, re.IGNORECASE):
                return True
        except re.error:
            if kw.strip().lower() in clean_name.lower():
                return True
    return False


def convert_txt_to_m3u(lines: list, default_group: str = "综合") -> list:
    """
    将 TXT 格式转换为 M3U 格式
    - TXT 格式: 每行 "频道名,URL"
    - 转换后: 标准 M3U 格式，首行 #EXTM3U
    - 分组使用 config.yaml 里的 default_group
    """
    new_lines = ["#EXTM3U"]
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        try:
            name, url = line.split(",", 1)
        except ValueError:
            continue
        name = name.strip()
        url = url.strip()
        new_lines.append(
            f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" group-title="{default_group}",{name}'
        )
        new_lines.append(url)
    return new_lines


def process_lines(lines: list, alias_map: dict, rules: dict, blocklist: list,
                  keep_multiple_urls: bool, channels: dict,
                  primary=False, source_name="未知源", default_group="综合",
                  whitelist: list = None):
    """
    处理 M3U 行，归并频道、分组、去重
    """
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            url_line = lines[i+1] if i+1 < len(lines) else ""

            # 缺 URL 跳过
            if not url_line or url_line.startswith("#EXTINF"):
                logging.warning(f"[MISSING URL][{source_name}] {line.strip()}")
                i += 1
                continue

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

            # 白名单过滤
            if whitelist:
                if not any(re.search(kw, norm_name, re.IGNORECASE) for kw in whitelist):
                    logging.info(f"[FILTERED][{source_name}] {raw_name} → {norm_name} 不在白名单")
                    i += 2
                    continue

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

            # 删除所有远程源自带的 group-title，再插入规则分组
            line = re.sub(r'\s*group-title="[^"]*"', '', line)
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

            if group == default_group:
                logging.warning(f"[UNCATEGORIZED][{source_name}] {raw_name} → {norm_name}")

            i += 2
        else:
            i += 1
