"""Supabase Row Level Security request context.

The FastAPI application connects with a least-privilege runtime login role, not
with Supabase's table owner and not with a role that can bypass RLS. Before the
first protected statement in every transaction, this module installs the
verified identity as transaction-local PostgreSQL state:

* ``request.jwt.claims`` contains the verified ``sub`` (plus the fixed
  ``authenticated`` role/audience) and is set with a bound parameter.
* ``SET LOCAL ROLE authenticated`` makes the statement run as the same role the
  Supabase RLS policies target.

Both settings are transaction-local. PostgreSQL resets them at commit or
rollback, so a pooled connection cannot carry one user's identity into another
user's request. The ``after_begin`` hook runs again for every new transaction,
including the transaction SQLAlchemy opens after a commit or while refreshing a
row.

If the context cannot be established, the exception propagates and the
protected statement does not run. There is no fallback to the owner role or to
``BYPASSRLS``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from .config import DatabaseConfigurationError

AUTHENTICATED_ROLE = "authenticated"
"""The fixed database role targeted by the Story 1.3 RLS policies."""

_BOUND_IDENTITY_KEY = "apex_rls_identity"
_SET_CLAIMS = text("SELECT set_config('request.jwt.claims', :claims, true)")
# The role name is an application constant, never user input. PostgreSQL does
# not accept a bind parameter in SET ROLE, so this must remain a static string.
_SET_ROLE = f"SET LOCAL ROLE {AUTHENTICATED_ROLE}"


class RLSContextError(DatabaseConfigurationError):
    """Raised when the transaction-local identity context cannot be established.

    It derives from :class:`DatabaseConfigurationError` so the application's
    sanitized 503 handler and the Projects route error translation both fail
    closed instead of returning a generic server error.
    """


@dataclass(frozen=True, slots=True)
class RLSIdentity:
    """The verified identity that will be bound to the database transaction."""

    user_id: uuid.UUID
    claims: str


def build_rls_identity(user_id: uuid.UUID) -> RLSIdentity:
    """Build the transaction claims from a verified token subject.

    Only the verified subject is accepted. The role and audience are the fixed
    values for a signed-in Supabase user; they are never read from a request.
    """
    if not isinstance(user_id, uuid.UUID):
        raise RLSContextError(
            "The authenticated subject must be a UUID before RLS context can be set."
        )

    claims = json.dumps(
        {
            "aud": AUTHENTICATED_ROLE,
            "role": AUTHENTICATED_ROLE,
            "sub": str(user_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return RLSIdentity(user_id=user_id, claims=claims)


def _establish_transaction_context(connection: Connection, claims: str) -> None:
    """Apply the claims and role inside the transaction that has just begun."""
    connection.execute(_SET_CLAIMS, {"claims": claims}).scalar_one()
    connection.exec_driver_sql(_SET_ROLE)


def _bind_sync_session(session: Session, identity: RLSIdentity) -> None:
    """Attach the after-begin hook to a synchronous SQLAlchemy session."""
    if session.in_transaction():
        raise RLSContextError(
            "RLS context must be bound before the database session starts a transaction."
        )

    bound_claims = session.info.get(_BOUND_IDENTITY_KEY)
    if bound_claims is not None:
        if bound_claims != identity.claims:
            raise RLSContextError(
                "A different authenticated identity is already bound to this session."
            )
        return

    def _after_begin(
        _session: Session,
        _transaction: SessionTransaction,
        connection: Connection,
    ) -> None:
        _establish_transaction_context(connection, identity.claims)

    event.listen(session, "after_begin", _after_begin)
    session.info[_BOUND_IDENTITY_KEY] = identity.claims


def bind_request_identity(session: AsyncSession, identity: RLSIdentity) -> None:
    """Bind a verified identity to every transaction opened by ``session``.

    The session must not have started a transaction yet. In the request flow it
    is fresh from :func:`apex_backend.db.session.get_db_session` and no query
    has run, so the first protected statement always triggers the hook first.
    """
    _bind_sync_session(session.sync_session, identity)
