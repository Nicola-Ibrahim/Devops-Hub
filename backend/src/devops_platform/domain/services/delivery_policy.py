"""Application-delivery policy expressed in domain language."""

from devops_platform.domain.errors import DomainError
from devops_platform.domain.value_objects.image_digest import ImageDigest


class DeliveryPolicy:
    @staticmethod
    def require_approved_image(image: ImageDigest, approved: frozenset[str]) -> None:
        if image.value not in approved:
            raise DomainError("Image is not approved for this target.")
