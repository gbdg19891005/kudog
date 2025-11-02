import re, logging

def normalize_name(name, alias_map):
    for alias, main in alias_map.items():
        if alias.startswith("re:"):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():
            return main
    return name

def assign_group(name, rules):
    for group, keywords in rules.items():
        for kw in keywords:
            try:
                if re.search(kw, name, re.IGNORECASE):
                    return group
            except re.error:
                if kw.lower() in name.lower():
                    return group
    return "综合"

def is_blocked(name, blocklist):
    for kw in blocklist:
        if re.search(kw, name, re.IGNORECASE):
            return True
    return False

def process_lines(lines, alias_map, rules, blocklist, keep_multiple_urls, channels, primary=False, source_name="未知源"):
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            url_line = lines[i+1] if i+1 < len(lines) else ""
            line = lines[i].replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")

            m = re.search(r'tvg-name="([^"]+)"', line)
            raw_name = m.group(1).strip() if m else line.split(",", 1)[-1].strip()
            norm_name = normalize_name(raw_name, alias_map)

            if is_blocked(norm_name, blocklist):
                logging.info(f"[BLOCKED][{source_name}] {raw_name} → {norm_name}")
                i += 2
                continue

            group = assign_group(norm_name, rules)
            if "group-title" in line:
                line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
            else:
                line = line + f' group-title="{group}"'

            if norm_name not in channels:
                channels[norm_name] = {"line": line, "urls": [url_line], "group": group}
            else:
                if primary and url_line and url_line not in channels[norm_name]["urls"]:
                    if keep_multiple_urls:
                        channels[norm_name]["urls"].append(url_line)

            i += 2
        else:
            i += 1
