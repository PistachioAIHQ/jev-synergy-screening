"""Download Bat4RCT and write data/demo_200.csv."""
from __future__ import annotations

from .bat4rct import build_demo_csv


def main() -> None:
    build_demo_csv()


if __name__ == "__main__":
    main()
