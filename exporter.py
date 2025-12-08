import logging
import os
import tempfile
import shutil
from typing import Dict, List, Optional
from datetime import datetime


def get_shanghai_time(time_format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """获取中国上海时区的当前时间"""
    try:
        import pytz
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(shanghai_tz)
        return now.strftime(time_format)
    except ImportError:
        # 如果没有安装 pytz，使用系统时间
        logging.warning("[WARN] 未安装 pytz，使用系统时间")
        return datetime.now().strftime(time_format)
    except Exception as e:
        logging.warning(f"[WARN] 获取上海时间失败: {e}，使用系统时间")
        return datetime.now().strftime(time_format)


def export_m3u(channels: Dict[str, dict], custom_channels: List[dict], 
               group_order: List[str], epg: str, keep_multiple_urls: bool,
               outfile: str = "kudog.m3u", generate_debug_file: bool = False, 
               default_group: str = "综合", groups_config: Optional[dict] = None) -> None:
    """
    导出 M3U 文件
    :param channels: 频道字典
    :param custom_channels: 自定义频道列表
    :param group_order: 分组顺序
    :param epg: EPG 地址
    :param keep_multiple_urls: 是否保留多个 URL
    :param outfile: 主输出文件名
    :param generate_debug_file: 是否生成调试文件
    :param default_group: 默认分组
    :param groups_config: groups.json 配置（可选，用于更新时间功能）
    """
    
    def write_m3u_content() -> List[str]:
        """生成 M3U 内容"""
        merged = [f'#EXTM3U x-tvg-url="{epg}"']
        
        # 自定义频道置顶
        for ch in custom_channels:
            merged.append(
                f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch.get("logo","")}" '
                f'group-title="{ch.get("group", default_group)}",{ch["name"]}'
            )
            merged.append(ch["url"])
        
        # 【新增】在自定义频道后添加更新时间频道（如果配置启用）
        if groups_config:
            update_config = groups_config.get("update_time_config", {})
            if update_config.get("enabled", False):
                time_format = update_config.get("format", "%Y-%m-%d %H:%M:%S")
                prefix = update_config.get("prefix", "⏰更新时间: ")
                update_url = update_config.get("url", "https://vd3.bdstatic.com/mda-mev3hw0htz28h5wn/1080p/cae_h264/1622343504467773766/mda-mev3hw0htz28h5wn.mp4")
                
                update_time = get_shanghai_time(time_format)
                update_name = f"{prefix}{update_time}"
                
                # 使用更新时间作为独立分组名称
                update_group = update_name  # 👈 修改：分组名 = 更新时间
                if custom_channels:
                    update_logo = custom_channels[0].get("logo", "")
                else:
                    update_logo = ""
                
                merged.append(
                    f'#EXTINF:-1 tvg-name="{update_name}" tvg-logo="{update_logo}" '
                    f'group-title="{update_group}",{update_name}'
                )
                merged.append(update_url)
        
        # 按 group_order 排序输出（原有逻辑）
        group_counts = {}
        for group in group_order + [default_group]:
            for name, ch in channels.items():
                if ch.get("group") == group:
                    merged.append(ch["line"])
                    urls = ch["urls"] if keep_multiple_urls else [ch["urls"][0]]
                    merged.extend(urls)
                    group_counts[group] = group_counts.get(group, 0) + 1
        
        return merged, group_counts
    
    # 生成内容
    merged, group_counts = write_m3u_content()
    
    # 写主输出文件（原子写入）
    temp_fd, temp_path = tempfile.mkstemp(suffix='.m3u', text=True)
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            f.write("\n".join(merged))
        shutil.move(temp_path, outfile)
        logging.info(f"[DONE] 已生成主输出文件: {outfile}")
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logging.error(f"[ERROR] 写入主输出文件失败: {e}")
        return

    # 可选：生成调试文件
    if generate_debug_file:
        debug_file = "merged.m3u"
        try:
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write("\n".join(merged))
            logging.info(f"[DEBUG] 已生成调试文件: {debug_file}")
        except Exception as e:
            logging.warning(f"[WARN] 写入调试文件失败: {e}")

    # 分组统计
    logging.info("[SUMMARY] 分组统计：")
    for group, count in group_counts.items():
        logging.info(f"  {group}: {count} 个频道")
    logging.info(f"[SUMMARY] 最终频道数: {len(channels)}")
