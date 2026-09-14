from pathlib import Path

# Source checkout layout: <root>/apps/api/app/core/paths.py.
# Packaged/container deployments must preserve this layout and include data/templates.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TEMPLATE_DIRECTORY = PROJECT_ROOT / "data" / "templates"


def project_path(value: Path | str) -> Path:
    """Resolve application configuration paths independently of the shell cwd."""
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
