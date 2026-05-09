# Repository Structure

```
email_outreach/
│
├── cloud_terraform/                        # All cloud infrastructure (Terraform)
│   ├── backend.tf                          # S3 + DynamoDB state
│   ├── main.tf                             # wires modules together
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   ├── providers.tf
│   ├── environments/
│   │   ├── dev/
│   │   └── prod/
│   └── modules/
│       ├── network/                        # VPC, subnets, IGW, NAT, VPC endpoints, SGs
│       ├── eks/                            # EKS cluster, OIDC provider, add-ons
│       ├── node-groups/                    # general / scraping / stateful node groups
│       ├── karpenter/                      # IAM + Helm release for Karpenter autoscaler
│       ├── ecr/                            # ECR repo per service
│       ├── rabbitmq/                       # (optional) Amazon MQ for RabbitMQ, or empty if Helm-only
│       ├── secrets/                        # Secrets Manager shells (populated out-of-band)
│       ├── iam-irsa/                       # per-service IAM roles + trust policies for k8s SAs
│       ├── s3-backup/                      # TF state bucket + Mongo backup bucket
│       ├── observability/                  # CloudWatch log groups, metric filters, SNS, alarms
│       └── route53/                        # (optional) hosted zone + NLB record
│
├── deploy/                                 # Helm charts for EKS deployment
│   ├── charts/
│   │   ├── orchestrator/
│   │   ├── planning/
│   │   ├── sourcing/
│   │   ├── prospecting/
│   │   ├── messaging/
│   │   └── web-ui/
│   ├── umbrella/
│   │   └── email-outreach/                 # single umbrella release for dev
│   └── platform/                           # third-party Helm values overrides
│       ├── kube-prometheus-stack-values.yaml   # Prometheus + Grafana + Alertmanager
│       ├── fluent-bit-values.yaml              # log shipping → CloudWatch
│       ├── linkerd-values.yaml                 # service mesh / mTLS
│       ├── keda-values.yaml                    # queue-depth autoscaler
│       ├── external-secrets-values.yaml        # Secrets Manager → k8s Secrets
│       └── mongodb-values.yaml                 # Bitnami MongoDB StatefulSet overrides
│
├── src/
│   ├── local_infrastructure/               # Local dev infrastructure
│   │   ├── k8/                             # Kubernetes manifests for local dev cluster
│   │   ├── rabbit_mq/                      # RabbitMQ adapter (dev message broker)
│   │   ├── factory/                        # Broker factory — abstracts broker via BROKER_TYPE env
│   │   └── observability/                  # Local Prometheus + Grafana + RabbitMQ exporter configs
│   │
│   ├── shared/                             # Shared code used by all services
│   │   ├── models/                         # Mongoose schemas (Campaign, EmailDraft)
│   │   └── types/                          # TypeScript types, queue payloads, pipeline state
│   │
│   ├── orchestrator/                       # Entry point, pipeline coordinator, all API endpoints
│   ├── planning/                           # ICP analysis → Plan Document (LLM)
│   ├── sourcing/                           # Data mining — Layer 1 APIs + Layer 2 headless browsers
│   ├── prospecting/                        # ICP scoring + semantic search on extra fields
│   ├── messaging/                          # Draft generation (LLM) + write draft to user email account
│   └── web-ui/                             # Static SPA — campaign mgmt, prospects, draft status, pipeline monitoring
│
├── README.md
├── cloud_INFRASTRUCTURE.md
├── messaging_infrastructure.md
└── Repository_structure.md
```

## Notes

**Services** (`src/<service>/`)
All inter-service communication is async via message queues — services never call each other directly.
The Review Service is removed; its API endpoints are absorbed into `orchestrator`.

**Messaging** (`src/local_infrastructure/`)
Local dev uses **RabbitMQ** (`rabbit_mq/`). Production uses **AWS SQS** (or Amazon MQ for RabbitMQ).
The broker factory (`factory/`) switches via the `BROKER_TYPE` env var — service code is broker-agnostic.

**Observability**
- *Cloud*: `cloud_terraform/modules/observability/` provisions CloudWatch log groups, SNS alarms, and metric filters. `deploy/platform/kube-prometheus-stack-values.yaml` + `fluent-bit-values.yaml` deploy Prometheus/Grafana and log shipping in-cluster.
- *Local*: `src/local_infrastructure/observability/` holds Prometheus scrape configs, Grafana dashboards, and a RabbitMQ exporter for the local dev environment.

**Helm charts** (`deploy/`)
One chart per service with `deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `hpa.yaml`/`scaledobject.yaml`, `externalsecret.yaml`, and `servicemonitor.yaml`. The `umbrella/` chart deploys all services in a single `helm upgrade` for dev.
