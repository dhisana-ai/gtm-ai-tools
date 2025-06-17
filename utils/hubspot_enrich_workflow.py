#!/usr/bin/env python3
"""
- Reads contacts from HubSpot
- Researches each lead and their company using Serper.dev and OpenAI
- Summarizes the research
- Creates a note in HubSpot for each contact
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv
from typing import List, Dict
import sys
sys.path.append("./utils")
from hubspot_add_note import add_note

load_dotenv()

HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

HUBSPOT_BASE_URL = "https://api.hubapi.com"
SERPER_BASE_URL = "https://google.serper.dev/search"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

HEADERS_HUBSPOT = {"Authorization": f"Bearer {HUBSPOT_API_KEY}", "Content-Type": "application/json"}
HEADERS_SERPER = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
HEADERS_OPENAI = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

async def fetch_contacts(limit=1) -> List[Dict]:
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts?limit={limit}&sort=-createdAt"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS_HUBSPOT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

async def search_serper(query: str) -> str:
    payload = {"q": query}
    async with httpx.AsyncClient() as client:
        resp = await client.post(SERPER_BASE_URL, headers=HEADERS_SERPER, json=payload)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("organic", [])
        summary = "\n".join([f"{r.get('title')}: {r.get('snippet')}" for r in results[:3]])
        return summary

async def summarize_with_openai(prompt: str) -> str:
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that summarizes research about leads for CRM enrichment."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 256
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(OPENAI_API_URL, headers=HEADERS_OPENAI, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

async def create_hubspot_note_v3_backup(contact_id: str, summary: str):
    url = f"{HUBSPOT_BASE_URL}/engagements/v1/engagements"
    payload = {
        "engagement": {
            "active": True,
            "type": "NOTE"
        },
        "associations": {
            "contactIds": [int(contact_id)]
        },
        "metadata": {
            "body": summary
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=HEADERS_HUBSPOT, json=payload)
        resp.raise_for_status()
        return resp.json()

async def enrich_and_update_contacts():
    contacts = await fetch_contacts(limit=1)
    for contact in contacts:
        contact_id = contact["id"]
        props = contact.get("properties", {})
        name = props.get("firstname", "") + " " + props.get("lastname", "")
        company = props.get("company", "")
        phone = props.get("phone", "")
        email = props.get("email", "")

        linkedin_url = (
            props.get("linkedinurl")
            or props.get("linkedin_url")
            or props.get("linkedin")
            or props.get("linkedin_profile")
            or ""
        )
        print(f"Contact ID: {contact_id}, Name: {name}, Company: {company}, Email: {email}, Phone: {phone}, LinkedIn: {linkedin_url}")
        if not name.strip():
            print(f"Skipping contact with ID {contact_id} (no name or possibly deleted).")
            continue

        search_query = f"{name} {company} {linkedin_url} {phone} {email}".strip()
        serper_summary = await search_serper(search_query)
        prompt = (
            f"Research summary for {name} (Company: {company}, Email: {email}, Phone: {phone}, LinkedIn: {linkedin_url}):\n"
            f"{serper_summary}\n\n"
            "Summarize the most relevant information for CRM enrichment, including any insights from the LinkedIn profile, phone number, or email if available."
        )
        summary = await summarize_with_openai(prompt)
        print(f"[SUMMARY] {summary}")
        try:
            result = await add_note(contact_id, summary)
            print(f"[INFO] Note created in HubSpot for {name}. Result: {result}")
        except Exception as e:
            print(f"[ERROR] Failed to create note for {name} (ID: {contact_id}): {e}")

if __name__ == "__main__":
    asyncio.run(enrich_and_update_contacts()) 