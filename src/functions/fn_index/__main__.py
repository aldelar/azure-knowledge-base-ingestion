"""Allow ``python -m fn_index article_dir``."""

import logging
import sys

from fn_index import run


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    if len(sys.argv) != 2:
        print("Usage: python -m fn_index <article_dir>", file=sys.stderr)
        sys.exit(1)

    run(sys.argv[1])


if __name__ == "__main__":
    main()
