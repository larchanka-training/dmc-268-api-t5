"""Small valid graph for constraint tests, with explicit domain values."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from code_review.adapters.outbound.postgres import models as m

NOW = datetime.now(UTC)


def insert(conn, model, **values):
    values.setdefault("id", uuid4())
    conn.execute(model.__table__.insert().values(**values))
    return values["id"]


def tenant(conn):
    workspace = insert(conn, m.Workspace, name="Test", state="active", access_epoch=0)
    user = insert(conn, m.User, display_name="Tester", state="active")
    member = insert(
        conn,
        m.Membership,
        tenant_id=workspace,
        user_id=user,
        role="owner",
        state="active",
        access_epoch=0,
    )
    integration = insert(
        conn,
        m.GitIntegration,
        tenant_id=workspace,
        provider_host="github.com",
        app_config_key=str(uuid4()),
        installation_id=1,
        state="active",
        access_epoch=0,
    )
    repository = insert(
        conn,
        m.Repository,
        tenant_id=workspace,
        integration_id=integration,
        external_id=1,
        full_name="example/repo",
        state="active",
        access_epoch=0,
    )
    return {
        "tenant_id": workspace,
        "member": member,
        "integration": integration,
        "repository": repository,
    }


def review(conn, graph=None):
    graph = dict(graph or tenant(conn))
    tid = graph["tenant_id"]
    mr = insert(
        conn,
        m.MergeRequest,
        tenant_id=tid,
        repository_id=graph["repository"],
        external_number=int(uuid4()) % 1000000000 + 1,
        revision_descriptor={"head": "abc"},
        revision_epoch=1,
        refresh_requested_seq=1,
        refresh_applied_seq=1,
    )
    request = insert(
        conn,
        m.ReviewRequest,
        tenant_id=tid,
        merge_request_id=mr,
        actor_membership_id=graph["member"],
        idempotency_key=str(uuid4()),
        request_hash="request",
        config_snapshot={},
        config_hash="config",
        budget={},
        reserved_tokens=0,
        accounted_tokens=0,
        track_latest=False,
        deadline_at=NOW + timedelta(hours=1),
        state="accepted",
    )
    job = insert(
        conn,
        m.ReviewJob,
        tenant_id=tid,
        request_id=request,
        merge_request_id=mr,
        revision_fingerprint="revision",
        revision_epoch=1,
        config_hash="config",
        state="queued",
        phase="prepare",
    )
    call = insert(
        conn,
        m.ModelCall,
        tenant_id=tid,
        job_id=job,
        kind="job_synthesis",
        call_key="synthesis",
        state="planned",
    )
    work = insert(
        conn,
        m.WorkItem,
        tenant_id=tid,
        kind="run_review",
        review_job_id=job,
        business_key=str(job),
        state="queued",
        attempt_count=0,
        max_attempts=3,
        available_at=NOW,
        deadline_at=NOW + timedelta(hours=1),
    )
    attempt = insert(
        conn,
        m.InferenceAttempt,
        tenant_id=tid,
        model_call_id=call,
        work_item_id=work,
        attempt_no=1,
        owner_token=uuid4(),
        state="accepted",
        reserved_tokens=100,
    )
    conn.execute(
        m.ModelCall.__table__.update()
        .where(m.ModelCall.id == call)
        .values(accepted_attempt_id=attempt, state="succeeded")
    )
    finding = insert(
        conn,
        m.Finding,
        tenant_id=tid,
        job_id=job,
        model_call_id=call,
        attempt_id=attempt,
        category="bug",
        severity="high",
        body="Example",
        evidence={},
        fingerprint="finding",
    )
    graph.update(
        mr=mr, request=request, job=job, call=call, work=work, attempt=attempt, finding=finding
    )
    return graph


def billing(conn, graph):
    graph = dict(graph)
    tid = graph["tenant_id"]
    account = insert(conn, m.BillingAccount, tenant_id=tid, state="active", billing_details={})
    purchase = insert(
        conn,
        m.Purchase,
        tenant_id=tid,
        billing_account_id=account,
        created_by_id=graph["member"],
        product_snapshot={},
        amount_minor=100,
        currency="USD",
        state="awaiting_payment",
    )
    entitlement = insert(
        conn,
        m.Entitlement,
        tenant_id=tid,
        billing_account_id=account,
        source_purchase_id=purchase,
        total_units=10,
        reserved_units=1,
        consumed_units=0,
        state="active",
    )
    reservation = insert(
        conn,
        m.UsageReservation,
        tenant_id=tid,
        request_id=graph["request"],
        entitlement_id=entitlement,
        units=1,
        state="reserved",
    )
    graph.update(
        account=account, purchase=purchase, entitlement=entitlement, reservation=reservation
    )
    return graph


def payment_values(graph, sequence=1, state="pending"):
    return dict(
        id=uuid4(),
        tenant_id=graph["tenant_id"],
        purchase_id=graph["purchase"],
        sequence_no=sequence,
        provider="test",
        provider_scope="test:merchant:sandbox",
        idempotency_key=str(uuid4()),
        request_hash="hash",
        expected_amount=100,
        currency="USD",
        state=state,
        available_at=NOW,
    )
