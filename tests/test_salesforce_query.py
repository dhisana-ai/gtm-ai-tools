import sys
import types
import asyncio

# create dummy simple_salesforce module before importing target
sf_mod = types.ModuleType("simple_salesforce")

class DummySF:
    def __init__(self, *args, **kwargs):
        self.queries = []
    def query_all(self, soql):
        self.queries.append(soql)
        return {"records": [{"Name": "Acme"}]}

sf_mod.Salesforce = DummySF
sys.modules["simple_salesforce"] = sf_mod

from utils import salesforce_query as mod


async def fake_structured(prompt: str, model):
    if model is mod.SoqlQuery:
        return mod.SoqlQuery(soql="SELECT Name FROM Account"), "SUCCESS"
    return mod.QueryResult(results=[{"Name": "Acme"}]), "SUCCESS"


def test_run_salesforce_query(monkeypatch):
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_structured)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.run_salesforce_query("list accounts"))
    assert result["results"][0]["Name"] == "Acme"
