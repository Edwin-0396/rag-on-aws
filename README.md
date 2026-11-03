# RAG on AWS — production-grade retrieval-augmented generation

A question-answering API over your own documents, built the way a DevOps engineer ships it:
containerized, provisioned with Terraform, running on EKS with autoscaling, and deployed
through a GitHub Actions pipeline using OIDC (no long-lived AWS keys).

## Architecture
- **App**: FastAPI · sentence-transformers embeddings · ChromaDB vector store · Claude as the LLM
- **Infra**: Terraform → VPC, EKS (managed node group), ECR with image scanning
- **Runtime**: Kubernetes Deployment + Service + HPA, health probes, secrets for the API key
- **CI/CD**: test → build → push to ECR → rolling deploy to EKS

## Run locally
    pip install -r app/requirements.txt
    export ANTHROPIC_API_KEY=... API_TOKEN=$(openssl rand -hex 24)
    CHROMA_PATH=./data uvicorn app.main:app --reload
    curl -X POST localhost:8000/ingest -H "Authorization: Bearer $API_TOKEN" -H 'content-type: application/json' -d '{"id":"runbook","text":"..."}'
    curl -X POST localhost:8000/ask -H "Authorization: Bearer $API_TOKEN" -H 'content-type: application/json' -d '{"question":"How do I roll back?"}'

## Deploy
    cd terraform && terraform init && terraform apply
    kubectl create namespace rag
    kubectl -n rag create secret generic rag-secrets \
      --from-literal=anthropic-api-key=... --from-literal=api-token=$(openssl rand -hex 24)
    # set AWS_ROLE_ARN secret in GitHub, push to main

## Best practices applied
- **Security**: OIDC deploy role scoped to `main` (no static keys), least-privilege IAM, bearer-token auth on write/query endpoints, non-root container with read-only root FS and dropped capabilities, immutable ECR tags with scan-on-push, Trivy gate in CI, EKS audit logs, API endpoint restricted by CIDR.
- **Reliability**: startup/readiness/liveness probes, persistent EBS volume for the vector store, LLM timeouts and retries, rollout status gate.
- **Delivery**: lint + unit tests + `terraform fmt/validate` + image scan on every PR; deploy only from `main` behind a GitHub `production` environment; concurrency control.
- **Cost**: single NAT gateway, ECR lifecycle (keep last 10 images), `terraform destroy` after demos.

## Roadmap
- Swap ChromaDB for a managed store (OpenSearch / pgvector on RDS) for persistence across pods
- Retrieval evaluation set and CI gate on answer quality
- Observability: latency, token cost and retrieval hit-rate dashboards
