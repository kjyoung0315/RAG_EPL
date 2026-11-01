from src.config import get_settings
from src.indexer import index_items


if __name__ == "__main__":
    report, total = index_items(get_settings())
    print(f"Loaded {report.indexed_count} normalized items from {report.total_files} JSON files.")
    print(f"epl_items collection count: {total}")
