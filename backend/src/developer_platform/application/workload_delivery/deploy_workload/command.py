from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentCommand:
    image_digest: str
    target_id: str = "local"
