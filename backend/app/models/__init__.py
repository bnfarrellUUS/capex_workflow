import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text, Table, Column, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Level approvers are many-to-many: any one of them can act at that level.
# L1 approvers are per-division; L2 approvers are per-region (a region's VP
# pool); L3 approvers hang off the threshold row. `position` is the order an
# admin set (the first approver is the request's "assigned to"), with user_id
# as the tiebreaker -- migrated rows all start at 0, and SQL Server does not
# order ties, so without it two reads could name different people; the
# relationship does not write it, so pools are saved through
# services/approver_pools.set_pool, never by assigning the list directly.
division_l1_approvers = Table(
    "division_l1_approvers", db.metadata,
    Column("division_id", String(36), ForeignKey("divisions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
    Column("position", Integer, nullable=False, server_default="0"),
)
threshold_approvers = Table(
    "threshold_approvers", db.metadata,
    Column("threshold_id", String(36), ForeignKey("approval_thresholds.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
    Column("position", Integer, nullable=False, server_default="0"),
)
region_vp_approvers = Table(
    "region_vp_approvers", db.metadata,
    Column("region_id", String(36), ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
    Column("position", Integer, nullable=False, server_default="0"),
)

# Money uses fixed precision so SQL Server stores cents (an unscaled Numeric
# becomes DECIMAL(18,0) there and would truncate). Ratios get more scale.
MONEY = Numeric(18, 2)
RATIO = Numeric(9, 4)


def _id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    roles: Mapped[str] = mapped_column(String(255), default='["REQUESTOR"]')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set for new accounts and admin resets: the user is gated to the
    # set-password endpoint until they choose their own password.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    division_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("divisions.id", ondelete="NO ACTION"), nullable=True
    )
    division: Mapped[Optional["Division"]] = relationship(
        back_populates="users", foreign_keys=[division_id]
    )

    delegate_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    delegate: Mapped[Optional["User"]] = relationship(
        "User", remote_side=[id], back_populates="delegates_for"
    )
    delegates_for: Mapped[list["User"]] = relationship(
        "User", back_populates="delegate"
    )

    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # unique=True is correct on SQLite, which treats NULLs as distinct. SQL
    # Server does not, so migration b8c9d0e1f2a3 replaces the constraint there
    # with a unique index filtered to `reset_token IS NOT NULL`. Without that,
    # the table can hold only ONE row with a NULL reset_token.
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    reset_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # The Entra ID object ID, pinned on this user's first SSO sign-in and
    # compared on every one after (sso_service gate 4). NOT unique: the row is
    # found by email and this only confirms it is the same person, and a
    # nullable-unique column caps the table at one NULL on SQL Server (see
    # migration b8c9d0e1f2a3).
    entra_oid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Part of the Flask-Login id (see get_id), so it is baked into the session
    # and remember-me cookies; bumping it signs this user out everywhere.
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    @property
    def is_active(self) -> bool:
        return self.active

    def get_id(self) -> str:
        return f"{self.id}:{self.session_version or 0}"

    @property
    def roles_list(self) -> list[str]:
        return json.loads(self.roles)


class Region(db.Model):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Level-2 approvers (the region's VP + backups; any one may approve).
    vp_approvers: Mapped[list["User"]] = relationship(
        "User", secondary=region_vp_approvers,
        order_by=(region_vp_approvers.c.position, region_vp_approvers.c.user_id))

    divisions: Mapped[list["Division"]] = relationship(back_populates="region")


class Division(db.Model):
    __tablename__ = "divisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    number: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Level-1 approvers for this division (any one may approve).
    l1_approvers: Mapped[list["User"]] = relationship(
        "User", secondary=division_l1_approvers,
        order_by=(division_l1_approvers.c.position, division_l1_approvers.c.user_id)
    )

    # Nullable because divisions predate regions; the admin form requires it.
    region_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regions.id", ondelete="NO ACTION"), nullable=True
    )
    region: Mapped[Optional["Region"]] = relationship(back_populates="divisions")

    users: Mapped[list["User"]] = relationship(
        back_populates="division", foreign_keys="User.division_id"
    )


class ApprovalThreshold(db.Model):
    __tablename__ = "approval_thresholds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    level: Mapped[int] = mapped_column(Integer, unique=True)  # 1, 2, 3
    max_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    # Approvers for this level (any one may approve). L1 uses the division's list.
    approvers: Mapped[list["User"]] = relationship(
        "User", secondary=threshold_approvers,
        order_by=(threshold_approvers.c.position, threshold_approvers.c.user_id))


class CapexRequest(db.Model):
    __tablename__ = "capex_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")

    requestor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    requestor: Mapped["User"] = relationship("User", foreign_keys=[requestor_id])
    assignee_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id])
    # An ADMIN's per-request approver for the CURRENT level only (ADO 5907):
    # joins that level's pool in front, and is cleared whenever the request
    # leaves the level. See workflow_service.current_actors / reassign.
    reassigned_to_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    reassigned_to: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reassigned_to_id])
    division_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("divisions.id", ondelete="NO ACTION"), nullable=True
    )
    division: Mapped[Optional["Division"]] = relationship("Division")
    request_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Basic info
    description: Mapped[str] = mapped_column(Text, default="")
    budgeted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Only set while budgeted is true; cleared when the flag comes off.
    budget_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    replacement: Mapped[bool] = mapped_column(Boolean, default=False)
    health_safety: Mapped[bool] = mapped_column(Boolean, default=False)
    revenue_generating: Mapped[bool] = mapped_column(Boolean, default=False)
    environmental: Mapped[bool] = mapped_column(Boolean, default=False)
    competitive_bids: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_recommended: Mapped[bool] = mapped_column(Boolean, default=False)

    # Narrative
    justification: Mapped[str] = mapped_column(Text, default="")
    effect_on_operations: Mapped[str] = mapped_column(Text, default="")

    # Economic justification
    asset_life: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    irr_after_tax: Mapped[Optional[Decimal]] = mapped_column(RATIO, nullable=True)
    first_year_ebit: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    annual_savings: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    payback_years: Mapped[Optional[Decimal]] = mapped_column(RATIO, nullable=True)
    npv_savings: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)

    # Finance section (completed after final approval)
    cost_autos_trucks: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_machinery: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_improvements: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_furniture: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_it_computer: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_misc: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    asset_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gl_account: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    useful_life_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    useful_life_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    in_service_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finance_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    total_cost: Mapped[Decimal] = mapped_column(MONEY, default=0)
    required_levels: Mapped[int] = mapped_column(Integer, default=1)
    current_level: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    equipment_items: Mapped[list["EquipmentItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    actions: Mapped[list["ApprovalAction"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    comments: Mapped[list["RequestComment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan",
        order_by="RequestComment.created_at",
    )


class EquipmentItem(db.Model):
    __tablename__ = "equipment_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="equipment_items")
    units: Mapped[int] = mapped_column(Integer)
    condition: Mapped[str] = mapped_column(String(10))  # "NEW" | "USED"
    type: Mapped[str] = mapped_column(String(150))
    make: Mapped[str] = mapped_column(String(150))
    model: Mapped[str] = mapped_column(String(150))
    cost: Mapped[Decimal] = mapped_column(MONEY)


class Attachment(db.Model):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="attachments")
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    uploaded_by: Mapped["User"] = relationship("User")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ApprovalAction(db.Model):
    __tablename__ = "approval_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="actions")
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id])
    acted_for_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(30))  # SUBMITTED | APPROVED | REJECTED | RESUBMITTED | REASSIGNED | FINANCE_COMPLETED
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RequestComment(db.Model):
    """A question or answer on a request. Immutable: no edit, no delete."""
    __tablename__ = "request_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="comments")
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    author: Mapped["User"] = relationship("User")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Ping(db.Model):
    """One note in a conversation. A REPLY IS A CHILD ROW, not a separate table:
    `parent_id` points at the conversation root and never at another reply, so a
    thread is exactly two levels deep and one exchange is one row in the inbox.

    Who it is addressed to lives in `ping_recipients` -- there is deliberately no
    recipient column here. Immutable once sent, so no updated_at.
    """
    __tablename__ = "pings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    parent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("pings.id"), nullable=True, index=True)
    sender_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), index=True)
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    note: Mapped[str] = mapped_column(Text)
    # Optional context: the one thing a CAPRI ping can be "about". NO ACTION,
    # not cascade -- request_service.delete_draft refuses a draft with pings.
    request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="NO ACTION"), nullable=True, index=True)
    request: Mapped[Optional["CapexRequest"]] = relationship("CapexRequest")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PingRecipient(db.Model):
    """Per-person state. Read is personal; done is SHARED and derived at read time
    (see ping_service.apply_shared_done) -- this row still records each person's
    own tick, so the roster can show who read and who closed it.
    """
    __tablename__ = "ping_recipients"
    __table_args__ = (
        # Addressing the same person twice is a dedupe bug, not a state the
        # database should hold.
        UniqueConstraint("ping_id", "user_id", name="uq_ping_recipient"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    ping_id: Mapped[str] = mapped_column(ForeignKey("pings.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), index=True)
    user: Mapped["User"] = relationship("User")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="SET NULL"), nullable=True
    )
    recipient: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(30))  # ASSIGNED | DECIDED | FINANCE_READY | REMINDER
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Counter(db.Model):
    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    type: Mapped[str] = mapped_column(String(20), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_subject: Mapped[str] = mapped_column(Text)
    default_body_html: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now())
