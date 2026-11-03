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
    export ANTHROPIC_API_KEY=...
    CHROMA_PATH=./data uvicorn app.main:app --reload
    curl -X POST localhost:8000/ingest -H 'content-type: application/json' -d '{"id":"runbook","text":"..."}'
    curl -X POST localhost:8000/ask -H 'content-type: application/json' -d '{"question":"How do I roll back?"}'

## Deploy
    cd terraform && terraform init && terraform apply
    kubectl create secret generic llm-secrets --from-literal=anthropic-api-key=...
    # set AWS_ROLE_ARN secret in GitHub, push to main

## Roadmap
- Swap ChromaDB for a managed store (OpenSearch / pgvector on RDS) for persistence across pods
- Retrieval evaluation set and CI gate on answer quality
- Observability: latency, token cost and retrieval hit-rate dashboards
