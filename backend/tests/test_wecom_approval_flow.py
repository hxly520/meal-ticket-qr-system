"""审批回调出票流程回归测试。

覆盖三个历史事故点：
1. 审批详情获取失败时必须失败退出，绝不能用默认值（午餐/1 人/今天）出票
2. 出票必须带申请原因，并按表单的人数、餐别、日期生成整套票
3. 审批撤销要作废未核销的票
"""

import asyncio

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.meal_ticket import MealTicket
from app.models.wecom_event import WeComApprovalEvent
from app.services import wecom
from app.services.system_settings import seed_default_settings, update_settings

TEMPLATE = "3WNh3nnrjc1yC1Dj5hrq1iHLXr7zrUPs1apwBuwN"


def build_detail(reason: str = "恩捷人员审核") -> dict:
    return {
        "errcode": 0,
        "info": {
            "sp_no": "202610210018",
            "sp_name": "餐票申请",
            "sp_status": 2,
            "template_id": TEMPLATE,
            "applyer": {"userid": "ChenCanTing", "partyid": "27"},
            "apply_data": {
                "contents": [
                    {
                        "control": "Date",
                        "title": [{"text": "用餐日期", "lang": "zh_CN"}],
                        "value": {"date": {"type": "day", "s_timestamp": "1792598400"}},
                    },
                    {
                        "control": "Number",
                        "title": [{"text": "用餐人数", "lang": "zh_CN"}],
                        "value": {"new_number": "6"},
                    },
                    {
                        "control": "Selector",
                        "title": [{"text": "餐别", "lang": "zh_CN"}],
                        "value": {
                            "selector": {
                                "type": "multi",
                                "options": [{"key": "o1", "value": [{"text": "早餐", "lang": "zh_CN"}]}],
                            }
                        },
                    },
                    {
                        "control": "Textarea",
                        "title": [{"text": "申请原因", "lang": "zh_CN"}],
                        "value": {"text": reason},
                    },
                ]
            },
        },
    }


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_default_settings(session)
    update_settings(
        session,
        {
            "wecom_corp_id": "corp",
            "wecom_secret": "secret",
            "wecom_approval_template_id": TEMPLATE,
            "wecom_field_meal_date": "用餐日期",
            "wecom_field_meal_type": "餐别",
            "wecom_field_diner_count": "用餐人数",
            "wecom_field_reason": "申请原因",
            "wecom_field_department": "部门",
        },
    )
    try:
        yield session
    finally:
        session.close()


def make_event(db, sp_no: str = "202610210018", status: int = 2) -> WeComApprovalEvent:
    event = WeComApprovalEvent(
        sp_no=sp_no,
        template_id=TEMPLATE,
        applicant_userid="ChenCanTing",
        sp_status=status,
        raw_payload={"ApprovalInfo": {"SpNo": sp_no, "TemplateId": TEMPLATE}},
        processed=False,
        attempts=0,
        processing=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def patch_client(monkeypatch, *, detail=None, detail_error=None):
    async def fake_detail(self, sp_no):
        if detail_error:
            raise detail_error
        return detail

    async def fake_profile(self, userid):
        return {"name": "陈灿婷", "department": [27]}

    async def fake_departments(self, ids):
        return ["行政部"]

    async def fake_upload(self, image_bytes, filename):
        return "media-id"

    async def fake_send(self, touser, media_id):
        return None

    monkeypatch.setattr(wecom.WeComClient, "get_approval_detail", fake_detail)
    monkeypatch.setattr(wecom.WeComClient, "get_user_profile", fake_profile)
    monkeypatch.setattr(wecom.WeComClient, "get_department_names", fake_departments)
    monkeypatch.setattr(wecom.WeComClient, "upload_image", fake_upload)
    monkeypatch.setattr(wecom.WeComClient, "send_image", fake_send)


def test_full_set_of_tickets_with_reason(db, monkeypatch):
    patch_client(monkeypatch, detail=build_detail())
    event = make_event(db)

    asyncio.run(wecom.process_approval_event(db, event))

    tickets = db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).all()
    assert len(tickets) == 6
    assert {t.meal_type for t in tickets} == {"breakfast"}
    assert {t.diner_count for t in tickets} == {6}
    assert {t.diner_index for t in tickets} == {1, 2, 3, 4, 5, 6}
    assert {str(t.meal_date) for t in tickets} == {"2026-10-22"}
    assert {t.apply_reason for t in tickets} == {"恩捷人员审核"}
    assert {t.push_count for t in tickets} == {1}
    assert all(t.last_push_error is None for t in tickets)

    db.refresh(event)
    assert event.processed is True
    assert "已生成 6 张饭票" in event.process_result


def test_detail_failure_creates_no_tickets(db, monkeypatch):
    patch_client(monkeypatch, detail_error=RuntimeError("45009 接口调用超过限制"))
    event = make_event(db)

    with pytest.raises(wecom.ApprovalError):
        asyncio.run(wecom.process_approval_event(db, event))

    tickets = db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).all()
    assert tickets == []
    db.refresh(event)
    assert event.processed is False


def test_missing_meal_type_fails_instead_of_defaulting(db, monkeypatch):
    detail = build_detail()
    detail["info"]["apply_data"]["contents"] = detail["info"]["apply_data"]["contents"][:2]
    patch_client(monkeypatch, detail=detail)
    event = make_event(db)

    with pytest.raises(wecom.ApprovalError) as excinfo:
        asyncio.run(wecom.process_approval_event(db, event))

    assert "餐别" in str(excinfo.value)
    assert db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).all() == []


def test_revoked_approval_voids_unused_tickets(db, monkeypatch):
    patch_client(monkeypatch, detail=build_detail())
    event = make_event(db)
    asyncio.run(wecom.process_approval_event(db, event))

    event.sp_status = 3
    event.processed = False
    db.commit()
    asyncio.run(wecom.process_approval_event(db, event))

    tickets = db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).all()
    assert {t.status for t in tickets} == {"void"}


def test_resend_rotates_token_and_tracks_push(db, monkeypatch):
    patch_client(monkeypatch, detail=build_detail())
    event = make_event(db)
    asyncio.run(wecom.process_approval_event(db, event))
    ticket = db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).first()
    old_hash = ticket.token_hash

    asyncio.run(wecom.resend_ticket(db, ticket))

    assert ticket.token_hash != old_hash
    assert ticket.push_count == 2
    assert ticket.last_push_error is None


def test_resend_rejects_used_ticket(db, monkeypatch):
    patch_client(monkeypatch, detail=build_detail())
    event = make_event(db)
    asyncio.run(wecom.process_approval_event(db, event))
    ticket = db.scalars(
        select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)
    ).first()
    ticket.status = "used"
    db.commit()

    with pytest.raises(Exception) as excinfo:
        asyncio.run(wecom.resend_ticket(db, ticket))
    assert "只能补发未核销" in str(excinfo.value) or "未核销" in str(excinfo.value)
