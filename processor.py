import re
import logging
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any

EXTINF_PATTERN = re.compile(r'#EXTINF[:\-]?\d+.*?(?:tvg-name"?="?([^",]+)|(?:,)([^,]+?)(?:$|,))', re.IGNORECASE)
TVGID_PATTERN = re.compile(r'tvg-id"?="?([^",]+)', re.IGNORECASE)

@lru_cache(maxsize=1024)
def normalize_name(name: str, aliasmap: Dict[str, str]) -> str:
    for alias, main in aliasmap.items():
        if alias.startswith('re:'):
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():
            return main
    return name

def assign_group(name: str, rules: Dict[str, List[str]], default_group: str) -> str:
    for group, keywords in rules.items():
        for kw in keywords:
            try:
                if re.search(kw, name, re.IGNORECASE):
                    return group
            except re.error:
                if kw.lower() in name.lower():
                    return group
    return default_group

def is_blocked(name: str, blocklist: List[str]) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return True
    for kw in blocklist:
        if not kw:
            continue
        try:
            if re.search(re.escape(kw.strip()), clean_name, re.IGNORECASE):
                return True
        except re.error:
            if kw.strip().lower() in clean_name.lower():
                return True
    return False

def convert_txt_to_m3u(lines: List[str], default_group: str) -> List[str]:
    new_lines = ['#EXTM3U']
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        try:
            name, url = line.split(',', 1)
            name, url = name.strip(), url.strip()
            new_lines.append(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" group-title="{default_group}",{name}')
            new_lines.append(url)
        except ValueError:
            continue
    return new_lines

def process_lines(lines: List[str], aliasmap: Dict[str, str], rules: Dict[str, List[str]], 
                 blocklist: List[str], keep_multiple_urls: bool, channels: Dict[str, Any],
                 primary: bool = False, source_name: str = "", default_group: str = "",
                 whitelist: Optional[List[str]] = None) -> None:
    i = 0
    processed = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            url_line = lines[i+1].strip() if i+1 < len(lines) else ''
            if not url_line or url_line.startswith('#EXTINF'):
                logging.warning(f"MISSING URL {source_name}")
                i += 2
                continue
            
            line = line.replace('svg-name', 'tvg-name').replace('svg-id', 'tvg-id')
            
            # 提取名称
            m = EXTINF_PATTERN.search(line)
            raw_name = m.group(1).strip() if m and m.group(1) else ''
            if not raw_name:
                parts = line.split(',', 1)
                raw_name = parts[1].strip() if len(parts) > 1 else ''
            
            norm_name = normalize_name(raw_name, aliasmap)
            
            if whitelist and not any(re.search(kw, norm_name, re.IGNORECASE) for kw in whitelist if kw):
                i += 2
                continue
            
            if is_blocked(norm_name, blocklist):
                logging.info(f"BLOCKED {source_name}: {norm_name}")
                i += 2
                continue
            
            group = assign_group(norm_name, rules, default_group)
            
            if 'tvg-id' not in line:
                line = re.sub(r'tvg-name"?="?([^",]+)', f'tvg-id="{norm_name}" tvg-name="\\g<1>"', line)
            
            line = re.sub(r'group-title="?[^",]*"?', '', line)
            if ',' in line:
                parts = line.split(',', 1)
                line = f"{parts[0]},group-title=\"{group}\", {parts[1]}"
            else:
                line = f"{line},group-title=\"{group}\""
            
            if norm_name not in channels:
                channels[norm_name] = {'line': line, 'urls': [url_line], 'group': group}
                logging.debug(f"ADD {source_name}: {norm_name}")
            elif primary and url_line not in channels[norm_name]['urls']:
                if keep_multiple_urls:
                    channels[norm_name]['urls'].append(url_line)
            
            processed += 1
            i += 2
        else:
            i += 1
    logging.info(f"Processed {processed} from {source_name}")
