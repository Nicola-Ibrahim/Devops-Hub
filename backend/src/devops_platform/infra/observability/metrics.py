"""Aggregate operational metrics without credentials or resource identifiers."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from devops_platform.infra.persistence.models import (
    Operation,
    ProviderOrphanRow,
    Reservation,
    Resource,
)


async def render_metrics(session: AsyncSession) -> str:
    now = datetime.now(UTC)
    lines = []
    for action in ("provision", "delete", "reconcile"):
        queued = await session.scalar(
            select(func.count())
            .select_from(Operation)
            .where(Operation.action == action, Operation.status == "pending")
        )
        oldest = await session.scalar(
            select(func.min(Operation.created_at)).where(
                Operation.action == action, Operation.status == "pending"
            )
        )
        age = max(0, (now - oldest).total_seconds()) if oldest else 0
        lines.extend(
            [
                f'platform_operations_queued{{kind="{action}"}} {queued or 0}',
                f'platform_operation_oldest_age_seconds{{kind="{action}"}} {age}',
            ]
        )
        for outcome in ("succeeded", "failed", "cancelled"):
            count, total = (
                await session.execute(
                    select(
                        func.count(),
                        func.coalesce(
                            func.sum(
                                func.extract("epoch", Operation.completed_at - Operation.created_at)
                            ),
                            0,
                        ),
                    ).where(
                        Operation.action == action,
                        Operation.status == outcome,
                        Operation.completed_at.is_not(None),
                    )
                )
            ).one()
            labels = f'kind="{action}",outcome="{outcome}"'
            lines.extend(
                [
                    f"platform_operation_duration_seconds_sum{{{labels}}} {total}",
                    f"platform_operation_duration_seconds_count{{{labels}}} {count}",
                ]
            )
    for status, count in await session.execute(
        select(Resource.status, func.count()).group_by(Resource.status)
    ):
        if status in {
            "pending",
            "provisioning",
            "ready",
            "failed",
            "deleting",
            "cleanup_failed",
            "deleted",
        }:
            lines.append(f'platform_resources{{status="{status}"}} {count}')
    cleanup = await session.scalar(
        select(func.count())
        .select_from(Resource)
        .where(
            Resource.desired_state == "deleted",
            Resource.status != "deleted",
            Resource.expires_at < now,
        )
    )
    retries = await session.scalar(
        select(func.coalesce(func.sum(func.greatest(Operation.attempts - 1, 0)), 0))
    )
    orphans = await session.scalar(select(func.count()).select_from(ProviderOrphanRow))
    lines.extend(
        [
            f"platform_resources_overdue_cleanup_total {cleanup or 0}",
            f"platform_worker_claim_retries_total {retries or 0}",
            f"platform_orphaned_resources {orphans or 0}",
        ]
    )
    for field in ("cpu_millis", "memory_bytes", "storage_bytes"):
        reserved = await session.scalar(
            select(func.coalesce(func.sum(getattr(Reservation, field)), 0)).where(
                Reservation.released_at.is_(None)
            )
        )
        lines.append(f"platform_reserved_{field} {reserved or 0}")
    return "\n".join(lines) + "\n"
