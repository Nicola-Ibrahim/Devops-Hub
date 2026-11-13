export type AppTemplate = {
    id: string;
    version: string;
    language: string;
    name: string;
    description: string;
};
export type App = {
    id: string;
    project_id: string;
    environment_id: string;
    name: string;
    template_id: string;
    template_version: string;
    repository_url: string | null;
    status: string;
    created_at: string;
    expires_at?: string | null;
    resource_id?: string | null;
};
export type DeliveryStep = {
    id: string;
    application_id: string;
    kind: string;
    status: string;
    attempts: number;
    error_code: string | null;
    created_at: string;
    updated_at: string;
};
export type AppDetails = {
    application: App;
    steps: DeliveryStep[];
};
export type PreviewDeployment = {
    id: string;
    status: string;
    url?: string | null;
    created_at?: string;
    image_digest?: string | null;
    target_id?: string;
};
export type LocalPreview = {
    application: App;
    deployments: PreviewDeployment[];
    steps?: DeliveryStep[];
};
