import logging

def process_lines(lines, alias_map, rules, blocklist,
                  keep_multiple_urls, channels,
                  primary=True, source_name="未知源",
                  default_group="综合", whitelist=None,
                  stats=None):
    if stats is None:
        stats = {"added": 0, "appended": 0, "skipped": 0,
                 "blocked": 0, "filtered": 0, "missing_url": 0}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            try:
                name = line.split(",")[-1].strip()
            except Exception:
                name = "未知频道"

            if whitelist and not any(w in name for w in whitelist):
                stats["filtered"] += 1
                i += 2
                continue

            if any(b in name for b in blocklist):
                logging.warning(f"[BLOCKED][{source_name}] {line}")
                stats["blocked"] += 1
                i += 2
                continue

            url_line = ""
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                if not url_line or url_line.startswith("#") or url_line.startswith("#EXTINF"):
                    url_line = ""

            if not url_line:
                logging.warning(f"[MISSING URL][{source_name}] {line}")
                stats["missing_url"] += 1
                i += 1
                continue

            if name in alias_map:
                name = alias_map[name]

            group = default_group
            for g, keywords in rules.items():
                if any(k in name for k in keywords):
                    group = g
                    break

            if name not in channels:
                # 新频道：保留原始 line 和分组
                channels[name] = {"line": line, "urls": [url_line], "group": group}
                stats["added"] += 1
            else:
                # 已存在频道：只追加 URL，不改 line/group
                if keep_multiple_urls and url_line not in channels[name]["urls"]:
                    channels[name]["urls"].append(url_line)
                    stats["appended"] += 1
                else:
                    stats["skipped"] += 1
            i += 2
        else:
            i += 1

def convert_txt_to_m3u(lines, default_group="综合"):
    m3u_lines = ["#EXTM3U"]
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            parts = line.split(",", 1)
        else:
            parts = line.split(None, 1)
        if len(parts) == 2:
            name, url = parts
            m3u_lines.append(f'#EXTINF:-1 group-title="{default_group}",{name.strip()}')
            m3u_lines.append(url.strip())
    return m3u_lines
