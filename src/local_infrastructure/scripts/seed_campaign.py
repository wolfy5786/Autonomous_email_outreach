"""Dev helper — seed a sample campaign into MongoDB.

    python src/local_infrastructure/scripts/seed_campaign.py --id c-demo-001
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

SAMPLE_ICP = {
    "industry": "Seed–Series B teams shipping customer-facing LLM copilots and multi-step agents over messy enterprise knowledge — hybrid RAG (vector + BM25) across Confluence/SharePoint/Notion/Snowflake exports, tool-calling into internal REST/GraphQL, per-tenant prompt + router + model profiles (frontier APIs and self-hosted vLLM), and contracts that mention groundedness, refusal behavior, and p95 latency SLOs",
    "employee_range": [20, 400],
    "stack_includes": [
        "Orchestration in Python or TypeScript (LangGraph, Temporal, or bespoke state machines) with retries, idempotent tools, and per-session token budgets",
        "Vector stores and search (Pinecone, Weaviate, pgvector) plus embedding pipelines, chunking policies, and rerankers tuned per customer vertical",
        "Inference gateways with routing, caching, JSON-mode guards, and shadowing of new prompts/models before full rollout",
        "Eval and observability hooks in CI (golden sets, pairwise judges, offline regression gates) alongside classic APM for the non-LLM surface area",
    ],
    "geography": ["United States", "Canada", "United Kingdom"],
    "pain": "Shipping near-daily prompt, router, and retrieval changes without silent regressions — retrieval drift that drops NDCG overnight, tool-policy escapes, cost spikes from unbounded context, and buyer-driven requests for reproducible eval reports, trace-level provenance for bad answers, and evidence that red-team suites actually gate prod.",
    "additional_comment": "Prefer teams already running eval gates in CI; exclude pure chatbot wrappers with no retrieval.",
}

SAMPLE_PRODUCT = {
    "name": "Langfuse",
    "value_prop": "Open-source LLM engineering platform for tracing, evals, datasets, and prompt/version management — one place to debug multi-step agents, score production traffic, compare experiments, and show buyers how quality and safety checks map to live traces instead of ad-hoc notebooks and spreadsheets.",
    "pricing": "Cloud tiers (usage-based on traces and events) plus self-hosted / enterprise plans for VPC deploys, SSO, and support SLAs",
    "differentiators": [
        "Trace-first UX that stays usable when graphs branch ( tools, parallel calls, nested spans ) rather than flat chat logs",
        "Evals and datasets tied to the same IDs as production traces so regressions are bisectable to a prompt, retriever version, or model swap",
        "Self-hosting path for teams blocked from SaaS observability vendors but still needing collaboration across ML, backend, and product on one audit trail",
    ],
}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="c-demo-002")
    parser.add_argument("--name", default="Arjun")
    parser.add_argument(
        "--mongo-url", default=os.getenv("MONGO_URL", "mongodb://localhost:27017")
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "email_outreach"))
    args = parser.parse_args()

    client = AsyncIOMotorClient(args.mongo_url)
    try:
        db = client[args.db]
        doc = {
            "_id": args.id,
            "id": args.id,
            "name": args.name,
            "icp": SAMPLE_ICP,
            "product_profile": SAMPLE_PRODUCT,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db["campaigns"].replace_one({"_id": args.id}, doc, upsert=True)
        print(f"seeded campaign {args.id} into {args.db}.campaigns")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
