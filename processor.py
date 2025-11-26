import re
import logging
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any

EXTINF_PATTERN = re.compile(r'#EXTINF[:\-]?\d+.*?(?:tvg-name"?="?([^",]+)|(?:,)([^,]+?)(?:$|,))', re.IGNORECASE)
TVGID_PATTERN = re.compile(r'tvg-id"?="?([^",]+)', re.IGNORECASE)

# ✅ 修复：移除lru_cache，避免dict缓存问题
def normalize_name(name: str, aliasmap: Dict[str, str]) -> str:
    """名称规范化：别名→主名，支持正则匹配"""
    if not isinstance(aliasmap, dict):
        return name
    for alias, main in aliasmap.items():
        if isinstance(alias, str) and alias.startswith('re:'):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif isinstance(alias, str) and alias.lower() == name.lower():
            return main
    return name

def assign_group(name: str, rules: Dict[str, List[str]], default_group: str) -> str:
    """根据groups.json规则分配分组"""
    if not isinstance(rules, dict):
        return default_group
    for group, keywords in rules.items():
        if not isinstance(keywords, list):
            continue
        for kw in keywords:
            if isinstance(kw, str):
                try:
                    if re.search(kw, name, re.IGNORECASE):
                        return group
                except re.error:
                    if kw.lower() in name.lower():
                        return group
    return default_group

def is_blocked(name: str, blocklist: List[str]) -> bool:
    """检查频道是否在黑名单"""
    clean_name = name.strip()
    if not clean_name or not isinstance(blocklist, list):
        return True
    for kw in blocklist:
        if isinstance(kw, str) and kw.strip():
            try:
                if re.search(re.escape(kw.strip()), clean_name, re.IGNORECASE):
                    return True
            except re.error:
                if kw.strip().lower() in clean_name.lower():
                    return True
    return False

def convert_txt_to_m3u(lines: List[str], default_group: str) -> List[str]:
    """TXT格式转M3U"""
    new_lines = ['#EXTM3U']
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        try:
            parts = line.split(',', 1)
            if len(parts) < 2:
                continue
            name, url = parts[0].strip(), parts[1].strip()
            new_lines.append(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" group-title="{default_group}",{name}')
            new_lines.append(url)
        except Exception:
            continue
    return new_lines

def process_channel_pair(line: str, url_line: str, aliasmap: Dict[str, str], 
                        rules: Dict[str, List[str]], blocklist: List[str], 
                        default_group: str, whitelist: Optional[List[str]] = None,
                        source_name: str = "", primary: bool = False) -> Optional[Tuple[str, str, List[str], str]]:
    """处理单个频道对（独立函数，避免缓存问题）"""
    if not url_line or url_line.startswith('#EXTINF'):
        logging.warning(f"⚠ MISSING URL {source_name}")
        return None
    
    line = line.replace('svg-name', 'tvg-name').replace('svg-id', 'tvg-id')
    
    # 提取名称
    m = EXTINF_PATTERN.search(line)
    raw_name = m.group(1).strip() if m and m.group(1) else ''
    if not raw_name:
        parts = line.split(',', 1)
        raw_name = parts[1].strip() if len(parts) > 1 else ''
    
    norm_name = normalize_name(raw_name, aliasmap)
    
    # 白名单过滤
    if whitelist and isinstance(whitelist, list):
        if not any(re.search(kw, norm_name, re.IGNORECASE) for kw in whitelist if isinstance(kw, str)):
            return None
    
    # 黑名单过滤
    if is_blocked(norm_name, blocklist):
        logging.debug(f"🚫 BLOCKED {source_name}: {norm_name}")
        return None
    
    # 分配分组
    group = assign_group(norm_name, rules, default_group)
    
    # 标准化标签
    if 'tvg-id' not in line:
        line = re.sub(r'tvg-name"?="?([^",]+)', f'tvg-id="{norm_name}" tvg-name="\\g<1>"', line)
    
    # 更新group-title
    line = re.sub(r'group-title="?[^",]*"?', '', line)
    if ',' in line:
        parts = line.split(',', 1)
        line = f"{parts[0]},group-title=\"{group}\", {parts[1]}"
    else:
        line = f"{line},group-title=\"{group}\""
    
    return norm_name, line, [url_line], group

def process_lines(lines: List[str], aliasmap: Dict[str, str], rules: Dict[str, List[str]], 
                 blocklist: List[str], keep_multiple_urls: bool, channels: Dict[str, Any],
                 primary: bool = False, source_name: str = "", default_group: str = "",
                 whitelist: Optional[List[str]] = None) -> None:
    """批量处理M3U行（修复版）"""
    i = 0
    processed = 0
    skipped = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            url_line = lines[i+1].strip() if i+1 < len(lines) else ''
            result = process_channel_pair(line, url_line, aliasmap, rules, blocklist,
                                        default_group, whitelist, source_name, primary)
            
            if result:
                norm_name, proc_line, urls, group = result
                if norm_name not in channels:
                    channels[norm_name] = {'line': proc_line, 'urls': urls, 'group': group}
                    logging.debug(f"➕ ADD {source_name}: {norm_name} [{group}]")
                elif primary and urls[0] not in channels[norm_name]['urls']:
                    if keep_multiple_urls:
                        channels[norm_name]['urls'].extend(urls)
                        logging.debug(f"🔗 ADD URL to {norm_name}")
                    else:
                        logging.debug(f"⏭ SKIP duplicate URL for {norm_name}")
                processed += 1
            else:
                skipped += 1
            i += 2
        else:
            i += 1
    
    logging.info(f"📊 {source_name}: {processed} added, {skipped} skipped")
