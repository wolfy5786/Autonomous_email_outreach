# Infrastructure & Deployment Design

> Companion document to [`README.md`](./README.md). The README describes **what** the system does. This document describes **how it is deployed** on AWS using EKS, and the Terraform + Kubernetes components that compose the running system.

---

## Table of Contents

1. [Summary of Architecture Decisions](#summary-of-architecture-decisions)
2. [Amendment to the Logical Architecture](#amendment-to-the-logical-architecture)
3. [High-Level Deployment Diagram](#high-level-deployment-diagram)
4. [AWS Network Layout](#aws-network-layout)
5. [EKS Cluster Layout](#eks-cluster-layout)
6. [Node Groups](#node-groups)
7. [Component Inventory](#component-inventory)
8. [Per-Service Compute & Scaling](#per-service-compute--scaling)
9. [Autoscaling Strategy (KEDA + HPA)](#autoscaling-strategy-keda--hpa)
10. [Ingress & Load Balancing](#ingress--load-balancing)
11. [Service Discovery & Service Mesh](#service-discovery--service-mesh)
12. [Sidecar Configuration](#sidecar-configuration)
13. [Database (MongoDB) Deployment](#database-mongodb-deployment)
14. [Message Queue (RabbitMQ)](#message-queue-rabbitmq)
15. [Secrets Management](#secrets-management)
16. [LLM Access Path (OpenAI)](#llm-access-path-openai)
17. [Observability](#observability)
18. [CI/CD and Container Registry](#cicd-and-container-registry)
19. [Terraform Module Layout](#terraform-module-layout)
20. [Helm Chart Layout](#helm-chart-layout)
21. [Scale-Up Path (Demo → Production)](#scale-up-path-demo--production)
22. [Rough Monthly Cost Estimate](#rough-monthly-cost-estimate)
23. [Open Items / Follow-Ups](#open-items--follow-ups)

---

## Summary of Architecture Decisions

| Area | Decision |
|---|---|
| Kubernetes control plane | **Amazon EKS** (managed) |
| Worker nodes | **EC2 managed node groups** (3 groups: general, scraping, stateful) |
| Availability zones | **2 AZs** (EKS minimum; cost-conscious) |
| NAT egress | **Single NAT Gateway** in AZ-A (demo trade-off; documented SPOF) |
| Message queue | **RabbitMQ** only — one application queue + one dead-letter queue per event type (same logical names as README § Message Queues). **Amazon SQS is not used.** |
| Primary datastore | **MongoDB** as a StatefulSet in EKS, backed by EBS gp3 PVC |
| Vector / semantic search | **Embeddings co-located in MongoDB** (same collection, brute-force cosine for demo; migrate to Atlas Vector Search or Qdrant at scale) |
| Ingress / API gateway | **NGINX Ingress Controller** fronted by an **AWS NLB** |
| Service mesh | **Linkerd** (lightweight) — provides mTLS, metrics sidecar, retries |
| Service discovery | Native **Kubernetes Services + CoreDNS** |
| Pod autoscaling | **KEDA** for Sourcing, Prospecting, Messaging, Planning (queue-depth driven, with CPU as composite fallback trigger). **HPA on CPU** for Orchestrator, web-ui, and nginx |
| LLM provider | **OpenAI** (external API over egress via NAT) |
| Secrets | **AWS Secrets Manager + External Secrets Operator** (IRSA-scoped) |
| Web UI | **Static SPA served by a dedicated `web-ui` nginx pod** — full dashboard for campaign management, prospect browsing, draft status tracking, and pipeline monitoring. The Review Service and Send Service are removed; review-related API endpoints are folded into the Orchestrator. The system writes drafts to the user's email account and marks the task done. |
| Observability | **Prometheus + Grafana** in-cluster (metrics) + **CloudWatch Logs** (log aggregation) |
| Registry & deploy | **ECR** for images; **Helm charts** applied from CI |
| IaC state | **S3 + DynamoDB lock** |

---

## Amendment to the Logical Architecture

Two services from the original design are **removed**: the **Review Service** and the **Send Service**. The system no longer reviews or sends emails — it generates drafts and writes them to the user's email account.

### Changes from the original design

**Review Service → removed.** The review flow is replaced by:
- A static SPA (`web-ui`) serves as the full system dashboard (campaign management, prospect browsing, draft status, pipeline monitoring).
- Draft-related API endpoints are **absorbed into the Orchestrator**:
  - `GET /api/campaigns/:id/drafts`
  - `GET /api/drafts/:id`
  - `POST /api/drafts/:id/regenerate`
- The `review.requested` and `review.completed` RabbitMQ queues are **retired**.

**Send Service → removed.** The email delivery flow is replaced by:
- The **Messaging Service** writes drafts directly to the user's email account via the provider's Draft API (Gmail `drafts.create`, Microsoft Graph `createDraft`).
- Once a draft is written, the task is marked complete. The user reviews, edits, and sends from their own email client.
- The `send.requested`, `send.completed`, and `send.failed` RabbitMQ queues are **retired**.
- New queues: `draft.written` (Messaging → Orchestrator) and `draft.failed` (Messaging → Orchestrator).

**Updated queue list** (vs. README § Message Queues): drop `review.requested`, `review.completed`, `send.requested`, `send.completed`, `send.failed`, `messaging.completed`. Add `draft.written`, `draft.failed`.

---

## High-Level Deployment Diagram

```
                 Internet
                    │
                    ▼
        ┌───────────────────────┐
        │   AWS NLB (public)    │  ← ACM TLS termination (optional)
        └───────────┬───────────┘
                    │ :443 / :80
                    ▼
        ┌───────────────────────┐
        │  ingress-nginx pods   │  (HPA 2→4)
        │  (web-ui + /api)      │
        └───────────┬───────────┘
                    │ ClusterIP via CoreDNS + Linkerd mTLS
   ┌────────────────┼──────────────────────────────────┐
   ▼                ▼                                  ▼
┌─────────┐   ┌─────────────┐                   ┌──────────────┐
│ web-ui  │   │ orchestrator│  ◄── HTTP /api ──►│   mongodb    │
│ (nginx) │   │ (all API    │                   │ StatefulSet  │
│ static  │   │  endpoints) │                   │ (stateful NG)│
│  SPA    │   └──────┬──────┘                   └──────▲───────┘
└─────────┘          │ publishes to RabbitMQ            │
                     ▼                                 │
         ┌───────────────────────┐                     │
         │      RabbitMQ         │  (in-cluster or     │
         │  plan.requested       │   Amazon MQ)        │
         │  sourcing.requested   │                     │
         │  prospecting.*        │                     │
         │  messaging.*          │                     │
         │  draft.* (+ DLQs)     │                     │
         └───────────┬───────────┘                     │
                     │ KEDA scales consumers on depth  │
    ┌────────────────┼─────────────┐                   │
    ▼                ▼             ▼                   │
┌─────────┐  ┌─────────────┐  ┌──────────┐            │
│planning │  │  sourcing   │  │messaging │            │
│ (gen NG)│  │(scraping NG)│  │ (gen NG) │            │
│         │  │ headless    │  │ writes   │            │
│         │  │ browsers    │  │ drafts   │            │
└────┬────┘  └──────┬──────┘  └────┬─────┘            │
     │ all reads/writes ──────────────────────────────►│
     │         ┌───────────────┐                       │
     └────────►│ prospecting   │──────────────────────►│
               │  (general NG) │
               └───────────────┘

                     │ Messaging Service also calls external
                     │ email provider Draft APIs (Gmail, Microsoft)
                     └──→ via NAT Gateway egress

Control plane (namespace: platform)
 ├─ linkerd-control-plane
 ├─ keda
 ├─ external-secrets-operator
 ├─ ingress-nginx
 ├─ kube-prometheus-stack (prometheus + grafana)
 └─ fluent-bit DaemonSet  → CloudWatch Logs
```

---

## AWS Network Layout

| Resource | Config |
|---|---|
| VPC | `10.40.0.0/16` |
| AZs | `us-west-2a`, `us-west-2b` (pick region closest to operators) |
| Public subnets | `10.40.0.0/24`, `10.40.1.0/24` (one per AZ) — host NLB + NAT GW |
| Private subnets | `10.40.10.0/24`, `10.40.11.0/24` — host EKS worker nodes + pods |
| Internet Gateway | attached to VPC |
| NAT Gateway | **single**, in `us-west-2a` public subnet; both private subnets route `0.0.0.0/0` to it |
| VPC endpoints (gateway) | **S3**, **DynamoDB** (free, avoids NAT hops for state/backups) |
| VPC endpoints (interface) | **ECR api + ECR dkr**, **Secrets Manager**, **CloudWatch Logs**, **STS** (reduces NAT bandwidth cost and latency). No SQS endpoint — message traffic stays on **RabbitMQ** (in-cluster or private Amazon MQ), not Amazon SQS. Messaging Service egress to Gmail/Microsoft Draft APIs goes through NAT. |
| Security groups | one per concern: cluster, worker-nodes, nlb, mongodb, bastion (optional) |

**NAT SPOF note**: single NAT is intentional for demo. The scale-up path is "add second NAT GW in AZ-b" — purely a Terraform variable flip.

---

## EKS Cluster Layout

| Setting | Value |
|---|---|
| Cluster name | `email-outreach-dev` |
| Kubernetes version | latest stable (e.g. 1.30) |
| Control plane endpoint | **private + public**, public access restricted to operator CIDR |
| IRSA (OIDC provider) | enabled |
| Logging | API, audit, authenticator → CloudWatch |
| Add-ons | vpc-cni, coredns, kube-proxy, aws-ebs-csi-driver |
| Cluster autoscaler | **Karpenter** (preferred) or `cluster-autoscaler` on managed node groups |

---

## Node Groups

Three managed node groups with taints, so workloads land where intended.

| Node group | Instance type | Min/Desired/Max | Taint | Purpose |
|---|---|---|---|---|
| `general` | `t3.medium` (2 vCPU, 4 GiB) | 2 / 2 / 6 | none | Orchestrator, Planning, Prospecting, Messaging, web-ui, ingress-nginx, linkerd, external-secrets, KEDA, prometheus, grafana |
| `scraping` | `m5.large` (2 vCPU, 8 GiB) — **memory-heavy** for headless browsers | 0 / 1 / 8 | `workload=scraping:NoSchedule` | Sourcing service pods running crawl4ai / browser-use / Firecrawl |
| `stateful` | `t3.medium` (or `r5.large` if Mongo working set grows) | 1 / 1 / 2 | `workload=stateful:NoSchedule` | MongoDB StatefulSet. Pinned to AZ-a (EBS volume is AZ-scoped) |

**Why three groups:**
- **scraping** workloads are bursty and memory-heavy; isolating them prevents a crawl surge from starving HTTP services. Also makes SPOT instances safe to use here (we can checkpoint scrape progress).
- **stateful** group is tainted so scheduler cannot place noisy neighbours next to MongoDB; also simplifies node replacements.
- **general** carries everything else on cheap on-demand t3s.

Tolerations for scraping/stateful are set in their respective Helm charts.

---

## Component Inventory

Everything that runs in the cluster, grouped by namespace.

### Namespace `app`
| Component | Kind | Image source |
|---|---|---|
| `orchestrator` | Deployment | ECR: `email-outreach/orchestrator` |
| `planning` | Deployment | ECR: `email-outreach/planning` |
| `sourcing` | Deployment | ECR: `email-outreach/sourcing` |
| `prospecting` | Deployment | ECR: `email-outreach/prospecting` |
| `messaging` | Deployment | ECR: `email-outreach/messaging` |
| `web-ui` | Deployment | ECR: `email-outreach/web-ui` (nginx + static SPA build) |

### Namespace `data`
| Component | Kind | Image source |
|---|---|---|
| `mongodb` | StatefulSet (1 replica) + headless Service + PVC (gp3, 50 Gi) | Bitnami MongoDB chart |
| `rabbitmq` | StatefulSet (or single-node) + Service | Bitnami / RabbitMQ Cluster Operator (same logical queues as README § Message Queues) |

### Namespace `platform`
| Component | Kind | Source |
|---|---|---|
| `ingress-nginx` | Deployment + NLB Service | `ingress-nginx` Helm chart |
| `linkerd-control-plane` | Deployments | `linkerd-control-plane` Helm chart |
| `linkerd-viz` | Deployments (optional) | `linkerd-viz` Helm chart |
| `keda` | Deployments | `kedacore/keda` Helm chart |
| `external-secrets` | Deployments | `external-secrets` Helm chart |
| `cert-manager` | Deployments (optional, if using ACME) | `jetstack/cert-manager` chart |
| `kube-prometheus-stack` | Prometheus + Grafana + Alertmanager | `prometheus-community/kube-prometheus-stack` |
| `fluent-bit` | DaemonSet | `fluent/fluent-bit` chart (ships logs → CloudWatch) |

### Outside the cluster (AWS managed)
- **Secrets Manager** entries (OpenAI key, Apollo/Hunter keys, SMTP/SES creds, Mongo admin password)
- **ECR repositories** (one per service)
- **CloudWatch log groups** (one per namespace, retention 14 days)
- **S3 bucket** (Terraform state, optional Mongo backups)
- **DynamoDB table** (Terraform state lock)

**RabbitMQ** is the only message broker: deploy it **in-cluster** (namespace `data` or `platform`) or use **Amazon MQ for RabbitMQ** in the VPC. Queues, exchanges, and DLQs are defined in RabbitMQ — not Amazon SQS.

---

## Per-Service Compute & Scaling

All values are **initial** requests/limits; revise after 1 week of Grafana data.

| Service | CPU req / limit | Mem req / limit | Node group | Min / Max replicas | Primary scaler | Notes |
|---|---|---|---|---|---|---|
| orchestrator | 100m / 500m | 256Mi / 512Mi | general | 2 / 4 | HPA CPU @70% | HTTP-bound; 2 replicas for ingress HA |
| planning | 200m / 1000m | 512Mi / 1Gi | general | 1 / 5 | KEDA: `plan.requested` depth ≥ 1 + HPA CPU @70% | LLM latency bound, not CPU bound |
| sourcing | 500m / 2000m | 1Gi / 4Gi | **scraping** | 1 / 10 | KEDA: `sourcing.requested` depth ≥ 5 + HPA CPU @70% | Headless browser RAM-hungry |
| prospecting | 250m / 1000m | 512Mi / 1Gi | general | 1 / 5 | KEDA: `prospecting.requested` depth ≥ 1 + HPA CPU @70% | Mostly cosine sim + DB reads |
| messaging | 200m / 800m | 512Mi / 1Gi | general | 1 / 5 | KEDA: `messaging.requested` depth ≥ 1 + HPA CPU @70% | LLM-bound + external Draft API calls |
| web-ui | 50m / 200m | 64Mi / 128Mi | general | 2 / 2 | none (static nginx) | HA via 2 replicas |
| ingress-nginx | 100m / 500m | 128Mi / 256Mi | general | 2 / 4 | HPA CPU @70% | |
| mongodb | 500m / 2000m | 2Gi / 4Gi | stateful | 1 (StatefulSet) | vertical (change instance type) | EBS gp3 50Gi PVC |
| prometheus | 500m / 1000m | 1Gi / 2Gi | general | 1 | none | 15-day retention on EBS |
| grafana | 100m / 500m | 128Mi / 256Mi | general | 1 | none | |
| fluent-bit | 50m / 200m | 64Mi / 128Mi | all (DS) | n/a | DaemonSet | |
| linkerd-proxy (sidecar) | 100m / 500m | 64Mi / 128Mi | all | injected | — | Counted inside each app pod |
| linkerd-control-plane | 200m / 500m | 300Mi / 500Mi | general | 3 | — | destination, identity, proxy-injector |
| keda-operator | 100m / 500m | 128Mi / 256Mi | general | 1 | — | |
| external-secrets | 50m / 200m | 64Mi / 128Mi | general | 1 | — | |

**Linkerd-proxy sidecar adds ~100m CPU / 64Mi memory to every app pod** — factor this into node sizing.

---

## Autoscaling Strategy (KEDA + HPA)

KEDA is the right fit for a queue-choreographed system because CPU usage lags behind queue backlog. KEDA watches **RabbitMQ queue length** (HTTP management API, authenticated via a `TriggerAuthentication` that references a Kubernetes Secret with the broker URL and credentials) and synthesizes an HPA under the hood — which means we can also add a **CPU trigger to the same `ScaledObject`**, so it scales on whichever fires first (queue depth OR CPU).

### KEDA scaler example (Sourcing)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: sourcing
  namespace: app
spec:
  scaleTargetRef:
    name: sourcing
  pollingInterval: 15
  cooldownPeriod: 120
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
    - type: rabbitmq
      metadata:
        protocol: http
        queueName: sourcing.requested
        mode: QueueLength
        value: "5"            # target messages per pod
        activationValue: "0"
      authenticationRef:
        name: keda-rabbitmq-auth
    - type: cpu
      metadata:
        type: Utilization
        value: "70"
```

Use KEDA’s `TriggerAuthentication` (or `ClusterTriggerAuthentication`) so the scaler can reach the RabbitMQ **management API** (host, user, password, vhost). See [KEDA RabbitMQ scaler](https://keda.sh/docs/scalers/rabbitmq-queue/). **Do not** use the `aws-sqs-queue` trigger — SQS is out of scope.

### Services on KEDA + CPU-fallback
- `planning` → scaler on `plan.requested`
- `sourcing` → scaler on `sourcing.requested`
- `prospecting` → scaler on `prospecting.requested`
- `messaging` → scaler on `messaging.requested`

### Services on HPA-only
- `orchestrator` → HPA CPU @70%, min 2, max 4
- `ingress-nginx` → HPA CPU @70%, min 2, max 4
- `web-ui` → fixed 2 replicas

### Cluster-level autoscaling
Use **Karpenter** (recommended) or `cluster-autoscaler`. Karpenter reacts within ~45s and can spin up `scraping` node capacity on-demand using a `NodePool` with SPOT + `m5.large`/`m5.xlarge` fallback.

---

## Ingress & Load Balancing

**Layer 4**: a public **AWS Network Load Balancer** is created by a `LoadBalancer` Service on the `ingress-nginx` controller. NLB → chosen for TCP pass-through, low latency, preserved client IP, and cost.

**Layer 7**: `ingress-nginx` handles host/path routing, gzip, rate limiting, and (optionally) TLS termination via ACM.

### Ingress rules

| Host / path | Backend Service | Purpose |
|---|---|---|
| `/` | `web-ui.app` (nginx static) | Web UI SPA (campaign management, prospect browsing, draft status, pipeline monitoring) |
| `/api/*` | `orchestrator.app` | All REST endpoints from README § API Endpoints |
| `/grafana/*` | `grafana.platform` | Metrics UI (IP-allowlisted at ingress level) |

### TLS
- Public cert via **AWS Certificate Manager** on the NLB target group (if a domain is provided).
- For demo without a domain: HTTP only at `http://<nlb-dns-name>/`. Document this and leave a TODO.

### Why NGINX and not ALB Ingress
- ALB Ingress creates one ALB per Ingress (cost + slower provisioning).
- NGINX in-cluster gives richer routing primitives (rewrite, auth-snippets, rate limit per path).
- User explicitly preferred nginx.

---

## Service Discovery & Service Mesh

### Discovery (CoreDNS-native)
Every service has a `ClusterIP` Kubernetes Service in namespace `app`:

```
orchestrator.app.svc.cluster.local
planning.app.svc.cluster.local
sourcing.app.svc.cluster.local
prospecting.app.svc.cluster.local
messaging.app.svc.cluster.local
web-ui.app.svc.cluster.local
mongodb.data.svc.cluster.local   # headless Service for StatefulSet
rabbitmq.data.svc.cluster.local  # if RabbitMQ runs in `data` (adjust namespace if you place it in `platform`)
```

Services **do not** call each other directly for business logic (per README) — they communicate via **RabbitMQ** queues. HTTP service-to-service calls only exist for health / admin purposes and for ingress-nginx → app pods.

### Service mesh: Linkerd
Linkerd injection is enabled for the `app` and `data` namespaces via the `linkerd.io/inject: enabled` namespace annotation. The control plane is installed via the `linkerd-control-plane` Helm chart.

**What Linkerd buys us:**
- **Automatic mTLS** between pods (zero config; identity via service-account certs).
- **Golden metrics** (success rate, RPS, latency p50/p95/p99) per pod and per edge, scraped into Prometheus.
- **Automatic retries** and timeouts via `ServiceProfile` CRDs for idempotent endpoints (orchestrator GETs, internal health checks).
- **Low overhead** — the proxy sidecar is ~5 MB Rust binary, ~1ms p99 tax.

**Why not Istio:** operational complexity is disproportionate for a demo.

---

## Sidecar Configuration

Only **one** sidecar is injected per app pod: `linkerd-proxy`. Everything else runs as a DaemonSet or separate Deployment to avoid per-pod cost.

Per app pod:

```
┌────────────── Pod ──────────────┐
│  linkerd-init (initContainer)   │  ← iptables rules to route traffic through proxy
│  app container                  │
│  linkerd-proxy (sidecar)        │  ← mTLS, retries, metrics
└─────────────────────────────────┘
```

Node-level collection (DaemonSet, not sidecar):
- **fluent-bit** tails `/var/log/containers/*.log` → CloudWatch Log Groups (one per namespace).

OpenTelemetry (optional, deferred): if distributed tracing is needed later, add an **OpenTelemetry Collector** as a DaemonSet and instrument services via OTEL SDKs. Not a sidecar either.

---

## Database (MongoDB) Deployment

### Topology (demo)
- Single MongoDB StatefulSet replica in namespace `data`.
- Headless Service `mongodb.data.svc.cluster.local:27017`.
- **PVC** on `gp3` StorageClass, 50 Gi, `ReclaimPolicy: Retain`.
- Pinned to AZ-a via `nodeAffinity` (EBS volumes are AZ-scoped).
- Tolerates the `workload=stateful:NoSchedule` taint.
- Authentication: `admin`/`root` password stored in Secrets Manager, synced in by External Secrets.

### Indexing (derived from README § NoSQL Storage Design)
```
db.companies.createIndex({ domain: 1 });
db.companies.createIndex({ campaign_ids: 1 });
db.companies.createIndex({ freshness_timestamp: 1 });
db.persons.createIndex({ company_id: 1 });
db.persons.createIndex({ email: 1 });
db.persons.createIndex({ freshness_timestamp: 1 });
db.email_drafts.createIndex({ campaign_id: 1, status: 1 });
```

### Vector search on `extra` keys (demo)
Embeddings for each `extra` key are stored alongside the document, e.g.:
```
companies.extra_embeddings = [
  { key: "annual_recurring_revenue", vector: [0.12, ...] },
  { key: "primary_use_case",         vector: [0.08, ...] }
]
```
The Prospecting Service performs brute-force cosine similarity in Python over a campaign's documents. At scale → migrate to **MongoDB Atlas Vector Search** or a dedicated **Qdrant** pod (this is called out in the Scale-Up Path).

### Backups
- Nightly `mongodump` CronJob writes `.gz` archives to an S3 bucket via IRSA.
- Retention 7 days. Not PITR — acceptable for demo.

### High availability (scale-up)
- Demo: 1 pod, 1 AZ.
- Scale-up: convert to a 3-member replica set across 3 AZs, each with its own EBS volume. The StatefulSet Helm chart supports this with a single values change.

---

## Message Queue (RabbitMQ)

**RabbitMQ is the only message broker in this design — Amazon SQS is not used.**

All application queues are **classic or quorum queues** (not FIFO in the SQS sense; order is best-effort per queue unless you adopt single-active-consumer or stream semantics later). Each application queue has a paired **dead-letter queue (DLQ)**; routing uses a dead-letter exchange with a retry count enforced in the consumer (or `x-death` headers for observability), analogous to SQS `maxReceiveCount: 5`.

| Queue (RabbitMQ name) | DLQ | Consumer timeout / note |
|---|---|---|
| `plan.requested` | `plan.requested.dlq` | 60s ack budget |
| `plan.ready` | `plan.ready.dlq` | 30s |
| `sourcing.requested` | `sourcing.requested.dlq` | **300s** (scraping can be slow) |
| `sourcing.completed` | `sourcing.completed.dlq` | 30s |
| `sourcing.partial` | `sourcing.partial.dlq` | 30s |
| `prospecting.requested` | `prospecting.requested.dlq` | 30s |
| `prospecting.completed` | `prospecting.completed.dlq` | 30s |
| `messaging.requested` | `messaging.requested.dlq` | **120s** (LLM latency + Draft API call) |
| `draft.written` | `draft.written.dlq` | 30s |
| `draft.failed` | `draft.failed.dlq` | 30s |
| `campaign.completed` | `campaign.completed.dlq` | 30s |

**Retired** (consequence of removing Review Service and Send Service): `review.requested`, `review.completed`, `send.requested`, `send.completed`, `send.failed`, `messaging.completed`.

**Access control:** use **RabbitMQ users and vhost permissions** (or Kubernetes Secrets mounted to each Deployment) so each service can only `configure|write|read` the exchanges and queues it needs — matching the publish/consume matrix in README § Message Queues. For Amazon MQ, place the broker in private subnets; for in-cluster RabbitMQ, restrict the management port to cluster-internal and use TLS where applicable.

---

## Secrets Management

- **Source of truth**: AWS Secrets Manager, one secret per credential.
- **In-cluster delivery**: `external-secrets-operator` watches `ExternalSecret` CRDs and materializes native Kubernetes `Secret` objects into the right namespace.
- **Authentication**: the operator uses an **IRSA**-bound service account, policy restricted to `secretsmanager:GetSecretValue` on `email-outreach/*`.

Secrets we provision:
| Name in Secrets Manager | Consumed by |
|---|---|
| `email-outreach/openai` | planning, messaging |
| `email-outreach/apollo` | sourcing |
| `email-outreach/hunter` | sourcing |
| `email-outreach/linkedin` | sourcing |
| `email-outreach/github` | sourcing |
| `email-outreach/email-oauth` (Gmail / Microsoft OAuth client credentials) | messaging |
| `email-outreach/mongodb-admin` | mongodb init, orchestrator, planning, sourcing, prospecting, messaging |

Each service pod also gets its **own IRSA role** where still relevant (S3 for Mongo backups, no queue IAM — **RabbitMQ** uses credentials from Kubernetes Secrets, optionally synced from Secrets Manager via External Secrets). Scope RabbitMQ usernames to least privilege per the publish/consume matrix.

---

## LLM Access Path (OpenAI) & Email Draft API

- Planning and Messaging services call `api.openai.com` via the single NAT Gateway.
- The OpenAI key is pulled from Secrets Manager at pod start (no env-var committed).
- The Messaging Service also calls **email provider Draft APIs** (Gmail `drafts.create`, Microsoft Graph `createDraft`) via NAT Gateway egress. OAuth tokens are pulled from Secrets Manager (`email-outreach/email-oauth`).
- No traffic is logged at the proxy; Linkerd sees only the outbound HTTPS destination count.
- **Scale-up option**: swap to Amazon Bedrock later and delete the NAT egress dependency for LLM traffic — pure code + IAM change, no infra rework.

---

## Observability

Hybrid stack, per your decision.

### Metrics (in-cluster)
- `kube-prometheus-stack` Helm chart deploys:
  - Prometheus (15d retention, 50 Gi gp3 PVC)
  - Alertmanager
  - Grafana (admin password from Secrets Manager)
  - `kube-state-metrics`, `node-exporter` DaemonSet
  - ServiceMonitors for Linkerd, NGINX, KEDA
- **Linkerd metrics** surfaced automatically (success rate, latency, RPS per edge).
- Grafana dashboards shipped: per-service golden signals + **RabbitMQ** queue depth (Prometheus `rabbitmq` exporter or KEDA / management metrics, depending on install).

### Logs (AWS-native)
- `fluent-bit` DaemonSet tails all pod logs.
- Routes to **CloudWatch Log Groups** `/eks/email-outreach/<namespace>` with 14-day retention.
- Structured JSON logs preserved; queryable via **CloudWatch Logs Insights**.

### Traces (deferred)
Not installed initially. Linkerd gives request-level metrics which cover 90% of the debugging need. If full traces are needed later → add OTEL collector DaemonSet + AWS X-Ray exporter.

### Alerts (starter set)
- `ingress-nginx` 5xx rate > 5% for 5m
- Any **RabbitMQ** DLQ with ready messages > 0 (exporter or management API → Prometheus alert or CloudWatch if using a sidecar/adapter)
- `mongodb` pod not ready for > 5m
- `keda-operator` errors
- Node group at max capacity + pending pods > 0 for 10m

---

## CI/CD and Container Registry

### Registry
- **ECR**, one repository per service, image scanning on push enabled, lifecycle policy keeps last 30 images.

### Image build
- Multi-stage Dockerfile per service; non-root user; distroless or Alpine base where feasible.
- Tags: `git-<short-sha>` and `env-<env>-<sha>`.

### Delivery pipeline
```
  git push
     │
     ▼
  GitHub Actions
  ├─ build + test
  ├─ docker build + push to ECR
  ├─ helm lint + template (dry run)
  └─ helm upgrade --install  <release> ./helm/charts/<service>  -f values-dev.yaml
                           --set image.tag=<sha>
                           --namespace app --atomic --wait
```

- **Secrets in CI**: AWS OIDC federation → short-lived credentials (no static keys).
- **Environments**: `dev` to start. `prod` is the same chart + a `values-prod.yaml` with higher replica counts, different node group sizes, and secret refs pointing at `email-outreach-prod/*` in Secrets Manager.
- **Rollbacks**: `helm rollback <release> <revision>` — two commands.

---

## Terraform Module Layout

```
terraform/
├── backend.tf                # S3 + DynamoDB state
├── versions.tf
├── providers.tf
├── variables.tf
├── outputs.tf
├── main.tf                   # wires modules together
├── environments/
│   ├── dev/
│   │   ├── main.tfvars
│   │   └── backend.tfvars
│   └── prod/
│       └── ...
└── modules/
    ├── network/              # VPC, subnets, IGW, NAT, VPC endpoints, SGs
    ├── eks/                  # cluster, OIDC provider, add-ons
    ├── node-groups/          # general + scraping + stateful (parameterized)
    ├── karpenter/            # IAM + helm release (optional, if using Karpenter)
    ├── ecr/                  # loop over list(services) → one repo each
    ├── rabbitmq/              # (optional) Amazon MQ for RabbitMQ in VPC, or empty if Helm-only
    ├── secrets/              # Secrets Manager secrets (empty shells, populated out-of-band)
    ├── iam-irsa/             # per-service IAM roles + trust policies for k8s SAs
    ├── s3-backup/            # bucket + lifecycle for Mongo backups + TF state
    ├── observability/        # CloudWatch log groups, metric filters, SNS topic, alarms
    └── route53/              # (optional) hosted zone + record for the NLB
```

### Module boundaries (why split this way)
- `network` is reusable for any future VPC-bound service (no EKS coupling).
- `eks` + `node-groups` are split so worker config can change without touching the control plane.
- `ecr`, `secrets` are list-driven — adding a new service = appending to one list. **RabbitMQ** topology (queues + DLQs) is defined as code (e.g. Helm values, `definitions.json` export, or operator CRDs), not a Terraform SQS module.
- `iam-irsa` enforces S3/Secrets/backup policies; **queue authorization is RabbitMQ-side** (users + vhost + permissions), plus Kubernetes network policies to the broker Service.

### State layout
- Single state file per environment, in S3 at `s3://email-outreach-tfstate/<env>/terraform.tfstate`.
- DynamoDB table `email-outreach-tf-lock` for state locking.

---

## Helm Chart Layout

```
deploy/
├── charts/
│   ├── orchestrator/         # per-service charts (Deployment, Service,
│   ├── planning/             # ServiceAccount, HPA/ScaledObject, ExternalSecret,
│   ├── sourcing/             # NetworkPolicy, PodDisruptionBudget, Ingress)
│   ├── prospecting/
│   ├── messaging/
│   └── web-ui/
├── umbrella/
│   └── email-outreach/       # umbrella chart depending on all service charts,
│                             # used as a single release in dev to deploy everything
└── platform/
    ├── ingress-nginx-values.yaml
    ├── linkerd-values.yaml
    ├── keda-values.yaml
    ├── external-secrets-values.yaml
    ├── cert-manager-values.yaml
    ├── kube-prometheus-stack-values.yaml
    ├── fluent-bit-values.yaml
    ├── mongodb-values.yaml   # bitnami/mongodb with our overrides
    └── rabbitmq-values.yaml  # bitnami/rabbitmq or cluster operator; queues align with README § Message Queues
```

**Chart contents (template names)** for each service chart:
- `deployment.yaml`
- `service.yaml` (ClusterIP)
- `serviceaccount.yaml`
- `hpa.yaml` or `scaledobject.yaml` (conditional on `values.scaler.type`)
- `externalsecret.yaml`
- `networkpolicy.yaml`
- `poddisruptionbudget.yaml`
- `ingress.yaml` (only for orchestrator and web-ui)
- `servicemonitor.yaml` (for Prometheus scraping)

---

## Scale-Up Path (Demo → Production)

Every demo-level shortcut below is a **single config change** away from production-grade:

| Today (demo) | Production move | Trigger |
|---|---|---|
| Single NAT Gateway in AZ-a | NAT per AZ | sustained egress > 50 Mbps OR need AZ-resilient outbound |
| MongoDB 1-node StatefulSet, AZ-a | 3-member replica set across 3 AZs | working set > 4 GiB OR need RPO < 1h |
| Embeddings inside Mongo | Qdrant StatefulSet or MongoDB Atlas Vector Search | `extra_embeddings` corpus > 1M vectors OR p95 search > 500ms |
| 2 AZs | 3 AZs | user-facing SLA commitments |
| t3.medium general group | m5.large/m5.xlarge on general | sustained CPU > 60% across nodes |
| `cluster-autoscaler` (if used) | Karpenter | scraping bursts want sub-minute node provisioning |
| OpenAI via NAT | Amazon Bedrock | data-residency / IAM scoping requirements |
| RabbitMQ classic queues | **Quorum queues** or **streams** for `messaging.requested` | strict ordering / replay requirements |
| HTTP only at NLB | ACM TLS + Route53 | custom domain acquired |
| CloudWatch logs | CloudWatch + optional Loki in-cluster for long-term cheap storage | log volume > 5 GB/day |
| Single-region | Multi-region active/passive | DR requirement |

---

## Rough Monthly Cost Estimate

Ballpark for the demo footprint, **us-west-2**, on-demand pricing, 24/7:

| Item | Qty | Approx $/mo |
|---|---|---|
| EKS control plane | 1 | 73 |
| `general` nodes (t3.medium, 2× at baseline) | 2 | 60 |
| `scraping` nodes (m5.large, 1× baseline) | 1 | 70 |
| `stateful` nodes (t3.medium, 1×) | 1 | 30 |
| NAT Gateway + egress (~50 GB/mo) | 1 | 40 |
| NLB | 1 | 20 |
| EBS gp3 (Mongo 50 GiB + Prom 50 GiB + misc 20 GiB) | ~120 GiB | 12 |
| RabbitMQ (in-cluster; no SQS) | — | $0 extra beyond node RAM/CPU; **Amazon MQ** is extra if you choose it |
| CloudWatch Logs (low volume) | — | ~5 |
| Secrets Manager (7 secrets) | 7 | 3 |
| ECR (~5 GiB) | — | ~1 |
| S3 (TF state + backups) | — | < 1 |
| Data transfer (OpenAI + email Draft API egress, small) | — | ~5 |
| **Total (demo)** | | **~$320 / month** |

Production footprint (3 AZs, replicated Mongo, HA NAT, ALB+NLB, 3× scraping nodes baseline) roughly **~$900–1,200/mo** before any LLM / third-party API costs.

---

## Open Items / Follow-Ups

These are intentionally unresolved and should be decided before first deploy:

1. **Custom domain + TLS**: do we acquire a domain for `*.email-outreach.<yours>.com`, or ship demo on raw NLB DNS (HTTP only)?
2. **Web UI auth**: the README states "no authentication required". For an open internet-facing NLB, even a simple IP allowlist at the nginx Ingress level is advisable — please confirm.
3. **Email account provider default**: the system writes drafts via Gmail API or Microsoft Graph. Which do we configure first? Gmail is the most common; Microsoft Graph is needed for Outlook/M365 users.
4. **OAuth flow for email account**: the Messaging Service needs OAuth tokens to write drafts. Decide: user-initiated OAuth consent flow in the Web UI at campaign creation time, or pre-provisioned service account tokens stored in Secrets Manager?
5. **SPOT instances for `scraping` group**: cost-saver, but requires idempotent scrape workers. Confirm scrapers are checkpointable before enabling.
6. **Karpenter vs. cluster-autoscaler**: Karpenter is strictly better for bursty scraping; confirm we adopt it from day one.
7. **Region**: `us-west-2` chosen as default. Confirm or change.
8. **GPU for LLM self-host**: ruled out for demo. Confirm we never revisit and stay on OpenAI/Bedrock.
9. **Web UI framework**: React + Vite is the usual default for a static SPA served by nginx — confirm or propose alternative (HTMX, SvelteKit static export, etc.).
