import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Level approvers are many-to-many: any one of them can act at that level.
# L1 approvers are per-division; L2/L3 approvers hang off the threshold row.
division_l1_approvers = Table(
    "division_l1_approvers", db.metadata,
    Column("division_id", String(36), ForeignKey("divisions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
)
threshold_approvers = Table(
    "threshold_approvers", db.metadata,
    Column("threshold_id", String(36), ForeignKey("approval_thresholds.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
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
    username: Mapped[str] = mapped_column(String(150), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    roles: Mapped[str] = mapped_column(String(255), default='["REQUESTOR"]')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

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
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    reset_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def roles_list(self) -> list[str]:
        return json.loads(self.roles)


class Division(db.Model):
    __tablename__ = "divisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    number: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Level-1 approvers for this division (any one may approve).
    l1_approvers: Mapped[list["User"]] = relationship(
        "User", secondary=division_l1_approvers
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="division", foreign_keys="User.division_id"
    )


class ApprovalThreshold(db.Model):
    __tablename__ = "approval_thresholds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    level: Mapped[int] = mapped_column(Integer, unique=True)  # 1, 2, 3
    max_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    # Approvers for this level (any one may approve). L1 uses the division's list.
    approvers: Mapped[list["User"]] = relationship("User", secondary=threshold_approvers)


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
    division_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("divisions.id", ondelete="NO ACTION"), nullable=True
    )
    division: Mapped[Optional["Division"]] = relationship("Division")
    request_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Basic info
    description: Mapped[str] = mapped_column(Text, default="")
    budgeted: Mapped[bool] = mapped_column(Boolean, default=False)
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
    cost_permits: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    cost_misc: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    asset_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gl_account: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    po_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
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
    action: Mapped[str] = mapped_column(String(30))  # SUBMITTED | APPROVED | REJECTED | RESUBMITTED | FINANCE_COMPLETED
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


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
