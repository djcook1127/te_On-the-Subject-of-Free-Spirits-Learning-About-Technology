"""祝日データを含むAzure Functions用ZIPを作る。"""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

BACKEND = Path(__file__).resolve().parent
FILES = (
    "function_app.py", "host.json", ".funcignore", "requirements.txt",
    "selection_rooms.py", "shared_rooms.py", "local_rooms.py", "selection_store.py",
    "room_contract.py", "candidate_demo.py", "product_catalog.py", "connection_pool.py",
    "database.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with ZipFile(args.output, "w", compression=ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(BACKEND / name, name)
        archive.write(BACKEND.parent / "shared/japan-holidays.json", "shared/japan-holidays.json")


if __name__ == "__main__":
    main()
