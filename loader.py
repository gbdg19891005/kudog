import json, os, yaml

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
    """加载 sources.json"""
    with open("sources.json", "r", encoding="utf-8") as f:
        return json.load(f)


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
