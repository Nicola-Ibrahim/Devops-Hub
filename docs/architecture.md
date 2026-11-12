# DevOps Hub architecture

This document describes the current code structure and its intended boundaries.
It is an architecture map, not proof that every listed capability has completed
local, PostgreSQL, Docker, or cloud acceptance.

## C4 Level 1: System context

```mermaid
flowchart LR
    developer["Developer"]
    operator["Platform operator"]
    hub["DevOps Hub<br/>Internal developer platform"]
    postgres[("Control-plane PostgreSQL")]
    docker["Local Docker runtime"]
    github["GitHub<br/>optional integration"]
    future["Server or cloud target<br/>planned"]

    developer -->|Dashboard or API| hub
    operator -->|Configures and operates| hub
    hub -->|Stores platform state| postgres
    hub -->|Provisions and removes resources| docker
    hub -.->|Repository and preview workflows| github
    hub -.->|Future provider adapters| future
```

## C4 Level 2: Containers and bounded contexts

```mermaid
flowchart LR
    developer["Developer"]
    operator["Platform operator"]
    docker["Local Docker runtime"]
    github["GitHub<br/>optional"]
    opa["OPA policy engine<br/>Identity permissions"]

    subgraph hub["DevOps Hub"]
        dashboard["Developer dashboard<br/>Next.js"]
        api["Platform API<br/>FastAPI"]
        subgraph identity["Identity bounded context"]
            identityModule["Identity module"]
        end
        subgraph platform["Developer Platform bounded context"]
            platformModule["Developer Platform module"]
            resourceWorker["Resource worker"]
            deliveryWorker["Application delivery worker"]
        end
        controlPlane[("Control-plane PostgreSQL")]
    end

    developer --> dashboard
    developer --> api
    operator --> api
    dashboard -->|HTTPS / JSON| api
    api -->|Identity commands and queries| identityModule
    api -->|Evaluate Identity permissions| opa
    api -->|Platform commands and queries| platformModule
    identityModule --> controlPlane
    platformModule --> controlPlane
    resourceWorker -->|Claim and complete operations| controlPlane
    deliveryWorker -->|Claim and complete delivery steps| controlPlane
    resourceWorker -->|Manage databases| docker
    deliveryWorker -->|Manage applications| docker
    deliveryWorker -.->|Repository integration| github
```

### Identity: access and administration

The Identity module dispatches these commands and queries. The boxes describe
application behavior; they are not separate deployed containers.

```mermaid
flowchart TB
    api["FastAPI identity routes"] --> module["IdentityModule<br/>execute / query"]
    module --> access["Sign in and manage access<br/>Log in/out; refresh session; rotate CSRF<br/>Change password; list/revoke sessions<br/>Issue/revoke/authenticate API tokens"]
    module --> people["Manage internal users<br/>Create, activate/deactivate users<br/>Bootstrap first admin; set up passwords"]
    module --> membership["Manage project membership<br/>List members; grant or change membership<br/>Select active project"]
    access --> identityDb[("Identity-owned tables")]
    people --> identityDb
    membership --> identityDb
```

### Developer Platform: projects, databases, and applications

The Developer Platform module dispatches the developer-facing actions. Workers
execute durable resource and delivery steps after the API transaction commits.

```mermaid
flowchart TB
    api["FastAPI platform routes"] --> module["DeveloperPlatformModule<br/>execute / query"]
    module --> projects["Set up a project<br/>Register project; view projects<br/>Browse approved resource options"]
    module --> databases["Request and manage a database<br/>Request PostgreSQL; view status and operation<br/>Get connection; extend lease; delete<br/>View activity and resources"]
    module --> applications["Create and deliver an application<br/>View templates; create application<br/>Attach database; deploy; retry failed step<br/>View applications and deployment history<br/>Process preview webhook"]
    projects --> platformDb[("Platform-owned tables")]
    databases --> platformDb
    applications --> platformDb
    platformDb --> resourceWorker["Database worker<br/>Provision, reconcile, and remove"]
    platformDb --> deliveryWorker["Application worker<br/>Execute delivery steps"]
    resourceWorker --> docker["Local Docker provider"]
    deliveryWorker --> docker
    deliveryWorker -.-> github["GitHub integration<br/>when configured"]
```

## Bounded-context responsibilities

| Context | Owns | Public services offered to the API or workers |
| --- | --- | --- |
| Identity | Internal users, password credentials, browser sessions, API tokens, project membership | Sign in and manage access; manage internal users; manage project membership |
| Developer Platform | Project registration, approved catalog, temporary resources and leases, operations, application delivery | Set up a project; request and manage a database; create and deliver an application |

The API calls only the `IdentityModule` and `DeveloperPlatformModule` contracts. It does not choose handlers or issue SQL directly. The resource and delivery workers use durable operations and delivery steps so provider effects can be retried after a restart.

## Trigger map

```mermaid
flowchart LR
    Developer[Developer or dashboard]
    API[FastAPI API]
    Identity[Identity module]
    Platform[Developer Platform module]
    DB[(Control-plane PostgreSQL)]
    ResourceWorker[Resource worker]
    DeliveryWorker[Application delivery worker]
    Docker[Local Docker provider]
    GitHub[GitHub adapter]

    Developer -->|login, browse, request, renew, delete| API
    API -->|identity commands and queries| Identity
    API -->|platform commands and queries| Platform
    Identity --> DB
    Platform -->|durable intent, operation, audit| DB
    ResourceWorker -->|claim and update resource operations| DB
    DeliveryWorker -->|claim and update delivery steps| DB
    ResourceWorker -->|provision, inspect, delete| Docker
    DeliveryWorker -->|deploy, remove| Docker
    DeliveryWorker -.->|optional repository and webhook flow| GitHub
```

## Domain-first rules

- Identity and Developer Platform are independent bounded contexts. Cross-context actor mapping belongs in the host or composition layer.
- Domain code owns business state and invariants. Application handlers orchestrate one use case through domain objects and interfaces.
- A repository corresponds to an aggregate or named transactional capability. The current resource aggregate uses `SQLAlchemyResourceRepository`; application delivery uses `SQLAlchemyApplicationDeliveryRepository`.
- SQLAlchemy, Docker, GitHub, encryption, and future AWS SDK calls belong in infrastructure. A future AWS adapter must implement an application port; the domain must not import cloud SDKs.
- HTTP authentication and project permission checks happen at the API/HTTP host boundary. The host owns transaction completion. Workers perform provider effects only after durable intent has committed.

## Current limits

- The local Docker target is the implemented demonstration target. Configured server, Kubernetes, and cloud targets remain future adapter work.
- GitHub integration is optional and configuration dependent.
- A database request being recorded does not mean a database is ready. The resource worker must confirm readiness and record the result.
- The dashboard is a client of the API; it does not contain platform lifecycle rules.
