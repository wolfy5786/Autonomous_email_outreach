"""Dev helper — seed mock Prospecting+Sourcing data for a campaign.

Inserts the documents that Sourcing and Prospecting would normally produce —
companies, persons (POCs), hints — so the Messaging service can be developed
end-to-end before those upstream services exist. Also patches the campaign
with `config.email_account` if missing.

Workflow:
    # 1. Seed the campaign
    python src/local_infrastructure/scripts/seed_campaign.py --id c-demo-001
    # 2. Run real Planning to produce the plan_record
    python src/local_infrastructure/scripts/publish_plan_requested.py --campaign-id c-demo-001
    # 3. Seed mock prospecting data:
    python src/local_infrastructure/scripts/seed_prospecting_mock.py --campaign-id c-demo-001
    # 4. Use the printed POC IDs:
    python src/local_infrastructure/scripts/publish_messaging_requested.py \
        --campaign-id c-demo-001 --poc-id <printed>

Idempotent — re-running with the same campaign_id overwrites prior mock docs.

When Prospecting + Sourcing land for real, this script becomes obsolete; the
data it inserts will be produced by the actual services. The shape it inserts
IS the contract those services must honor (see ``messaging.schemas.PocRecord``,
``CompanyContext``, ``HintContext``).
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


MOCK_COMPANIES = [
    {
        "name": "Acme Observability",
        "domain": "acme.com",
        "industry": "B2B SaaS / DevTools",
        "description": "Internal developer platform with Kubernetes-native CI/CD.",
        "icp_fit_score": 0.91,
    },
    {
        "name": "BetaScale",
        "domain": "betascale.io",
        "industry": "B2B SaaS / Infra",
        "description": "Multi-tenant analytics infra for fintechs.",
        "icp_fit_score": 0.78,
    },
]

MOCK_POCS = {
    "Acme Observability": [
        {"first_name": "Sam", "last_name": "Lee",
         "title": "VP Engineering", "seniority": "vp", "department": "engineering",
         "email": "sam@acme.com", "icp_poc_score": 0.88},
        {"first_name": "Riya", "last_name": "Patel",
         "title": "Head of Platform", "seniority": "director", "department": "platform",
         "email": "riya@acme.com", "icp_poc_score": 0.83},
    ],
    "BetaScale": [
        {"first_name": "Jordan", "last_name": "Kim",
         "title": "Director of Infrastructure", "seniority": "director",
         "department": "infrastructure",
         "email": "jordan@betascale.io", "icp_poc_score": 0.72},
    ],
}

MOCK_HINTS = {
    "Acme Observability": [
        {"category": "funding",
         "summary": "Raised $20M Series B in Mar 2026",
         "source_url": "https://techcrunch.com/acme-series-b",
         "relevance_score": 0.95},
        {"category": "hiring",
         "summary": "Hiring 4 platform engineers (Greenhouse JD posted last 14 days)",
         "source_url": "https://acme.com/careers",
         "relevance_score": 0.83},
        {"category": "product_launch",
         "summary": "Shipped multi-region cluster autoscaler in Q1",
         "source_url": "https://acme.com/blog/multi-region",
         "relevance_score": 0.74},
    ],
    "BetaScale": [
        {"category": "news",
         "summary": "Featured in Crunchbase Pulse for fintech infra growth",
         "source_url": "https://news.crunchbase.com/betascale",
         "relevance_score": 0.62},
        {"category": "hiring",
         "summary": "Two senior backend roles open",
         "source_url": "https://betascale.io/careers",
         "relevance_score": 0.55},
    ],
}


async def _ensure_email_account(db, campaign_id: str, credentials_ref: str) -> None:
    doc = await db["campaigns"].find_one({"_id": campaign_id})
    if doc is None:
        doc = await db["campaigns"].find_one({"id": campaign_id})
    if doc is None:
        raise SystemExit(
            f"campaign {campaign_id} not found — run seed_campaign.py first."
        )
    config = doc.get("config") or {}
    if not config.get("email_account"):
        config["email_account"] = {
            "provider": "gmail",
            "credentials_ref": credentials_ref,
        }
        await db["campaigns"].update_one(
            {"_id": doc.get("_id", doc.get("id"))},
            {"$set": {"config": config}},
        )
        print(
            f"  patched campaign with config.email_account.credentials_ref={credentials_ref!r}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument(
        "--credentials-ref",
        default="alice",
        help=(
            "Stored on campaign.config.email_account.credentials_ref. The credentials "
            "resolver maps this to GMAIL_REFRESH_TOKEN_<REF>."
        ),
    )
    parser.add_argument(
        "--mongo-url",
        default=os.getenv("MONGO_URL", "mongodb://localhost:27017"),
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "email_outreach"))
    args = parser.parse_args()

    client = AsyncIOMotorClient(args.mongo_url)
    try:
        db = client[args.db]
        await _ensure_email_account(db, args.campaign_id, args.credentials_ref)

        printed_pocs: list[tuple[str, str, str]] = []  # (company, poc_id, email)

        for ci, company_spec in enumerate(MOCK_COMPANIES):
            company_id = f"{args.campaign_id}-co-{ci}"
            company_doc = {
                "_id": company_id, "id": company_id,
                "name": company_spec["name"],
                "domain": company_spec["domain"],
                "industry": company_spec["industry"],
                "description": company_spec["description"],
                "icp_fit_score": company_spec["icp_fit_score"],
                "data_completeness": 0.85,
                "freshness_timestamp": _utcnow_iso(),
                "scrape_mode_last": "all",
                "campaign_ids": [args.campaign_id],
                "extra": {},
                "provenance": {},
            }
            await db["companies"].replace_one({"_id": company_id}, company_doc, upsert=True)
            print(f"  upserted company {company_spec['name']!r} id={company_id}")

            for pi, poc_spec in enumerate(MOCK_POCS[company_spec["name"]]):
                poc_id = f"{company_id}-poc-{pi}"
                poc_doc = {
                    "_id": poc_id, "id": poc_id,
                    "company_id": company_id,
                    **poc_spec,
                    "email_verified": True,
                    "freshness_timestamp": _utcnow_iso(),
                    "extra": {},
                }
                await db["persons"].replace_one({"_id": poc_id}, poc_doc, upsert=True)
                printed_pocs.append((company_spec["name"], poc_id, poc_spec["email"]))

            for hi, hint_spec in enumerate(MOCK_HINTS[company_spec["name"]]):
                hint_id = f"{company_id}-hint-{hi}"
                hint_doc = {
                    "_id": hint_id, "id": hint_id,
                    "company_id": company_id,
                    "campaign_id": args.campaign_id,
                    "source_name": "mock_seeder",
                    "source_type": "scrape",
                    "discovered_at": _utcnow_iso(),
                    "extra": {},
                    **hint_spec,
                }
                await db["hints"].replace_one({"_id": hint_id}, hint_doc, upsert=True)

        total_hints = sum(len(v) for v in MOCK_HINTS.values())
        print()
        print(
            f"Done. Seeded {len(MOCK_COMPANIES)} companies, "
            f"{len(printed_pocs)} POCs, {total_hints} hints "
            f"for campaign {args.campaign_id}."
        )
        print()
        print("POCs available for messaging.requested:")
        for company, poc_id, email in printed_pocs:
            print(f"  poc_id={poc_id}  email={email}  company={company}")
        print()
        print("Next step:")
        print("  python src/local_infrastructure/scripts/publish_messaging_requested.py \\")
        print(f"    --campaign-id {args.campaign_id} --poc-id <pick-one-above>")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
