"""PRISM backend package."""

import os
import sys

# macOS wheels can load both Homebrew and PyTorch OpenMP runtimes. Keeping
# their worker pools single-threaded avoids native crashes when ML stacks mix.
# Set this before native libraries load; an explicit operator setting wins.
if sys.platform == "darwin":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
