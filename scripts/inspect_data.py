from src.config import get_settings
from src.data_loader import load_items


if __name__ == "__main__":
    settings = get_settings()
    items, report = load_items(settings.data_dir)
    print(f"JSON files read: {report.total_files}")
    print(f"Indexable items: {len(items)}")
    print("Indexed by type:")
    for item_type, count in sorted(report.indexed_by_type.items()):
        print(f"  - {item_type}: {count}")
    print("Skipped duplicate/manifest directories:")
    for directory, count in sorted(report.skipped_by_directory.items()):
        print(f"  - {directory}: {count}")
    if report.invalid_files:
        print("Invalid JSON:")
        print("\n".join(report.invalid_files))
