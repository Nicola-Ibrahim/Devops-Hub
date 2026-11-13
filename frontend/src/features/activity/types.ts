export type Activity = {
    id: string;
    actor_id: string | null;
    resource_id: string;
    operation_id: string;
    action: string;
    created_at: string;
};
