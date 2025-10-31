import requests, re, json, os

# ===== 读取 sources.json =====
with open("sources.json", "r", encoding="utf-8") as f:
    sources = json.load(f)

remote_urls = sources.get("remote_urls", [])
local_files = sources.get("local_files", [])

# ===== 读取 groups.json =====
with open("groups.json", "r", encoding="utf-8") as f:
    config = json.load(f)

rules = config["rules"]
custom_channels = config["custom_channels"]
blocklist = config.get("blocklist", [])
group_order = list(rules.keys())

# ===== alias.txt =====
alias_map = {}
if os.path.exists("alias.txt"):
    with open("alias.txt", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.strip().split(",")
            main = parts[0]
            for alias in parts[1:]:
                alias_map[alias] = main

def normalize_name(name: str) -> str:
    for alias, main in alias_map.items():
        if alias.startswith("re:"):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():
            return main
    return name

def assign_group(name: str) -> str:
    for group, keywords in rules.items():
        for kw in keywords:
            try:
                if re.search(kw, name, re.IGNORECASE):
                    return group
            except re.error:
                if kw.lower() in name.lower():
                    return group
    return "综合"

def is_blocked(name: str) -> bool:
    for kw in blocklist:
        if re.search(kw, name, re.IGNORECASE):
            return True
    return False

# ===== 已有频道和源 =====
channels = {}

if os.path.exists("kudog.m3u"):
    with open("kudog.m3u", "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
        for i in range(0, len(lines), 2):
            if lines[i].startswith("#EXTINF"):
                m = re.search(r'tvg-name="([^"]+)"', lines[i])
                if not m:
                    continue
                raw_name = m.group(1)
                norm_name = normalize_name(raw_name)
                url_line = lines[i+1] if i+1 < len(lines) else ""
                if norm_name not in channels:
                    channels[norm_name] = {"line": lines[i], "urls": set(), "group": assign_group(norm_name)}
                channels[norm_name]["urls"].add(url_line)
    print(f"[INFO] 已加载现有 kudog.m3u，共 {len(channels)} 个频道")

# ===== 增量合并 =====
def process_lines(lines, primary=False):
    for i in range(0, len(lines), 2):
        if lines[i].startswith("#EXTINF"):
            line = lines[i]
            url_line = lines[i+1] if i+1 < len(lines) else ""

            line = line.replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")
            m = re.search(r'tvg-name="([^"]+)"', line)
            raw_name = m.group(1) if m else "未知频道"
            norm_name = normalize_name(raw_name)

            if is_blocked(norm_name):
                print(f"[BLOCKED] {raw_name} → {norm_name}")
                continue

            group = assign_group(norm_name)
            if "group-title" in line:
                line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
            else:
                line = line + f' group-title="{group}"'

            if norm_name not in channels:
                channels[norm_name] = {"line": line, "urls": set([url_line]), "group": group}
                print(f"[ADD] 新频道: {raw_name} → {norm_name} → {group}")
            else:
                if primary:
                    # 主远程源：允许追加新 URL
                    if url_line not in channels[norm_name]["urls"]:
                        channels[norm_name]["urls"].add(url_line)
                        print(f"[ADD] 主源新URL: {norm_name}")
                else:
                    # 后续远程源：只补充主源没有的 URL
                    if url_line not in channels[norm_name]["urls"]:
                        channels[norm_name]["urls"].add(url_line)
                        print(f"[ADD] 新源: {raw_name} → {norm_name}")
                    else:
                        print(f"[SKIP] 已存在频道和源: {raw_name} → {norm_name}")

# ===== 本地优先 =====
for fname in local_files:
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            process_lines(lines[1:], primary=True)  # 本地也当作主源
        print(f"[INFO] 成功读取本地文件: {fname}")

# ===== 远程源 =====
is_primary = True
for url in remote_urls:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        process_lines(lines[1:], primary=is_primary)
        print(f"[INFO] 成功读取远程文件: {url}")
        is_primary = False
    except Exception as e:
        print(f"[WARN] 远程文件 {url} 读取失败: {e}")

# ===== 输出，按分组排序 =====
merged = ['#EXTM3U x-tvg-url="https://epg.catvod.com/epg.xml"']

# 自定义频道置顶
for ch in custom_channels:
    merged.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"')
    merged.append(ch["url"])

# 按 group_order 排序输出
for group in group_order + ["综合"]:
    for name, ch in channels.items():
        if ch.get("group") == group:
            merged.append(ch["line"])
            merged.extend(ch["urls"])

with open("kudog.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print(f"[DONE] 合并完成，最终频道数: {len(channels)}")
