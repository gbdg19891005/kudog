# 📺 Kudog IPTV Playlist Builder

一个基于 Python 的 IPTV 播放列表聚合器，支持 **多源合并、别名归并、分组管理、屏蔽规则、自定义频道**，并通过 GitHub Actions 自动生成最新的 `kudog.m3u`。

---

## ✨ 功能特性
- 支持 **本地源 + 远程源** 自动合并
- 支持 **alias.txt** 别名归并（含正则）
- 支持 **groups.json** 分组规则、自定义频道、屏蔽列表
- 支持 **config.yaml** 配置化（UA、Referrer、EPG、日志级别、输出文件名等）
- 支持 **多 URL 策略**（保留多个 / 只保留第一个）
- 自动生成 **分组统计日志**
- GitHub Actions 定时运行，自动更新 `kudog.m3u`

---

## 📂 项目结构
playlist-builder/ ├── config.yaml # 全局配置 ├── sources.json # 源文件列表（本地/远程） ├── groups.json # 分组规则、自定义频道、屏蔽列表 ├── alias.txt # 别名映射（支持正则） │ ├── loader.py # 配置和源文件加载 ├── processor.py # 频道归并、分组、屏蔽逻辑 ├── exporter.py # 输出 M3U 文件 └── main.py # 入口脚本（可叫 merge.py）



---

## ⚙️ 配置说明

### config.yaml
```yaml
ua: "Mozilla/5.0"
referrer: "https://kudog.chatgb.dpdns.org/"
epg: "https://epg.catvod.com/epg.xml"
timeout: 10
keep_multiple_urls: true

log_level: "INFO"          # 可选: DEBUG / INFO / WARNING / ERROR
output_file: "kudog.m3u"   # 主输出文件
generate_debug_file: true  # 是否生成 merged.m3u
default_group: "综合"       # 默认分组
force_logo: true           # 是否强制补全 logo
force_tvg_id: false        # 是否强制补全 tvg-id
sources.json
json
{
  "remote_urls": [
    "https://example.com/iptv1.m3u",
    "https://example.com/iptv2.m3u"
  ],
  "local_files": [
    "local1.m3u",
    "local2.txt"
  ]
}
groups.json
json
{
  "rules": {
    "央视": ["CCTV", "央视"],
    "卫视": ["卫视"],
    "港澳台": ["TVB", "凤凰", "台视"],
    "体育": ["体育", "Sport"],
    "电影": ["电影", "Movie"]
  },
  "custom_channels": [
    {
      "name": "我的测试频道",
      "logo": "https://logo.example.com/test.png",
      "group": "自定义",
      "url": "http://example.com/stream.m3u8"
    }
  ],
  "blocklist": ["购物", "测试源"]
}
alias.txt
代码
CCTV-1综合,CCTV1,央视一套,中央一套
re:^CCTV[- ]?01$,CCTV-1综合
🚀 使用方法
本地运行
bash
pip install -r requirements.txt
python main.py
调试模式：

bash
python main.py --debug
或在 config.yaml 里设置 log_level: "DEBUG"。

GitHub Actions 自动化
仓库已配置 .github/workflows/merge.yml，默认每 2 小时 自动运行一次，生成并提交最新的 kudog.m3u。

用户可以直接订阅：

代码
https://raw.githubusercontent.com/<你的用户名>/kudog/main/kudog.m3u
📊 日志示例
代码
INFO: 成功读取远程文件: https://example.com/iptv1.m3u
INFO: 成功读取本地文件: local1.m3u
[SUMMARY] 分组统计：
  央视: 20 个频道
  卫视: 15 个频道
  综合: 30 个频道
[DONE] 全量重建完成，最终频道数: 65
🛠 开发计划
[ ] 增加频道 logo / tvg-id 自动补全

[ ] 增加 playlist 校验工具

[ ] 增加 pytest 单元测试

[ ] 增加 Web 界面配置管理
