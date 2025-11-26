import json
import os
import yaml
import logging
from typing import Dict, Any, Optional

def loadconfig() -> Dict[str, Any]:
    """加载config.yaml，返回带默认值的配置字典
    作用：提供所有运行参数，文件不存在使用内置默认值
    """
    config_path = 'config.yaml'  # 固定配置文件路径
    defaults = {  # 内置默认配置，确保程序总是能运行
        'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'referrer': '', 'epg': 'https://epg.catvod.com/epg.xml',
        'timeout': 15, 'keepmultipleurls': True, 'loglevel': 'INFO',
        'outputfile': 'kudog.m3u', 'generatedebugfile': False, 'defaultgroup': '未分类',
        'forcelogo': False, 'forcetvgid': False, 'max_retries': 3, 'cache_sources': True
    }
    
    config = defaults.copy()  # 先复制默认值
    if os.path.exists(config_path):  # 检查文件存在
        try:
            with open(config_path, 'r', encoding='utf-8') as f:  # UTF-8编码支持中文
                file_config = yaml.safe_load(f) or {}  # 安全解析YAML
                config.update(file_config)  # 覆盖默认值
                logging.info("✓ Config loaded: config.yaml")
        except (yaml.YAMLError, OSError) as e:
            logging.warning(f"⚠ Config failed ({e}), using defaults")
    else:
        logging.info("ℹ config.yaml not found, using defaults")
    return config

def loadsources() -> Dict[str, Any]:
    """加载sources.json，返回{'local_files':[], 'remote_urls':[]}"""
    if os.path.exists('sources.json'):
        with open('sources.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    logging.warning("⚠ sources.json not found")
    return {'local_files': [], 'remote_urls': []}

def loadgroups() -> Dict[str, Any]:
    """加载groups.json，返回{'rules':{}, 'customchannels':[], 'blocklist':[]}"""
    if os.path.exists('groups.json'):
        with open('groups.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    logging.warning("⚠ groups.json not found")
    return {'rules': {}, 'customchannels': [], 'blocklist': []}

def loadalias() -> Dict[str, str]:
    """加载alias.txt，返回{别名:主名}字典
    格式：主名,别名1,别名2,re:正则别名
    """
    aliasmap = {}
    if os.path.exists('alias.txt'):
        try:
            with open('alias.txt', 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):  # 带行号便于调试
                    line = line.strip()
                    if not line or line.startswith('#'):  # 跳过空行和注释
                        continue
                    parts = [p.strip() for p in line.split(',')]  # 按逗号分割
                    if len(parts) >= 2:
                        main = parts[0]  # 第一个为主名
                        for alias in parts[1:]:  # 其余为别名
                            aliasmap[alias] = main
            logging.info(f"✓ Loaded {len(aliasmap)} aliases")
        except OSError as e:
            logging.warning(f"⚠ Alias file failed: {e}")
    return aliasmap
