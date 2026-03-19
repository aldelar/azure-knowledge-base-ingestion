"""Allow ``python -m fn_index article_dir [department]``."""

import logging
import sys

from fn_index import run


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python -m fn_index <article_dir> [department]", file=sys.stderr)
        sys.exit(1)

    article_dir = sys.argv[1]
    department = sys.argv[2] if len(sys.argv) == 3 else ""
    run(article_dir, department=department)


if __name__ == "__main__":
    main()
