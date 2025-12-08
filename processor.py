import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs


def normalize_url(url: str) -> str:
    """
    标准化 URL，去除时间戳等无关参数
    用于智能去重判断
    """
    try:
        parsed = urlparse(url)
        
        # 去除常见的时间戳和跟踪参数
        ignore_params = [
            'timestamp', 'token', 'sign', '_', 't', 'random', 
            'time', 'ts', 'v', 'version', 'cache'
        ]
        
        query_params = parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() 
                          if k.lower() not in ignore_params}
        
        # 重建基础URL（不含动态参数）
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # 如果有静态参数，追加
        if filtered_params:
            from urllib.parse import urlencode
            query_string = urlencode(filtered_params, doseq=True)
            base_url = f"{base_url}?{query_string}"
        
        return base_url.lower()  # 统一小写比较
    except:
        return url.lower()


def are_urls_similar(url1: str, url2: str) -> bool:
    """
    判断两个 URL 是否本质相同（智能去重）
    :param url1: URL 1
    :param url2: URL 2
    :return: True 表示相似（应去重）
    """
    # 完全相同
    if url1 == url2:
        return True
    
    # 标准化后相同
    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    
    return norm1 == norm2


def normalize_name(name: str, alias_map: Dict[str, str]) -> str:
    """根据 alias.txt 归一化频道名"""
    for alias, main in alias_map.items():
        if alias.startswith("re:"):
            try:
                if re.search(alias[3:], name, re.IGNORECASE):
                    return main
            except re.error:
                logging.warning(f"[WARN] 正则表达式错误: {alias}")
        elif alias.lower() == name.lower():
            return main
    return name


def assign_group(name: str, rules: Dict[str, List[str]], default_group: str = "综合") -> str:
    """根据 groups.json 的规则分组"""
    for group, keywords in rules.items():
        for kw in keywords:
            try:
                if re.search(kw, name, re.IGNORECASE):
                    return group
            except re.error:
                # 回退到字符串匹配
                if kw.lower() in name.lower():
                    return group
    return default_group


def is_blocked(name: str, blocklist: List[str]) -> bool:
    """判断频道是否在 blocklist 中"""
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


def convert_txt_to_m3u(lines: List[str], default_group: str = "综合") -> List[str]:
    """
    将 TXT 格式转换为 M3U 格式
    - TXT 格式: 每行 "频道名,URL"
    - 转换后: 标准 M3U 格式，首行 #EXTM3U
    - 分组使用 config.yaml 里的 default_group
    """
    new_lines = ["#EXTM3U"]
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            name, url = line.split(",", 1)
        except ValueError:
            continue
        name = name.strip()
        url = url.strip()
        if name and url:
            new_lines.append(
                f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" group-title="{default_group}",{name}'
            )
            new_lines.append(url)
    return new_lines


def process_lines(lines: List[str], alias_map: Dict[str, str], 
                  rules: Dict[str, List[str]], blocklist: List[str],
                  keep_multiple_urls: bool, channels: Dict[str, dict],
                  primary: bool = False, source_name: str = "未知源", 
                  default_group: str = "综合",
                  whitelist: Optional[List[str]] = None) -> None:
    """
    处理 M3U 行，归并频道、分组、去重
    """
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("#EXTINF"):
            # 安全获取 URL 行
            url_line = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith("#"):
                    url_line = next_line

            # 缺 URL 跳过
            if not url_line:
                logging.warning(f"[MISSING URL][{source_name}] {line}")
                i += 1
                continue

            # 修复可能的错误字段
            line = line.replace("svg-name", "tvg-name").replace("svg-id", "tvg-id")

            # 提取频道名
            m = re.search(r'tvg-name="([^"]+)"', line)
            if m:
                raw_name = m.group(1).strip()
            else:
                parts = line.split(",", 1)
                if len(parts) > 1 and parts[1].strip():
                    raw_name = parts[1].strip()
                else:
                    m2 = re.search(r'tvg-id="([^"]+)"', line)
                    raw_name = m2.group(1).strip() if m2 else "未知频道"

            # 别名归并
            norm_name = normalize_name(raw_name, alias_map)

            # 白名单过滤
            if whitelist:
                matched = False
                for kw in whitelist:
                    try:
                        if re.search(kw, norm_name, re.IGNORECASE):
                            matched = True
                            break
                    except re.error:
                        if kw.lower() in norm_name.lower():
                            matched = True
                            break
                
                if not matched:
                    logging.debug(f"[FILTERED][{source_name}] {raw_name} → {norm_name} 不在白名单")
                    i += 2
                    continue

            # 屏蔽检查
            if is_blocked(norm_name, blocklist):
                logging.debug(f"[BLOCKED][{source_name}] {raw_name} → {norm_name}")
                i += 2
                continue

            # 分组
            group = assign_group(norm_name, rules, default_group)

            # 强制补全 tvg-id
            if 'tvg-id="' not in line:
                line = re.sub(r'tvg-name="([^"]+)"',
                              f'tvg-id="{norm_name}" tvg-name="\\1"', line)
                # 如果没有 tvg-name，添加 tvg-id
                if 'tvg-name="' not in line:
                    line = re.sub(r'#EXTINF:-1\s+',
                                  f'#EXTINF:-1 tvg-id="{norm_name}" tvg-name="{norm_name}" ',
                                  line)

            # 删除所有远程源自带的 group-title，再插入规则分组
            line = re.sub(r'\s*group-title="[^"]*"', '', line)
            if "," in line:
                parts = line.split(",", 1)
                line = parts[0] + f' group-title="{group}",' + parts[1]
            else:
                line = line + f' group-title="{group}"'

            # 归并逻辑（添加智能去重）
            if norm_name not in channels:
                channels[norm_name] = {"line": line, "urls": [url_line], "group": group}
                logging.debug(f"[ADD][{source_name}] {raw_name} → {norm_name} → {group}")
            else:
                if primary and url_line:
                    # 智能去重：检查URL是否已存在
                    is_duplicate = any(are_urls_similar(url_line, existing) 
                                      for existing in channels[norm_name]["urls"])
                    
                    if not is_duplicate:
                        if keep_multiple_urls:
                            channels[norm_name]["urls"].append(url_line)
                            logging.debug(f"[APPEND][{source_name}] {raw_name} → {norm_name} 新增URL")
                        else:
                            logging.debug(f"[IGNORE][{source_name}] {raw_name} → {norm_name} 保留首个URL")
                    else:
                        logging.debug(f"[DUPLICATE][{source_name}] {raw_name} → {norm_name} URL相似，已跳过")
                else:
                    logging.debug(f"[SKIP][{source_name}] {raw_name} → {norm_name}")

            if group == default_group:
                logging.debug(f"[UNCATEGORIZED][{source_name}] {raw_name} → {norm_name}")

            i += 2
        else:
            i += 1
