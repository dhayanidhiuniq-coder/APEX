"""Focused tests for the Supabase RLS request context.

No network or live database is used. SQLite in-memory sessions drive
SQLAlchemy's real transaction events while the PostgreSQL-specific setup
statements are recorded or replaced with fakes.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from apex_backend.api.v1 import projects as projects_routes
from apex_backend.db import rls
from apex_backend.db.config import DatabaseConfigurationError
from apex_backend.models.identity import Identity

USER_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")
OTHER_USER_ID = uuid.UUID("99999999-8888-4777-8666-555555555555")


class FakeResult:
    def __init__(self) -> None:
        self.scalar_one_calls = 0

    def scalar_one(self) -> str:
        self.scalar_one_calls += 1
        return "1"


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str] | None]] = []

    def execute(self, statement: object, parameters: dict[str, str]) -> FakeResult:
        self.calls.append(("execute", str(statement), dict(parameters)))
        return FakeResult()

    def exec_driver_sql(self, statement: str) -> None:
        self.calls.append(("exec_driver_sql", statement, None))


def _session() -> Session:
    return Session(create_engine("sqlite://"))


def _record_setup(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    applied: list[str] = []

    def _record(_connection: object, claims: str) -> None:
        applied.append(claims)

    monkeypatch.setattr(rls, "_establish_transaction_context", _record)
    return applied


def test_claims_are_built_only_from_the_verified_subject() -> None:
    identity = rls.build_rls_identity(USER_ID)

    assert identity.user_id == USER_ID
    assert json.loads(identity.claims) == {
        "aud": "authenticated",
        "role": "authenticated",
        "sub": str(USER_ID),
    }
    assert "email" not in json.loads(identity.claims)


def test_non_uuid_subject_cannot_build_rls_claims() -> None:
    with pytest.raises(rls.RLSContextError):
        rls.build_rls_identity("not-a-uuid")  # type: ignore[arg-type]


def test_setup_uses_bound_claims_then_the_fixed_role() -> None:
    identity = rls.build_rls_identity(USER_ID)
    connection = RecordingConnection()

    rls._establish_transaction_context(connection, identity.claims)  # type: ignore[arg-type]

    assert [call[0] for call in connection.calls] == [
        "execute",
        "exec_driver_sql",
    ]
    _, statement, parameters = connection.calls[0]
    assert "set_config('request.jwt.claims', :claims, true)" in statement
    assert parameters == {"claims": identity.claims}
    assert identity.claims not in statement
    assert connection.calls[1] == (
        "exec_driver_sql",
        "SET LOCAL ROLE authenticated",
        None,
    )


def test_async_session_registers_the_sync_transaction_hook() -> None:
    session = AsyncSession()
    identity = rls.build_rls_identity(USER_ID)

    rls.bind_request_identity(session, identity)

    assert session.sync_session.info[rls._BOUND_IDENTITY_KEY] == identity.claims
    assert not session.in_transaction()


def test_context_is_set_before_each_protected_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = rls.build_rls_identity(USER_ID)
    events: list[tuple[str, str]] = []

    def _record(_connection: object, claims: str) -> None:
        events.append(("setup", claims))

    def _query(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        events.append(("query", statement))

    monkeypatch.setattr(rls, "_establish_transaction_context", _record)

    engine = create_engine("sqlite://")
    event.listen(engine, "before_cursor_execute", _query)
    session = Session(engine)

    try:
        rls._bind_sync_session(session, identity)
        session.execute(text("SELECT 1"))
        session.commit()
        session.execute(text("SELECT 2"))
        session.commit()
    finally:
        session.close()
        engine.dispose()

    assert events == [
        ("setup", identity.claims),
        ("query", "SELECT 1"),
        ("setup", identity.claims),
        ("query", "SELECT 2"),
    ]


def test_context_is_reestablished_after_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = rls.build_rls_identity(USER_ID)
    applied = _record_setup(monkeypatch)
    session = _session()

    try:
        rls._bind_sync_session(session, identity)
        session.execute(text("SELECT 1"))
        session.rollback()
        session.execute(text("SELECT 2"))
        session.commit()
    finally:
        session.close()

    assert applied == [identity.claims, identity.claims]


def test_transaction_context_does_not_leak_between_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = rls.build_rls_identity(USER_ID)
    second = rls.build_rls_identity(OTHER_USER_ID)
    applied = _record_setup(monkeypatch)
    engine = create_engine("sqlite://")
    first_session = Session(engine)
    second_session = Session(engine)

    try:
        rls._bind_sync_session(first_session, first)
        rls._bind_sync_session(second_session, second)

        first_session.execute(text("SELECT 1"))
        first_session.commit()
        second_session.execute(text("SELECT 1"))
        second_session.commit()
        first_session.execute(text("SELECT 2"))
        first_session.commit()
    finally:
        first_session.close()
        second_session.close()
        engine.dispose()

    assert applied == [first.claims, second.claims, first.claims]


def test_session_cannot_be_rebound_to_another_user() -> None:
    session = _session()
    try:
        rls._bind_sync_session(session, rls.build_rls_identity(USER_ID))

        with pytest.raises(rls.RLSContextError):
            rls._bind_sync_session(session, rls.build_rls_identity(OTHER_USER_ID))
    finally:
        session.close()


def test_binding_after_a_transaction_has_started_fails_closed() -> None:
    session = _session()
    try:
        session.begin()

        with pytest.raises(rls.RLSContextError):
            rls._bind_sync_session(session, rls.build_rls_identity(USER_ID))
    finally:
        session.close()


def test_setup_failure_blocks_the_protected_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def _fail(_connection: object, _claims: str) -> None:
        raise rls.RLSContextError("RLS setup failed")

    def _query(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        queries.append(statement)

    monkeypatch.setattr(rls, "_establish_transaction_context", _fail)

    engine = create_engine("sqlite://")
    event.listen(engine, "before_cursor_execute", _query)
    session = Session(engine)

    try:
        rls._bind_sync_session(session, rls.build_rls_identity(USER_ID))

        with pytest.raises(rls.RLSContextError):
            session.execute(text("SELECT 1"))
    finally:
        session.close()
        engine.dispose()

    assert queries == []


def test_rls_context_error_fails_closed_as_database_configuration() -> None:
    assert issubclass(rls.RLSContextError, DatabaseConfigurationError)


def test_project_repository_binds_the_verified_subject_before_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound: list[tuple[object, rls.RLSIdentity]] = []

    def _record(session: object, identity: rls.RLSIdentity) -> None:
        bound.append((session, identity))

    monkeypatch.setattr(projects_routes, "bind_request_identity", _record)

    session = object()
    repository = asyncio.run(
        projects_routes.get_project_repository(
            Identity(id=str(USER_ID), email="apex.user@example.com"),
            session,  # type: ignore[arg-type]
        )
    )

    assert bound == [(session, rls.build_rls_identity(USER_ID))]
    assert isinstance(repository, projects_routes.SqlAlchemyProjectRepository)


def test_project_repository_rejects_a_spoofed_subject_before_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound: list[object] = []
    monkeypatch.setattr(
        projects_routes,
        "bind_request_identity",
        lambda session, identity: bound.append(session),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            projects_routes.get_project_repository(
                Identity(id="not-a-uuid", email=None),
                object(),  # type: ignore[arg-type]
            )
        )

    assert error.value.status_code == 401
    assert bound == []
