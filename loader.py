import json
import os
import yaml
import logging
from typing import Dict, List


def validate_config(config: dict) -> bool:
    """验证配置完整性"""
    required_fields = ["ua", "epg", "timeout", "output_file"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"配置缺少必填字段: {field}")
    
    if config["timeout"] <= 0:
        raise ValueError("timeout 必须大于 0")
    
    if not config["output_file"].endswith('.m3u'):
        logging.warning("output_file 建议以 .m3u 结尾")
    
    # 验证并发数
    if "max_concurrent_downloads" in config:
        if config["max_concurrent_downloads"] < 1:
            raise ValueError("max_concurrent_downloads 必须大于 0")
        if config["max_concurrent_downloads"] > 20:
            logging.warning("max_concurrent_downloads 过大可能导致网络拥堵，建议设置为 5-10")
    
    return True


def load_config() -> dict:
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
        "max_concurrent_downloads": 5,  # 新增：最大并发下载数
    }

    for k, v in defaults.items():
        config.setdefault(k, v)

    # 验证配置
    validate_config(config)
    
    return config


def load_sources() -> dict:
    """加载 sources.json"""
    with open("sources.json", "r", encoding="utf-8") as f:
        sources = json.load(f)
    
    # 确保必要字段存在
    sources.setdefault("local_files", [])
    sources.setdefault("remote_urls", [])
    
    return sources


def load_groups() -> dict:
    """加载 groups.json"""
    with open("groups.json", "r", encoding="utf-8") as f:
        groups = json.load(f)
    
    # 确保必要字段存在
    groups.setdefault("rules", {})
    groups.setdefault("custom_channels", [])
    groups.setdefault("blocklist", [])
    
    return groups


def load_alias() -> Dict[str, str]:
    """加载 alias.txt，支持正则别名"""
    alias_map = {}
    if os.path.exists("alias.txt"):
        with open("alias.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) < 2:
                    continue
                main = parts[0]
                for alias in parts:
                    alias_map[alias] = main
    return alias_map
