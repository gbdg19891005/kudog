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

# ===== 读取 alias.txt =====
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

# ===== 读取已有 kudog.m3u，收集已存在频道和源 =====
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
                    channels[norm_name] = {"line": lines[i], "urls": set()}
                channels[norm_name]["urls"].add(url_line)
    print(f"[INFO] 已加载现有 kudog.m3u，共 {len(channels)} 个频道")
else:
    print("[INFO] 没有找到现有 kudog.m3u，将新建")

# ===== 增量合并：先本地，再远程 =====
def process_lines(lines):
    global channels
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
                channels[norm_name] = {"line": line, "urls": set([url_line])}
                print(f"[ADD] 新频道: {raw_name} → {norm_name} → {group}")
            else:
                if url_line not in channels[norm_name]["urls"]:
                    channels[norm_name]["urls"].add(url_line)
                    print(f"[ADD] 新源: {raw_name} → {norm_name}")
                else:
                    print(f"[SKIP] 已存在频道和源: {raw_name} → {norm_name}")

# 本地文件优先
for fname in local_files:
    try:
        with open(fname, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            process_lines(lines[1:])  # 跳过 #EXTM3U
        print(f"[INFO] 成功读取本地文件: {fname}")
    except FileNotFoundError:
        print(f"[WARN] 本地文件 {fname} 不存在，跳过")

# 远程文件
for url in remote_urls:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        process_lines(lines[1:])
        print(f"[INFO] 成功读取远程文件: {url}")
    except Exception as e:
        print(f"[WARN] 远程文件 {url} 读取失败: {e}")

# ===== 生成合并后的 M3U =====
merged = ['#EXTM3U x-tvg-url="https://epg.catvod.com/epg.xml"']

# 自定义频道置顶
for ch in custom_channels:
    merged.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"')
    merged.append(ch["url"])

# 输出频道和所有源
for ch in channels.values():
    merged.append(ch["line"])
    merged.extend(ch["urls"])

with open("kudog.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print(f"[DONE] 合并完成，最终频道数: {len(channels)}")
