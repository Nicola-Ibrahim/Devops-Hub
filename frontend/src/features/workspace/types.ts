export type Environment = {
    id: string;
    name: string;
};
export type Project = {
    project_id: string;
    name: string;
    owning_team_name?: string | null;
    repository?: string | null;
    configured: boolean;
    environments: Environment[];
};
