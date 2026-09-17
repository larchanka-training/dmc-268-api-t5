"""Exercise database guarantees, not the unimplemented worker/payment protocols."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from code_review.adapters.outbound.postgres import models as m

from .factories import NOW, billing, insert, payment_values, review, tenant

pytestmark = pytest.mark.postgres


def rejected(conn, action, constraint):
    with pytest.raises(IntegrityError) as error, conn.begin_nested():
        action()
    assert error.value.orig.diag.constraint_name == constraint


def test_cross_tenant_repository_integration(db):
    a, b = tenant(db), tenant(db)
    rejected(
        db,
        lambda: insert(
            db,
            m.Repository,
            tenant_id=a["tenant_id"],
            integration_id=b["integration"],
            external_id=2,
            full_name="wrong/repo",
            state="active",
            access_epoch=0,
        ),
        "fk_repository_integration_id",
    )


@pytest.mark.parametrize("role", ["root", "OWNER", ""])
def test_membership_rejects_unknown_role(db, role):
    graph = tenant(db)
    rejected(
        db,
        lambda: db.execute(
            m.Membership.__table__.update()
            .where(m.Membership.id == graph["member"])
            .values(role=role)
        ),
        "ck_membership_role",
    )


def test_grant_requires_exactly_one_actor_and_same_tenant(db):
    a, b = tenant(db), tenant(db)
    values = dict(
        tenant_id=a["tenant_id"], repository_id=a["repository"], permission="read", state="active"
    )
    rejected(db, lambda: insert(db, m.RepositoryGrant, **values), "ck_repository_grant_one_actor")
    rejected(
        db,
        lambda: insert(db, m.RepositoryGrant, **values, membership_id=b["member"]),
        "fk_repository_grant_membership_id",
    )
    insert(db, m.RepositoryGrant, **values, membership_id=a["member"])
    rejected(
        db,
        lambda: insert(db, m.RepositoryGrant, **values, membership_id=a["member"]),
        "uq_repository_grant_membership_id",
    )


def test_single_default_profile(db):
    tid = tenant(db)["tenant_id"]
    insert(db, m.ReviewProfile, tenant_id=tid, name="default", is_default=True, settings={})
    rejected(
        db,
        lambda: insert(
            db, m.ReviewProfile, tenant_id=tid, name="other", is_default=True, settings={}
        ),
        "uq_review_profile_default",
    )
    insert(db, m.ReviewProfile, tenant_id=tid, name="other", is_default=False, settings={})


def test_prompt_must_belong_to_run_perspective(db):
    g = review(db)
    p1 = insert(db, m.Perspective, tenant_id=g["tenant_id"], key="one", name="one", state="active")
    p2 = insert(db, m.Perspective, tenant_id=g["tenant_id"], key="two", name="two", state="active")
    prompt = insert(
        db,
        m.PromptVersion,
        tenant_id=g["tenant_id"],
        perspective_id=p1,
        version=1,
        instructions="review",
        settings={},
        content_hash="hash",
    )
    rejected(
        db,
        lambda: insert(
            db,
            m.PerspectiveRun,
            tenant_id=g["tenant_id"],
            job_id=g["job"],
            perspective_id=p2,
            prompt_version_id=prompt,
            state="queued",
            coverage={},
        ),
        "fk_perspective_run_prompt_version_id_perspective_id",
    )


def test_job_cannot_point_to_another_pr_of_same_tenant(db):
    a = review(db)
    b = review(db, a)
    rejected(
        db,
        lambda: db.execute(
            m.ReviewJob.__table__.update()
            .where(m.ReviewJob.id == a["job"])
            .values(merge_request_id=b["mr"])
        ),
        "fk_review_job_request_id_merge_request_id",
    )


def test_one_active_job_but_history_allowed(db):
    g = review(db)
    values = dict(
        tenant_id=g["tenant_id"],
        request_id=g["request"],
        merge_request_id=g["mr"],
        revision_epoch=2,
        revision_fingerprint="new",
        config_hash="config",
        phase="prepare",
    )
    rejected(
        db,
        lambda: insert(db, m.ReviewJob, **values, state="queued"),
        "uq_review_job_active_request",
    )
    insert(db, m.ReviewJob, **values, state="superseded")


def test_accepted_attempt_must_belong_to_same_call(db):
    g = review(db)
    rejected(
        db,
        lambda: insert(
            db,
            m.ModelCall,
            tenant_id=g["tenant_id"],
            job_id=g["job"],
            kind="job_synthesis",
            call_key="other",
            state="planned",
            accepted_attempt_id=g["attempt"],
        ),
        "fk_model_call_accepted_attempt_id_id",
    )


def test_finding_requires_selected_attempt(db):
    g = review(db)
    unaccepted = insert(
        db,
        m.InferenceAttempt,
        tenant_id=g["tenant_id"],
        model_call_id=g["call"],
        work_item_id=g["work"],
        attempt_no=2,
        owner_token=uuid4(),
        state="received",
        reserved_tokens=100,
    )
    rejected(
        db,
        lambda: insert(
            db,
            m.Finding,
            tenant_id=g["tenant_id"],
            job_id=g["job"],
            model_call_id=g["call"],
            attempt_id=unaccepted,
            category="bug",
            severity="high",
            body="wrong",
            evidence={},
            fingerprint="wrong",
        ),
        "fk_finding_model_call_id_attempt_id",
    )


def test_comment_and_duplicate_must_belong_to_same_job(db):
    a = review(db)
    b = review(db, a)
    rejected(
        db,
        lambda: insert(
            db,
            m.Comment,
            tenant_id=a["tenant_id"],
            job_id=a["job"],
            finding_id=b["finding"],
            publication_key="key",
            target={},
            body="x",
            state="pending",
            available_at=NOW,
        ),
        "fk_comment_job_id_finding_id",
    )
    rejected(
        db,
        lambda: db.execute(
            m.Finding.__table__.update()
            .where(m.Finding.id == a["finding"])
            .values(duplicate_of_id=b["finding"])
        ),
        "fk_finding_job_id_duplicate_of_id",
    )
    rejected(
        db,
        lambda: db.execute(
            m.Finding.__table__.update()
            .where(m.Finding.id == a["finding"])
            .values(duplicate_of_id=a["finding"])
        ),
        "ck_finding_not_self_duplicate",
    )


def test_context_is_unique_per_call(db):
    g = review(db)
    values = dict(
        tenant_id=g["tenant_id"],
        model_call_id=g["call"],
        request_body={},
        content_hash="hash",
        token_count=10,
        output_reserve=10,
        counter_version="test",
    )
    insert(db, m.ContextPayload, **values)
    rejected(
        db,
        lambda: insert(db, m.ContextPayload, **values),
        "uq_context_payload_tenant_id_model_call_id",
    )


@pytest.mark.parametrize(
    "values,constraint",
    [
        ({"kind": "sync_revision"}, "ck_work_item_kind_target"),
        ({"state": "running"}, "ck_work_item_running_lease"),
        ({"max_attempts": 0}, "ck_work_item_max_attempts_positive"),
        ({"attempt_count": -1}, "ck_work_item_attempt_count_nonnegative"),
    ],
)
def test_work_item_constraints(db, values, constraint):
    g = review(db)
    rejected(
        db,
        lambda: db.execute(
            m.WorkItem.__table__.update().where(m.WorkItem.id == g["work"]).values(**values)
        ),
        constraint,
    )


def test_request_idempotency_scope(db):
    g = review(db)
    original = dict(
        db.execute(select(m.ReviewRequest.__table__).where(m.ReviewRequest.id == g["request"]))
        .mappings()
        .one()
    )
    original["id"] = uuid4()
    rejected(
        db,
        lambda: db.execute(m.ReviewRequest.__table__.insert().values(**original)),
        "uq_review_request_actor_membership_id",
    )


def test_unknown_payment_blocks_next_checkout_but_facts_are_kept(db):
    g = billing(db, review(db))
    payment = insert(db, m.Payment, **payment_values(g, state="payment_unknown"))
    rejected(db, lambda: insert(db, m.Payment, **payment_values(g, 2)), "uq_payment_open_purchase")
    db.execute(
        m.Payment.__table__.update().where(m.Payment.id == payment).values(state="succeeded")
    )
    insert(db, m.Payment, **payment_values(g, 2, state="succeeded"))


def test_accepted_payment_cannot_belong_to_different_purchase(db):
    g = billing(db, review(db))
    payment = insert(db, m.Payment, **payment_values(g, state="succeeded"))
    other = insert(
        db,
        m.Purchase,
        tenant_id=g["tenant_id"],
        billing_account_id=g["account"],
        product_snapshot={},
        amount_minor=100,
        currency="USD",
        state="awaiting_payment",
    )
    rejected(
        db,
        lambda: db.execute(
            m.Purchase.__table__.update()
            .where(m.Purchase.id == other)
            .values(accepted_payment_id=payment)
        ),
        "fk_purchase_accepted_payment_id_id",
    )


def test_one_entitlement_and_capacity(db):
    g = billing(db, review(db))
    rejected(
        db,
        lambda: insert(
            db,
            m.Entitlement,
            tenant_id=g["tenant_id"],
            billing_account_id=g["account"],
            source_purchase_id=g["purchase"],
            total_units=10,
            reserved_units=0,
            consumed_units=0,
            state="active",
        ),
        "uq_entitlement_tenant_id_source_purchase_id",
    )
    rejected(
        db,
        lambda: db.execute(
            m.Entitlement.__table__.update()
            .where(m.Entitlement.id == g["entitlement"])
            .values(consumed_units=10)
        ),
        "ck_entitlement_capacity",
    )


def test_settlement_record_and_timestamp(db):
    g = billing(db, review(db))
    rejected(
        db,
        lambda: db.execute(
            m.UsageReservation.__table__.update()
            .where(m.UsageReservation.id == g["reservation"])
            .values(state="consumed")
        ),
        "ck_usage_reservation_settlement",
    )
    common = dict(
        tenant_id=g["tenant_id"],
        billing_account_id=g["account"],
        entitlement_id=g["entitlement"],
        reservation_id=g["reservation"],
        quantity=1,
    )
    insert(db, m.BillingEntry, **common, kind="consume", business_key="consume")
    rejected(
        db,
        lambda: insert(db, m.BillingEntry, **common, kind="release", business_key="release"),
        "uq_billing_entry_settlement",
    )


def test_concurrent_checkout_unique_index(database):
    with database.begin() as conn:
        g = billing(conn, review(conn))
    barrier = Barrier(2)

    def checkout(sequence):
        try:
            with database.begin() as conn:
                barrier.wait(timeout=10)
                insert(conn, m.Payment, **payment_values(g, sequence))
            return "created"
        except IntegrityError as error:
            return error.orig.diag.constraint_name

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(checkout, [1, 2]))
    assert sorted(outcomes) == ["created", "uq_payment_open_purchase"]


def test_skip_locked_workers_claim_different_rows(database):
    with database.begin() as conn:
        a = review(conn)
        b = review(conn)
    claim = (
        select(m.WorkItem.id)
        .where(m.WorkItem.id.in_([a["work"], b["work"]]))
        .order_by(m.WorkItem.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    with database.connect() as first, first.begin(), database.connect() as second, second.begin():
        assert first.scalar(claim) != second.scalar(claim)
