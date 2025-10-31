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

# ===== 全量重建：从空开始 =====
channels = {}

# ===== TXT 转换为 M3U =====
def convert_txt_to_m3u(lines):
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
        new_lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="综合",{name}')
        new_lines.append(url)
    return new_lines

# ===== 处理函数（修正版） =====
def process_lines(lines, primary=False):
    for i in range(0, len(lines), 2):
        if lines[i].startswith("#EXTINF"):
            line = lines[i]
            url_line = lines[i+1] if i+1 < len(lines) else ""

            # 修复错误字段
            line = line.replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")

            # 提取频道名：优先 tvg-name，没有就取逗号后的名字
            m = re.search(r'tvg-name="([^"]+)"', line)
            if m:
                raw_name = m.group(1).strip()
            else:
                parts = line.split(",", 1)
                raw_name = parts[1].strip() if len(parts) > 1 else "未知频道"

            # 归并别名
            norm_name = normalize_name(raw_name)

            # 屏蔽名单
            if is_blocked(norm_name):
                print(f"[BLOCKED] {raw_name} → {norm_name}")
                continue

            # 分组
            group = assign_group(norm_name)
            if "group-title" in line:
                line = re.sub(r'group-title=".*?"', f'group-title="{group}"', line)
            else:
                line = line + f' group-title="{group}"'

            # 调试输出
            action = None
            if norm_name not in channels:
                channels[norm_name] = {"line": line, "urls": set([url_line]), "group": group}
                action = "ADD"
                print(f"[ADD] 新频道: {raw_name} → {norm_name} → {group}")
            else:
                if primary:
                    if url_line and url_line not in channels[norm_name]["urls"]:
                        channels[norm_name]["urls"].add(url_line)
                        action = "APPEND"
                        print(f"[APPEND] 主源新URL: {norm_name}")
                else:
                    action = "SKIP"
                    print(f"[SKIP] 已存在频道: {raw_name} → {norm_name}")

            print(f"[DEBUG] 原始: {raw_name} → 归并: {norm_name} → 分组: {group} → 动作: {action}")

# ===== 本地优先（当作主源） =====
for fname in local_files:
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            if not lines[0].startswith("#EXTM3U"):
                lines = convert_txt_to_m3u(lines)
            process_lines(lines[1:], primary=True)
        print(f"[INFO] 成功读取本地文件: {fname}")

# ===== 远程源 =====
is_primary = True
for url in remote_urls:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        if not lines[0].startswith("#EXTM3U"):
            lines = convert_txt_to_m3u(lines)
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

print(f"[DONE] 全量重建完成，最终频道数: {len(channels)}")
