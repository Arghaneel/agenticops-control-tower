"""Validate native artifacts using the published Evals 0.7.2 contracts.

Packaged upstream schemas keep this reader independent of sibling installations.
No caller-supplied schemas or remote references are evaluated.
"""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator

ArtifactKind = Literal["evaluation_report", "gate_decision"]


@lru_cache(maxsize=2)
def _validator(kind: ArtifactKind) -> Draft202012Validator:
    name = "evaluation-report" if kind == "evaluation_report" else "gate-decision"
    resource = files("agenticops_control_tower").joinpath("schemas").joinpath("evals")
    schema = json.loads(resource.joinpath(f"{name}-1.0.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_evals_artifact(artifact: Any, kind: ArtifactKind) -> None:
    """Raise a value-free diagnostic on structural failure; never compute a gate."""
    if kind not in ("evaluation_report", "gate_decision"):
        raise ValueError("Unsupported native Evals artifact type")
    if (
        kind == "evaluation_report"
        and isinstance(artifact, dict)
        and artifact.get("schema_version", "1.0") != "1.0"
    ):
        raise ValueError("Invalid native Evals evaluation_report: unsupported schema_version")
    error = next(_validator(kind).iter_errors(artifact), None)
    if error is not None:
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Invalid native Evals {kind} at {location} ({error.validator})")
