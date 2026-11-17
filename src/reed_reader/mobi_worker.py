"""Isolated KindleUnpack adapter; private worker, not an end-user command."""

import json
import resource
import sys
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    import mobi
    from loguru import logger

    logger.remove()
    _directory, output = mobi.extract(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps({"output": output}))


if __name__ == "__main__":
    main()
