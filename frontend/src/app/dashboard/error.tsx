"use client";
export default function WorkspaceError({ reset }: {
    error: Error & {
        digest?: string;
    };
    reset: () => void;
}) { return <div className="content-wrap"><section className="panel"><h1>Workspace unavailable</h1><p role="alert">This page could not be loaded.</p><button className="primary-button" onClick={reset}>Try again</button></section></div>; }
