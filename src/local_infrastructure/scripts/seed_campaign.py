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
    "industry": "Enterprise software & internal platforms",
    "employee_range": [50, 500],
    "stack_includes": ["Java", "JDBC", "Spring", "Spring Boot", "Maven/Gradle"],
    "geography": ["United States"],
    "pain": "Need a software engineer strong in Java with JDBC, Spring, and common Java frameworks, with about three years of shipping experience.",
}

SAMPLE_PRODUCT = {
    "name": "Mid-level Java backend engineer (~3 YOE)",
    "value_prop": "Java developer with roughly three years building and maintaining services using JDBC for data access, Spring/Spring Boot, and familiar supporting frameworks in typical enterprise stacks.",
    "pricing": "full-time or contract-to-hire",
    "differentiators": [
        "JDBC and relational persistence",
        "Spring ecosystem (Boot, MVC, Data)",
        "broad Java framework literacy beyond a single stack",
    ],
}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="c-demo-001")
    parser.add_argument("--name", default="Demo Kubernetes platforms")
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
