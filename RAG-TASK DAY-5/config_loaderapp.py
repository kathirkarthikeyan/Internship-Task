import json
import os

CONFIG_FILE = "config.json"

def load_config():
    """Load config and auto-create required directories."""
    if not os.path.isfile(CONFIG_FILE):
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Auto-create directories
    dirs_to_create = [
        config.get("input_dir", ""),
        config.get("output_dir", ""),
        config.get("log_dir", ""),
        os.path.dirname(config.get("chunks_json", "")),
        os.path.dirname(config.get("faiss_index_path", ""))
    ]

    for d in dirs_to_create:
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    return config
