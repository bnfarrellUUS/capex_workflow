from decimal import Decimal

from app.extensions import db
from app.services import pdf_service
from tests.factories import make_user, make_division, make_draft


def _titles(sections):
    return [s["title"] for s in sections]


def _by_title(sections, title):
    return next(s for s in sections if s["title"] == title)


def _complete_request(app, hidden_ok=True):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id, costs=("30000",))
    req.status = "APPROVED"
    req.justification = "The old forklift died."
    req.effect_on_operations = "Throughput doubles."
    req.asset_life = "7 years"
    req.annual_savings = Decimal("9000")
    req.budgeted = True
    db.session.commit()
    return req


# ---- section model ----

def test_includes_every_section_when_nothing_is_hidden(app):
    req = _complete_request(app)
    titles = _titles(pdf_service.request_pdf_sections(req, []))
    for expected in ["Summary", "Basic info", "Justification",
                     "Effect on operations", "Asset details",
                     "Economic analysis", "Approval history"]:
        assert expected in titles


def test_omits_a_hidden_section(app):
    req = _complete_request(app)
    titles = _titles(pdf_service.request_pdf_sections(req, ["economic"]))
    assert "Economic analysis" not in titles
    assert "Justification" in titles


def test_omits_every_hidden_section(app):
    req = _complete_request(app)
    titles = _titles(pdf_service.request_pdf_sections(
        req, ["description", "effect_on_ops", "asset_details", "economic"]))
    assert "Justification" not in titles
    assert "Effect on operations" not in titles
    assert "Asset details" not in titles
    assert "Economic analysis" not in titles
    # Structural sections always survive.
    assert "Summary" in titles and "Approval history" in titles


def test_budget_amount_shown_when_budgeted(app):
    req = _complete_request(app)
    req.budget_amount = Decimal("45000")
    db.session.commit()
    fields = dict(_by_title(pdf_service.request_pdf_sections(req, []), "Basic info")["fields"])
    assert fields["Budgeted"] == "Yes"
    assert fields["Budget amount"] == "$45,000.00"


def test_budget_amount_omitted_when_not_budgeted(app):
    req = _complete_request(app)
    req.budgeted = False
    db.session.commit()
    fields = dict(_by_title(pdf_service.request_pdf_sections(req, []), "Basic info")["fields"])
    assert "Budget amount" not in fields


def test_finance_breakdown_absent_until_finance_completes(app):
    req = _complete_request(app)
    assert "Finance cost breakdown" not in _titles(pdf_service.request_pdf_sections(req, []))


def test_finance_breakdown_present_once_complete(app):
    req = _complete_request(app)
    req.finance_completed = True
    req.cost_machinery = Decimal("30000")
    req.gl_account = "1500-20"
    db.session.commit()

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Finance cost breakdown")

    flat = " ".join(f"{k} {v}" for k, v in section["fields"])
    assert "30,000" in flat
    assert "1500-20" in flat


def test_ratio_fields_drop_trailing_zeros(app):
    # Numeric(9,4) columns arrive as 3.0000 / 12.5000; a record shouldn't print that.
    req = _complete_request(app)
    req.payback_years = Decimal("3.0000")
    req.irr_after_tax = Decimal("12.5000")
    db.session.commit()

    fields = dict(_by_title(pdf_service.request_pdf_sections(req, []), "Economic analysis")["fields"])

    assert fields["Payback (years)"] == "3"
    assert fields["IRR after tax (%)"] == "12.5"


def test_useful_asset_life_is_basic_info_even_when_economic_is_hidden(app):
    # It moved out of the Economic step, so hiding Economic no longer drops it.
    req = _complete_request(app)
    sections = pdf_service.request_pdf_sections(req, ["economic"])
    fields = dict(_by_title(sections, "Basic info")["fields"])
    assert fields["Useful / asset life"] == "7 years"


def test_flags_render_as_yes_no(app):
    req = _complete_request(app)
    fields = dict(_by_title(pdf_service.request_pdf_sections(req, []), "Basic info")["fields"])
    assert fields["Budgeted"] == "Yes"
    assert fields["Replacement"] == "No"


def test_asset_details_lists_line_items_and_total(app):
    req = _complete_request(app)
    section = _by_title(pdf_service.request_pdf_sections(req, []), "Asset details")
    assert section["kind"] == "table"
    # header row + one line item
    assert len(section["rows"]) == 2
    assert "$30,000.00" in section["rows"][1]
    assert "$30,000.00" in section["total"]


def test_approval_history_rows_match_the_audit_trail(app):
    req = _complete_request(app)
    actor = make_user("appr")
    from app.models import ApprovalAction
    db.session.add(ApprovalAction(request_id=req.id, actor_id=actor.id,
                                  action="SUBMITTED", level=1))
    db.session.add(ApprovalAction(request_id=req.id, actor_id=actor.id,
                                  action="APPROVED", level=1, comment="Looks fine"))
    db.session.commit()
    db.session.refresh(req)

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Approval history")

    assert len(section["rows"]) == 3  # header + two actions
    assert section["rows"][1][0] == "SUBMITTED"
    assert "Looks fine" in section["rows"][2]


def test_approval_history_says_none_when_empty(app):
    req = _complete_request(app)
    section = _by_title(pdf_service.request_pdf_sections(req, []), "Approval history")
    assert section["rows"] == [] or len(section["rows"]) == 1
    assert section.get("empty_note")


def test_attachments_are_listed_by_filename(app):
    req = _complete_request(app)
    from app.models import Attachment
    db.session.add(Attachment(request_id=req.id, filename="quote.pdf",
                              content_type="application/pdf", size=12,
                              storage_path="x", uploaded_by_id=req.requestor_id))
    db.session.commit()
    db.session.refresh(req)

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Attachments")

    assert "quote.pdf" in " ".join(section["items"])


# ---- rendering ----

def test_render_produces_a_real_pdf(app):
    req = _complete_request(app)
    data = pdf_service.build_request_pdf(req, [])
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000


def test_render_survives_a_request_with_hidden_sections(app):
    req = _complete_request(app)
    data = pdf_service.build_request_pdf(req, ["economic", "asset_details"])
    assert data[:5] == b"%PDF-"


def test_filename_is_the_request_number(app):
    req = _complete_request(app)
    assert pdf_service.pdf_filename(req) == f"{req.number}.pdf"


def test_comments_section_lists_every_comment(app):
    from app.models import RequestComment
    req = _complete_request(app)
    asker = make_user("asker")
    db.session.add(RequestComment(request_id=req.id, author_id=asker.id,
                                  body="Where are the bids?"))
    db.session.commit()

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Comments")

    assert section["rows"][0] == ["By", "Date", "Comment"]
    assert section["rows"][1][0] == asker.name
    assert section["rows"][1][2] == "Where are the bids?"
    assert section["empty_note"] is None


def test_comments_section_notes_when_there_are_none(app):
    req = _complete_request(app)

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Comments")

    assert section["rows"] == []
    assert section["empty_note"] == "No comments."


def test_comments_section_follows_approval_history(app):
    req = _complete_request(app)
    titles = _titles(pdf_service.request_pdf_sections(req, []))

    assert titles.index("Comments") == titles.index("Approval history") + 1
