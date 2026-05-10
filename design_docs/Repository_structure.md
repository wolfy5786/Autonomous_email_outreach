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
│       ├── rabbitmq/                        # (optional) Amazon MQ for RabbitMQ, or empty if Helm-only
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
│   │   ├── rabbit_mq/                      # Local RabbitMQ (Docker) — same broker model as prod
│   │   └── observability/                  # Local Prometheus + Grafana + RabbitMQ exporter configs
│   │
│   ├── orchestrator/                       # Entry point, pipeline coordinator, all API endpoints
│   ├── planning/                           # ICP analysis → Plan Document (LLM)
│   ├── sourcing/                           # Discovery + enrichment (see data_sourcing_map.md)
│   ├── prospecting/                        # ICP scoring + semantic search on extra fields
│   ├── messaging/                          # Draft generation (LLM) + write draft to user email account
│   └── web-ui/                             # Static SPA — campaign mgmt, prospects, draft status, pipeline monitoring
│
├── README.md
├── cloud_INFRASTRUCTURE.md
└── Repository_structure.md
```

## Notes

**Services** (`src/<service>/`)  
All inter-service communication is async via message queues — services never call each other directly.  
The Review Service and Send Service are removed. Review-related API endpoints are absorbed into `orchestrator`. The Messaging Service writes drafts directly to the user's email account (Gmail / Microsoft) and marks the task completed.

**Messaging** (`src/local_infrastructure/`)  
Local dev runs **RabbitMQ** in Docker (`rabbit_mq/`). Production uses **RabbitMQ** in-cluster on EKS or **Amazon MQ for RabbitMQ** — the same AMQP topology and queue names as documented in the root `README.md`.

**Observability**  
- *Cloud*: `cloud_terraform/modules/observability/` provisions CloudWatch log groups, SNS alarms, and metric filters. `deploy/platform/kube-prometheus-stack-values.yaml` + `fluent-bit-values.yaml` deploy Prometheus/Grafana and log shipping in-cluster.  
- *Local*: `src/local_infrastructure/observability/` holds Prometheus scrape configs, Grafana dashboards, and a RabbitMQ exporter for the local dev environment.

**Helm charts** (`deploy/`)  
One chart per service with `deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `hpa.yaml`/`scaledobject.yaml`, `externalsecret.yaml`, and `servicemonitor.yaml`. The `umbrella/` chart deploys all services in a single `helm upgrade` for dev.
