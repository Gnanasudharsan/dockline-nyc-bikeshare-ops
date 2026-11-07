"""Location of the dbt project and its compiled manifest.

Dagster reads dbt's ``manifest.json`` to build one asset per model, seed, and snapshot.
In the container image the manifest is compiled at build time. On a laptop
(``dagster dev``) and in tests, :func:`ensure_manifest` compiles it on first use.
"""

from __future__ import annotations

import os
from pathlib import Path

from dagster_dbt import DbtProject

__all__ = ["DBT_PROJECT_DIR", "DbtProject", "dbt_project", "ensure_manifest"]

REPO_ROOT = Path(__file__).resolve().parents[3]

DBT_PROJECT_DIR = Path(os.environ.get("DBT_PROJECT_DIR", str(REPO_ROOT / "dbt")))

dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    target=os.environ.get("DBT_TARGET", "dev"),
)


def ensure_manifest(project: DbtProject = dbt_project) -> Path:
    """Compile the dbt manifest if it is missing and return its path.

    Runs ``dbt deps`` (when packages are missing) and ``dbt parse``. Parsing does not
    connect to the database, but the profile must render, so a placeholder password
    is supplied when none is set.
    """
    if not project.manifest_path.exists():
        os.environ.setdefault("POSTGRES_PASSWORD", "parse-only-placeholder")
        project.preparer.prepare(project)
    return project.manifest_path
