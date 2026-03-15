import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


REQUIRED_TOP = ["app_name", "db_path", "sources"]
REQUIRED_SOURCE = ["id", "name", "type", "url"]
URL_DEDUPE_EXCEPT = {"hackernews", "reddit"}


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    config_path = Path("config.yaml")
    config = load_config(config_path)
    errors: List[str] = []

    for key in REQUIRED_TOP:
        if key not in config:
            errors.append(f"Missing top-level key: {key}")

    sources = config.get("sources", [])
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        sources = []

    seen_ids = set()
    seen_urls = set()
    for idx, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"sources[{idx}] must be a mapping")
            continue
        for key in REQUIRED_SOURCE:
            if not source.get(key):
                errors.append(f"sources[{idx}] missing {key}")
        source_id = source.get("id")
        source_url = source.get("url")
        source_type = source.get("type")
        if source_id in seen_ids:
            errors.append(f"duplicate source id: {source_id}")
        if source_type not in URL_DEDUPE_EXCEPT:
            if source_url in seen_urls:
                errors.append(f"duplicate source url: {source_url}")
        if source_id:
            seen_ids.add(source_id)
        if source_url and source_type not in URL_DEDUPE_EXCEPT:
            seen_urls.add(source_url)

    if errors:
        print("Config validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Config validation OK")
    print(f"Sources: {len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
