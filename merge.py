import requests, re, json

# 读取分组配置
with open("groups.json", "r", encoding="utf-8") as f:
    config = json.load(f)

rules = config["rules"]
custom_channels = config["custom_channels"]

# 读取 alias.txt
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
    """统一频道别名"""
    for alias, main in alias_map.items():
        if alias.startswith("re:"):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():
            return main
    return name

def assign_group(name: str) -> str:
    """根据规则分组"""
    for group, keywords in rules.items():
        for kw in keywords:
            if re.search(kw, name, re.IGNORECASE):
                return group
    return "综合"

# 拉取远程 interface.txt
url = "https://raw.githubusercontent.com/develop202/migu_video/main/interface.txt"
resp = requests.get(url)
github_content = resp.text.splitlines()

# 读取本地 kudog.txt
with open("kudog.txt", "r", encoding="utf-8") as f:
    kudog_content = f.read().splitlines()

merged = ['#EXTM3U x-tvg-url="https://epg.catvod.com/epg.xml"']

# ✅ 先写自定义频道（置顶）
for ch in custom_channels:
    merged.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"')
    merged.append(ch["url"])

# 再写合并后的其它频道
all_lines = github_content[1:] + kudog_content[1:]
for i in range(0, len(all_lines), 2):
    if all_lines[i].startswith("#EXTINF"):
        line = all_lines[i]
        url_line = all_lines[i+1] if i+1 < len(all_lines) else ""
        match = re.search(r'tvg-name="([^"]+)"', line)
        raw_name = match.group(1) if match else "未知频道"
        norm_name = normalize_name(raw_name)   # 先统一别名
        group = assign_group(norm_name)        # 再分组

        # 🔎 调试输出
        print(f"[DEBUG] {raw_name} → {norm_name} → {group}")

        if "group-title" in line:
            line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
        else:
            line = line + f' group-title="{group}"'
        merged.append(line)
        merged.append(url_line)

# 保存为 kudog.m3u
with open("kudog.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))
