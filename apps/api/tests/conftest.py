import asyncio
import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db

def _get_nested(doc: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    curr = doc
    for p in parts:
        if isinstance(curr, dict):
            curr = curr.get(p)
        else:
            return None
    return curr


class InMemoryCollection:
    def __init__(self):
        self.docs: Dict[str, Dict[str, Any]] = {}

    async def find_one(self, query: Dict[str, Any]):
        for doc in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "$or":
                    or_match = any(
                        all(_get_nested(doc, sub_k) == sub_v for sub_k, sub_v in sub_q.items())
                        for sub_q in v
                    )
                    if not or_match:
                        match = False
                        break
                elif isinstance(v, dict) and "$nin" in v:
                    if _get_nested(doc, k) in v["$nin"]:
                        match = False
                        break
                elif _get_nested(doc, k) != v:
                    match = False
                    break
            if match:
                return doc.copy()
        return None

    async def insert_one(self, doc: Dict[str, Any]):
        doc_id = str(doc.get("_id"))
        self.docs[doc_id] = doc.copy()
        return type("InsertResult", (), {"inserted_id": doc_id})()

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        doc = await self.find_one(query)
        if doc:
            doc_id = str(doc["_id"])
            if "$set" in update:
                for k, v in update["$set"].items():
                    self.docs[doc_id][k] = v
            return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()

    async def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        count = 0
        for doc_id, doc in list(self.docs.items()):
            match = True
            for k, v in query.items():
                if k == "$or":
                    or_match = any(
                        all(doc.get(sub_k) == sub_v for sub_k, sub_v in sub_q.items())
                        for sub_q in v
                    )
                    if not or_match:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    for set_k, set_v in update["$set"].items():
                        self.docs[doc_id][set_k] = set_v
                count += 1
        return type("UpdateResult", (), {"modified_count": count})()

    async def delete_one(self, query: Dict[str, Any]):
        doc = await self.find_one(query)
        if doc:
            doc_id = str(doc["_id"])
            del self.docs[doc_id]
            return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, query: Dict[str, Any]):
        to_delete = []
        for doc_id, doc in self.docs.items():
            match = True
            for k, v in query.items():
                if k == "$or":
                    or_match = any(
                        all(doc.get(sub_k) == sub_v for sub_k, sub_v in sub_q.items())
                        for sub_q in v
                    )
                    if not or_match:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                to_delete.append(doc_id)
        for doc_id in to_delete:
            del self.docs[doc_id]
        return type("DeleteResult", (), {"deleted_count": len(to_delete)})()

    def find(self, query: Dict[str, Any]):
        class Cursor:
            def __init__(self, docs_list):
                self._docs = docs_list
            async def to_list(self, length: int = 1000):
                return [d.copy() for d in self._docs[:length]]
        
        matched = []
        for doc in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "$or":
                    or_match = any(
                        all(doc.get(sub_k) == sub_v for sub_k, sub_v in sub_q.items())
                        for sub_q in v
                    )
                    if not or_match:
                        match = False
                        break
                elif isinstance(v, dict) and "$nin" in v:
                    if doc.get(k) in v["$nin"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(doc)
        return Cursor(matched)

class InMemoryDatabase:
    def __init__(self):
        self.collections: Dict[str, InMemoryCollection] = {}

    def __getattr__(self, name: str) -> InMemoryCollection:
        if name not in self.collections:
            self.collections[name] = InMemoryCollection()
        return self.collections[name]

    def __getitem__(self, name: str) -> InMemoryCollection:
        return getattr(self, name)

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    test_db = InMemoryDatabase()
    monkeypatch.setattr("app.db.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.auth.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.users.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.connections.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.grants.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.state.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.cards.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.ai.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.scenarios.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.notifications.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.reminders.get_db", lambda: test_db)
    monkeypatch.setattr("app.routers.dev.get_db", lambda: test_db)
    monkeypatch.setattr("app.workflows.activities.get_db", lambda: test_db)
    app.dependency_overrides[get_db] = lambda: test_db
    yield test_db
    app.dependency_overrides.pop(get_db, None)
