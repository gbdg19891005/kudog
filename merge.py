import requests, re, json

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

# ===== 读取 alias.txt =====
alias_map = {}
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

# ===== 合并源文件 =====
all_lines = []

# 远程文件
for url in remote_urls:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        all_lines += lines[1:]
        print(f"[INFO] 成功读取远程文件: {url}")
    except Exception as e:
        print(f"[WARN] 远程文件 {url} 读取失败: {e}")

# 本地文件
for fname in local_files:
    try:
        with open(fname, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            all_lines += lines[1:]
        print(f"[INFO] 成功读取本地文件: {fname}")
    except FileNotFoundError:
        print(f"[WARN] 本地文件 {fname} 不存在，跳过")

# ===== 生成合并后的 M3U =====
merged = ['#EXTM3U x-tvg-url="https://epg.catvod.com/epg.xml"']

# 自定义频道置顶
for ch in custom_channels:
    merged.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"')
    merged.append(ch["url"])

# 处理所有频道
for i in range(0, len(all_lines), 2):
    if all_lines[i].startswith("#EXTINF"):
        line = all_lines[i]
        url_line = all_lines[i+1] if i+1 < len(all_lines) else ""

        # 修正字段名
        line = line.replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")

        match = re.search(r'tvg-name="([^"]+)"', line)
        raw_name = match.group(1) if match else "未知频道"
        norm_name = normalize_name(raw_name)
        group = assign_group(norm_name)

        print(f"[DEBUG] {raw_name} → {norm_name} → {group}")

        if "group-title" in line:
            line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
        else:
            line = line + f' group-title="{group}"'
        merged.append(line)
        merged.append(url_line)

with open("kudog.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))
