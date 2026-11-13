export type BrowserPrincipal = {
    userId: string;
    userName: string;
    sessionId: string;
    projectId?: string | null;
    projectName?: string | null;
    role?: string | null;
    scopes: string[];
    csrfToken: string;
    memberships: {
        projectId: string;
        projectName: string;
        role: string;
    }[];
};
export type BrowserEnvelope = {
    csrfToken?: string;
    principal: BrowserPrincipal;
    absoluteExpiresAt?: string;
};
