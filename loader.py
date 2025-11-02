import json, os, re, yaml

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_sources():
    with open("sources.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_groups():
    with open("groups.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_alias():
    alias_map = {}
    if os.path.exists("alias.txt"):
        with open("alias.txt", "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",") if p.strip()]
                main = parts[0]
                for alias in parts:
                    alias_map[alias] = main
    return alias_map
