"""dbt models, seeds, and snapshots as Dagster assets, plus the raw tables they read."""

from collections.abc import Iterator, Mapping
from datetime import timedelta
from typing import Any

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from dockline_orchestration.project import DbtProject, dbt_project, ensure_manifest

# Freshness expectations for mart tables, by schedule tag. Dagster shows each asset as
# fresh / warning / failing against these windows.
HOURLY_MART_FRESHNESS = dg.FreshnessPolicy.time_window(
    fail_window=timedelta(hours=2), warn_window=timedelta(minutes=75)
)
DAILY_MART_FRESHNESS = dg.FreshnessPolicy.time_window(
    fail_window=timedelta(hours=26), warn_window=timedelta(hours=25)
)


def freshness_policy_for(dbt_resource_props: Mapping[str, Any]) -> dg.FreshnessPolicy | None:
    """Return the freshness policy for a dbt node: marts only, chosen by schedule tag."""
    if dbt_resource_props["resource_type"] != "model":
        return None
    fqn = dbt_resource_props.get("fqn", [])
    if len(fqn) < 2 or fqn[1] != "marts":
        return None
    if dbt_resource_props.get("config", {}).get("materialized") == "view":
        return None  # views are always current
    tags = set(dbt_resource_props.get("tags", []))
    if "daily" in tags:
        return DAILY_MART_FRESHNESS
    return HOURLY_MART_FRESHNESS


class DocklineDbtTranslator(DagsterDbtTranslator):
    """Group assets by dbt layer and attach freshness policies to marts."""

    def get_asset_spec(
        self, manifest: Mapping[str, Any], unique_id: str, project: DbtProject | None
    ) -> dg.AssetSpec:
        """Add the mart freshness policy to the default spec."""
        spec = super().get_asset_spec(manifest, unique_id, project)
        props = self.get_resource_props(manifest, unique_id)
        policy = freshness_policy_for(props)
        if policy is None:
            return spec
        return spec.replace_attributes(freshness_policy=policy)

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str | None:
        """Return the layer (staging, intermediate, marts, ...) as the asset group."""
        resource_type = dbt_resource_props["resource_type"]
        if resource_type == "seed":
            return "reference"
        if resource_type == "snapshot":
            return "snapshots"
        if resource_type == "source":
            return "raw"
        fqn = dbt_resource_props.get("fqn", [])
        return str(fqn[1]) if len(fqn) > 2 else "dbt"


@dbt_assets(
    manifest=ensure_manifest(),
    project=dbt_project,
    dagster_dbt_translator=DocklineDbtTranslator(),
    name="dockline_dbt",
)
def dockline_dbt_assets(context: dg.AssetExecutionContext, dbt: DbtCliResource) -> Iterator[Any]:
    """Run ``dbt build`` for the selected models (models, tests, seeds, snapshots)."""
    yield from dbt.cli(["build"], context=context).stream()
