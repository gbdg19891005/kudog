def export_m3u(channels, custom_channels, group_order, epg, keep_multiple_urls, outfile="kudog.m3u"):
    merged = [f'#EXTM3U x-tvg-url="{epg}"']

    for ch in custom_channels:
        merged.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
        merged.append(ch["url"])

    for group in group_order + ["综合"]:
        for name, ch in channels.items():
            if ch.get("group") == group:
                merged.append(ch["line"])
                urls = ch["urls"] if keep_multiple_urls else [ch["urls"][0]]
                merged.extend(urls)

    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(merged))
