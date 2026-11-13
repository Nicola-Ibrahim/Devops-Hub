export type ResourceOption = {
    template_id: string;
    version: string;
    target_id: string;
    size: {
        id: string;
        cpu_millis: number;
        memory_bytes: number;
        storage_bytes: number;
        storage_enforcement: string;
    };
    max_lifetime_seconds: number;
    requestable: boolean;
    unavailable_reason?: string | null;
};
export type Resource = {
    id: string;
    project_id: string;
    owner_id: string;
    environment_id?: string | null;
    display_name: string;
    template_id: string;
    target_id: string;
    size_id: string;
    desired_state: string;
    status: string;
    revision: number;
    created_at: string;
    expires_at: string;
    failure_code?: string | null;
};
export type Operation = {
    id: string;
    resource_id: string;
    action: string;
    status: string;
    attempts: number;
    error_code?: string | null;
};
export type ConnectionDetails = {
    connection_string: string;
    host: string;
    port: number;
    database: string;
    user: string;
    instructions: string;
};
