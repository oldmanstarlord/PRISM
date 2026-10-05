"""Test verifying that Layer 2 code remains strictly untouched."""

import subprocess
from pathlib import Path


def test_layer2_files_are_strictly_untouched() -> None:
    """Requirement: Layer 2 code is approved and must not be edited. Assert zero git diff."""
    repo_root = Path(__file__).resolve().parents[2]
    layer2_dir = repo_root / "backend" / "app" / "correlation_mst"

    assert layer2_dir.exists(), "Layer 2 directory must exist"

    cmd = ["git", "diff", "--exit-code", "HEAD", "--", str(layer2_dir)]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, (
        f"Layer 2 code has uncommitted changes:\n{proc.stdout}\n{proc.stderr}"
    )
