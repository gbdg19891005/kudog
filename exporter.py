import logging
from typing import Dict, Any, List

def export_m3u(channels: Dict[str, Any], customchannels: List[Dict], grouporder: List[str], 
               epg: str, keep_multiple_urls: bool, outfile: str = "kudog.m3u",
               generatedebugfile: bool = False, defaultgroup: str = "未分类"):
    """生成标准M3U文件，按分组排序输出"""
    merged = [f'#EXTM3U']  # M3U文件头
    merged.append(f'#x-tvg-url:{epg}')  # EPG节目单
    
    # === 1. 添加自定义频道（groups.json中定义） ===
    for ch in customchannels:
        name = ch["name"]
        logo = ch.get("logo", "")
        group = ch.get("group", defaultgroup)
        line = f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}",group-title="{group},{name}"'
        merged.append(line)
        merged.append(ch["url"])
    
    # === 2. 按分组排序输出处理后的频道 ===
    group_counts = {}
    for group in grouporder + [defaultgroup]:  # 规则组 + 默认组
        group_channels = 0
        for name, ch in channels.items():
            if ch.get('group') == group:
                ch_line = ch['line']  # 已处理好的EXTINF行
                urls = ch['urls'] if keep_multiple_urls else [ch['urls'][0]]
                merged.append(ch_line)  # EXTINF行
                merged.extend(urls)     # 一个或多个URL行
                group_channels += 1
        group_counts[group] = group_channels
    
    # === 3. 写入主输出文件 ===
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(merged) + '\n')
    logging.info(f"📁 MAIN OUTPUT: {outfile} ({len(merged)//2} lines)")
    
    # === 4. 生成调试文件（完整内容+统计） ===
    if generatedebugfile:
        debugfile = outfile.replace('.m3u', '_debug.m3u')
        with open(debugfile, 'w', encoding='utf-8') as f:
            f.write('\n'.join(merged) + '\n')
        logging.info(f"🔍 DEBUG FILE: {debugfile}")
    
    # === 5. 统计报告 ===
    logging.info("📊 CHANNEL SUMMARY:")
    total = sum(group_counts.values())
    for group, count in sorted(group_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count/total*100) if total else 0
        logging.info(f"  🎯 {group}: {count} ({pct:.1f}%)")
    logging.info(f"  🌟 TOTAL UNIQUE: {total}")
