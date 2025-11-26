import re
import logging
from functools import lru_cache  # 缓存装饰器，提升重复名称处理速度
from typing import Dict, List, Tuple, Optional, Iterator

# === 预编译正则（性能优化，重复使用不重新编译） ===
EXTINF_PATTERN = re.compile(r'#EXTINF[:\-]?\d+.*?(?:tvg-name"?="?([^",]+)|(?:,)([^,]+?)(?:$|,))', re.IGNORECASE)
TVGID_PATTERN = re.compile(r'tvg-id"?="?([^",]+)', re.IGNORECASE)
GROUP_PATTERN = re.compile(r'group-title="?([^",]+)', re.IGNORECASE)

@lru_cache(maxsize=1024)  # 缓存最近1024个名称匹配结果
def normalize_name(name: str, aliasmap: Dict[str, str]) -> str:
    """名称规范化：别名→主名，支持正则匹配
    例：'CCTV1 HD' → 'CCTV-1'（alias.txt配置）
    """
    for alias, main in aliasmap.items():
        if alias.startswith('re:'):  # 正则匹配
            if re.search(alias[3:], name, re.IGNORECASE):
                return main
        elif alias.lower() == name.lower():  # 精确匹配（忽略大小写）
            return main
    return name  # 无匹配返回原名

def assign_group(name: str, rules: Dict[str, List[str]], default_group: str) -> str:
    """根据groups.json规则分配分组
    优先级：第一个匹配的规则组 → 默认组'未分类'
    """
    for group, keywords in rules.items():  # 遍历所有分组规则
        for kw in keywords:  # 每个组可能多个关键词
            try:
                if re.search(kw, name, re.IGNORECASE):  # 正则匹配
                    return group
            except re.error:  # 正则语法错误降级为字符串匹配
                if kw.lower() in name.lower():
                    return group
    return default_group

def is_blocked(name: str, blocklist: List[str]) -> bool:
    """检查频道是否在黑名单，包含即屏蔽"""
    clean_name = name.strip()
    if not clean_name:
        return True  # 空名称直接屏蔽
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
    """TXT格式转标准M3U：名,URL → #EXTINF+URL"""
    new_lines = ['#EXTM3U']
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        try:
            name, url = line.split(',', 1)  # 按第一个逗号分割
            name, url = name.strip(), url.strip()
            # 生成标准EXTINF行
            new_lines.append(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" group-title="{default_group}",{name}')
            new_lines.append(url)
        except ValueError:  # 分割失败跳过
            continue
    return new_lines

def process_channel_pair(line: str, url_line: str, aliasmap: Dict[str, str], 
                        rules: Dict[str, List[str]], blocklist: List[str], 
                        default_group: str, whitelist: Optional[List[str]] = None,
                        source_name: str = "", primary: bool = False) -> Optional[Tuple[str, str, List[str], str]]:
    """处理单个EXTINF+URL对，返回处理结果或None（过滤掉）"""
    # 1. 验证URL有效性
    if not url_line or url_line.startswith('#EXTINF'):
        logging.warning(f"⚠ MISSING URL {source_name}: {line.strip()}")
        return None
    
    # 2. 标准化旧标签名
    line = line.replace('svg-name', 'tvg-name').replace('svg-id', 'tvg-id')
    
    # 3. 提取原始频道名（多种格式兼容）
    m = EXTINF_PATTERN.search(line)
    raw_name = m.group(1).strip() if m and m.group(1) else None
    if not raw_name:
        parts = line.split(',', 1)
        raw_name = parts[1].strip() if len(parts) > 1 else ''
    m2 = TVGID_PATTERN.search(line)
    raw_name = m2.group(1).strip() if m2 and not raw_name else raw_name
    
    # 4. 名称规范化
    norm_name = normalize_name(raw_name, aliasmap)
    
    # 5. 白名单过滤（指定源只取包含频道）
    if whitelist and not any(re.search(kw, norm_name, re.IGNORECASE) for kw in whitelist):
        logging.info(f"⏭ FILTERED {source_name}: {raw_name} → {norm_name}")
        return None
    
    # 6. 黑名单过滤
    if is_blocked(norm_name, blocklist):
        logging.info(f"🚫 BLOCKED {source_name}: {raw_name} → {norm_name}")
        return None
    
    # 7. 分配分组
    group = assign_group(norm_name, rules, default_group)
    
    # 8. 强制标准化标签
    if 'tvg-id' not in line:
        line = re.sub(r'tvg-name"?="?([^",]+)', f'tvg-id="{norm_name}" tvg-name="\\g<1>"', line)
    
    # 9. 更新group-title
    line = re.sub(r'group-title="?([^",]+)', '', line)  # 清除旧分组
    if ',' in line:
        parts = line.split(',', 1)
        line = f"{parts[0]}, group-title=\"{group}\", {parts[1]}"
    else:
        line = f"{line}, group-title=\"{group}\""
    
    return norm_name, line, [url_line], group  # 返回规范化结果

def process_lines(lines: List[str], aliasmap: Dict[str, str], rules: Dict[str, List[str]], 
                 blocklist: List[str], keep_multiple_urls: bool, channels: Dict[str, Any],
                 primary: bool = False, source_name: str = "", default_group: str = "",
                 whitelist: Optional[List[str]] = None) -> None:
    """批量处理M3U行，每2行(EXTINF+URL)为一组"""
    i = 0
    processed = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):  # 找到频道行
            url_line = lines[i+1].strip() if i+1 < len(lines) else ''
            result = process_channel_pair(line, url_line, aliasmap, rules, blocklist, 
                                        default_group, whitelist, source_name, primary)
            if result:  # 有效频道
                norm_name, proc_line, urls, group = result
                if norm_name not in channels:  # 新频道
                    channels[norm_name] = {'line': proc_line, 'urls': urls, 'group': group}
                    logging.debug(f"➕ ADD {source_name}: {norm_name} [{group}]")
                elif primary and urls[0] not in channels[norm_name]['urls']:  # 主源优先
                    if keep_multiple_urls:
                        channels[norm_name]['urls'].extend(urls)
                        logging.debug(f"🔗 APPEND URL to {norm_name}")
                    else:
                        logging.debug(f"⏭ SKIP duplicate URL for {norm_name}")
                else:  # 次源重复，跳过
                    logging.debug(f"⏭ SKIP {source_name}: {norm_name} (exists)")
                
                if group == default_group:
                    logging.warning(f"⚠ UNCATEGORIZED: {norm_name}")
                processed += 1
            i += 2  # 跳过EXTINF+URL两行
        else:
            i += 1  # 跳过注释/空行
    logging.info(f"📈 Processed {processed} channels from {source_name}")
