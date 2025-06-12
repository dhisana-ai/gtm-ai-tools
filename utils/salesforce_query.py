"""Run a natural language query against Salesforce using LLM assistance."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, List

from simple_salesforce import Salesforce

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - tests use stub
    from pydantic_stub import BaseModel

from utils.extract_from_webpage import _get_structured_data_internal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SoqlQuery(BaseModel):
    soql: str


class QueryResult(BaseModel):
    results: List[dict[str, Any]]


async def run_salesforce_query(natural_query: str) -> dict:
    """Return results for ``natural_query`` from Salesforce."""

    if not natural_query.strip():
        return {"error": "The query string cannot be empty"}

    prompt = (
        "Convert the following natural language request into a Salesforce SOQL "
        "query. Return JSON matching this schema:\n"
        f"{json.dumps(SoqlQuery.model_json_schema(), indent=2)}\n\n"
        f"Request:\n{natural_query}"
    )
    soql_data, status = await _get_structured_data_internal(prompt, SoqlQuery)
    if status != "SUCCESS" or soql_data is None:
        return {"error": "Failed to generate SOQL query"}

    soql = soql_data.soql

    instance_url = os.getenv("SALESFORCE_INSTANCE_URL")
    access_token = os.getenv("SALESFORCE_ACCESS_TOKEN")
    username = os.getenv("SALESFORCE_USERNAME")
    password = os.getenv("SALESFORCE_PASSWORD")
    security_token = os.getenv("SALESFORCE_SECURITY_TOKEN")
    domain = os.getenv("SALESFORCE_DOMAIN", "login")

    if instance_url and access_token:
        sf = Salesforce(instance_url=instance_url, session_id=access_token)
    elif username and password and security_token:
        sf = Salesforce(
            username=username,
            password=password,
            security_token=security_token,
            domain=domain,
        )
    else:
        return {"error": "Salesforce credentials not found in environment variables"}

    try:
        raw = sf.query_all(soql)
    except Exception as exc:  # pragma: no cover - network failures
        logger.exception("Salesforce query failed")
        return {"error": f"Query failed: {exc}"}

    result_prompt = (
        "Convert the following Salesforce response dictionary into a JSON object "
        "with key 'results' containing an array of records. Return JSON matching "
        f"this schema:\n{json.dumps(QueryResult.model_json_schema(), indent=2)}\n\n"
        f"Response:\n{json.dumps(raw)}"
    )
    parsed, status = await _get_structured_data_internal(result_prompt, QueryResult)
    if status != "SUCCESS" or parsed is None:
        return {"error": "Failed to parse query results"}

    return json.loads(parsed.model_dump_json())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a natural language Salesforce query")
    parser.add_argument("query", help="Natural language query")
    args = parser.parse_args()

    result = asyncio.run(run_salesforce_query(args.query))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
