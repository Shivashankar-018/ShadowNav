"""Step 1 check: confirm the virtual environment and Python version."""

import sys
from pathlib import Path


def main() -> None:
    print("ShadowNav setup check")
    print("Python version:", sys.version.split()[0])
    print("Python executable:", sys.executable)

    project_root = Path(__file__).resolve().parent.parent
    print("Project root:", project_root)

    if ".venv" not in sys.executable.replace("/", "\\"):
        print("WARNING: You are not using the .venv interpreter.")
        print("Activate it with: .\\.venv\\Scripts\\Activate.ps1")
        raise SystemExit(1)

    required_folders = [
        "data/raw",
        "data/processed",
        "data/sample",
        "models",
        "ml",
        "routing",
        "gis",
        "services",
        "database",
        "utils",
        "tests",
        "templates",
        "static/css",
        "static/js",
        "static/images",
    ]
    missing = [name for name in required_folders if not (project_root / name).is_dir()]
    if missing:
        print("Missing folders:", ", ".join(missing))
        raise SystemExit(1)

    print("All required folders exist.")
    print("STEP 1 OK")


if __name__ == "__main__":
    main()
