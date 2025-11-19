import json, os, yaml, logging

def load_config():
    """加载 config.yaml 配置"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 设置默认值，避免缺字段时报错
    defaults = {
        "ua": "Mozilla/5.0",
        "referrer": "",
        "epg": "https://epg.catvod.com/epg.xml",
        "timeout": 10,
        "keep_multiple_urls": True,
        "log_level": "INFO",
        "output_file": "kudog.m3u",
        "generate_debug_file": False,
        "default_group": "综合",
        "force_logo": False,
        "force_tvg_id": False,
    }

    for k, v in defaults.items():
        config.setdefault(k, v)

    return config


def load_sources():
    """加载 sources.json 并校验字段"""
    with open("sources.json", "r", encoding="utf-8") as f:
        sources = json.load(f)

    # 校验 remote_urls
    remote_urls = sources.get("remote_urls", [])
    validated_urls = []
    for src in remote_urls:
        if isinstance(src, str):
            # 字符串形式，默认 primary=True
            validated_urls.append({"url": src, "primary": True, "include_channels": []})
        elif isinstance(src, dict):
            url = src.get("url")
            if not url:
                logging.warning("[WARN] sources.json 中存在缺少 url 的远程源，已跳过")
                continue
            validated_urls.append({
                "url": url,
                "primary": bool(src.get("primary", False)),
                "include_channels": src.get("include_channels", [])
            })
        else:
            logging.warning(f"[WARN] sources.json 中存在无效的远程源: {src}")

    sources["remote_urls"] = validated_urls

    # 校验 local_files
    local_files = sources.get("local_files", [])
    validated_files = []
    for fname in local_files:
        if isinstance(fname, str):
            validated_files.append(fname)
        else:
            logging.warning(f"[WARN] sources.json 中存在无效的本地文件: {fname}")
    sources["local_files"] = validated_files

    return sources


def load_groups():
    """加载 groups.json"""
    with open("groups.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_alias():
    """加载 alias.txt，支持正则别名"""
    alias_map = {}
    if os.path.exists("alias.txt"):
        with open("alias.txt", "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",") if p.strip()]
                main = parts[0]
                for alias in parts:
                    alias_map[alias] = main
    return alias_map
