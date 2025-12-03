from __future__ import annotations

import math
import random
import re
from datetime import datetime
from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import schemas
from app.models.db_models import (
    Bank,
    Question,
    SmartPracticeAnswer,
    SmartPracticeFeedback,
    SmartPracticeGroup,
    SmartPracticeItem,
    SmartPracticeSession,
    SmartPracticeSettings,
    User,
)

# 开关：是否尊重用户所选题库，仅从中抽题 若为 False，则从所有可访问题库中抽题
USE_SELECTED_BANKS_FOR_SMART_PRACTICE = True # Temporary: False means draw from all accessible banks


def _normalize_answer(val: str, qtype: str) -> str:
    if qtype == "choice_multi":
        # 支持空格/中英文逗号/分号/斜杠/顿号/竖线等常见分隔，顺序不敏感
        raw_parts = re.split(r"[,\s;；、/|]+", val.replace("，", ","))
        cleaned = [p.strip().upper() for p in raw_parts if p.strip()]
        # 兼容无分隔符且连续字母的写法，如 "ABC"
        if len(cleaned) == 1 and len(cleaned[0]) > 1 and cleaned[0].isalpha():
            cleaned = list(cleaned[0])
        normalized = sorted({p for p in cleaned if p})
        return ",".join(normalized)
    return val.strip().upper()


def _ensure_banks_accessible(db: Session, bank_ids: list[int], current_user: User) -> list[Bank]:
    banks: list[Bank] = []
    for bank_id in bank_ids:
        bank = db.get(Bank, bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"题库 {bank_id} 不存在")
        if current_user.role != "admin" and not bank.is_public:
            raise HTTPException(status_code=403, detail=f"无权访问题库 {bank_id}")
        banks.append(bank)
    return banks


def _resolve_bank_ids_for_draw(db: Session, requested_bank_ids: list[int], current_user: User) -> list[int]:
    """Return bank ids to use for drawing questions. Toggle global to respect user selection."""
    if USE_SELECTED_BANKS_FOR_SMART_PRACTICE:
        return requested_bank_ids
    query = select(Bank.id)
    if current_user.role != "admin":
        query = query.where(Bank.is_public.is_(True))
    rows = db.exec(query).all()
    return [row[0] if isinstance(row, tuple) else row for row in rows]


def _load_questions(db: Session, bank_ids: list[int], current_user: User) -> list[Question]:
    _ensure_banks_accessible(db, bank_ids, current_user)
    query = select(Question).where(Question.bank_id.in_(bank_ids), Question.practice_count >= 0)
    if current_user.role != "admin":
        query = query.join(Bank, Bank.id == Question.bank_id).where(Bank.is_public.is_(True))
    questions = db.exec(query).all()
    return questions


def _allocate_counts(target_count: int, type_ratio: dict) -> dict[str, int]:
    if not type_ratio:
        return {}
    total_ratio = sum(float(v) for v in type_ratio.values()) or 0
    if total_ratio <= 0:
        return {}

    counts: dict[str, int] = {}
    remainders: list[tuple[str, float]] = []
    remaining = target_count
    for qtype, ratio_val in type_ratio.items():
        raw = target_count * float(ratio_val) / total_ratio
        base = int(raw)
        counts[qtype] = base
        remaining -= base
        remainders.append((qtype, raw - base))

    # 分配剩余数量给余数最大的题型
    remainders.sort(key=lambda x: x[1], reverse=True)
    for qtype, _ in remainders:
        if remaining <= 0:
            break
        counts[qtype] += 1
        remaining -= 1
    return counts


def _allocate_target_per_type(types: list[str], target_count: int, type_ratio: dict) -> dict[str, int]:
    """Return per-type target counts. If type_ratio is empty, split evenly."""
    if not types:
        return {}
    if type_ratio:
        return _allocate_counts(target_count, type_ratio)
    base = target_count // len(types)
    remainder = target_count % len(types)
    result: dict[str, int] = {t: base for t in types}
    for t in types[:remainder]:
        result[t] += 1
    return result


def _select_questions_by_ratio(
    questions: list[Question], target_count: int, type_ratio: dict, guaranteed_low_count: int | None = None
) -> tuple[list[Question], list[schemas.SmartPracticeSelectionItem]]:
    if not questions:
        return [], []

    # 允许的题型：type_ratio 仅作为过滤器；默认限单选/多选/判断
    selected_types = [t for t, v in type_ratio.items() if v] if type_ratio else ["choice_single", "choice_multi", "choice_judgment"]
    valid_questions = [q for q in questions if q.type in selected_types and q.practice_count >= 0]
    if not valid_questions:
        return [], []

    guaranteed_quota = min(guaranteed_low_count if guaranteed_low_count is not None else 20, target_count)
    weighted_quota = max(0, target_count - guaranteed_quota)

    # 阶段一：全局绝对保底
    random.shuffle(valid_questions)
    valid_questions.sort(key=lambda q: q.practice_count)
    picked_guaranteed = valid_questions[:guaranteed_quota]
    picked_ids = {q.id for q in picked_guaranteed}

    # 阶段二：加权补位（Efraimidis-Spirakis）
    remaining_pool = [q for q in valid_questions if q.id not in picked_ids]
    scored: list[tuple[float, Question]] = []
    for q in remaining_pool:
        score = random.random() ** (q.practice_count + 1)
        scored.append((score, q))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked_weighted = [q for _, q in scored[:weighted_quota]]

    # 合并与打乱
    final_list = picked_guaranteed + picked_weighted
    if len(final_list) < target_count:
        # 若题库不足，尝试再补足剩余
        leftovers = [q for q in remaining_pool if q.id not in {x.id for x in picked_weighted}]
        random.shuffle(leftovers)
        final_list.extend(leftovers[: target_count - len(final_list)])
    random.shuffle(final_list)

    # 摘要：统计各题型选中数量
    summary: list[schemas.SmartPracticeSelectionItem] = []
    for qtype in selected_types:
        counts_by_level: dict[int, int] = {}
        for q in final_list:
            if q.type != qtype:
                continue
            counts_by_level[q.practice_count] = counts_by_level.get(q.practice_count, 0) + 1
        total = sum(counts_by_level.values())
        summary.append(
            schemas.SmartPracticeSelectionItem(
                type=qtype,
                count_min=total,
                count_next=0,
                count_by_level=counts_by_level,
            )
        )

    return final_list, summary


def _prioritize_lowest_count(questions: list[Question], target_count: int) -> list[Question]:
    if not questions:
        return []
    random.shuffle(questions)
    questions.sort(key=lambda q: q.practice_count)
    return questions[:target_count]


def _compute_lowest_count_remaining(db: Session, bank_ids: list[int], allowed_types: list[str] | None = None) -> int | None:
    if not bank_ids:
        return None
    query = select(Question.practice_count).where(Question.bank_id.in_(bank_ids), Question.practice_count >= 0)
    if allowed_types:
        query = query.where(Question.type.in_(allowed_types))
    rows = db.exec(query).all()
    counts = [row[0] if isinstance(row, tuple) else row for row in rows]
    if not counts:
        return None
    zeros = len([c for c in counts if c == 0])
    return zeros


def _build_group(
    db: Session,
    sp_session: SmartPracticeSession,
    questions: list[Question],
    mode: str,
    group_index: int,
) -> SmartPracticeGroup:
    group = SmartPracticeGroup(
        session_id=sp_session.id,
        group_index=group_index,
        mode=mode,
        total_questions=len(questions),
    )
    db.add(group)
    db.flush()  # ensure group.id
    for idx, q in enumerate(questions):
        db.add(
            SmartPracticeItem(
                group_id=group.id,
                question_id=q.id,
                question_type=q.type,
                position=idx,
                is_reinforce=mode == "reinforce",
            )
        )
    return group


def _serialize_group(
    db: Session,
    group: SmartPracticeGroup,
    questions: Iterable[Question],
    sp_session: SmartPracticeSession,
    current_user: User,
    selection_summary: list[schemas.SmartPracticeSelectionItem] | None = None,
) -> schemas.SmartPracticeGroup:
    realtime = sp_session.realtime_analysis
    item_question_ids = [
        item.question_id for item in db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == group.id)).all()
    ]
    answers = {
        a.question_id: a
        for a in db.exec(
            select(SmartPracticeAnswer).where(
                SmartPracticeAnswer.session_id == sp_session.id,
                SmartPracticeAnswer.question_id.in_(item_question_ids),
                SmartPracticeAnswer.answered_at >= group.created_at,
            )
        ).all()
    }
    question_map: list[schemas.SmartPracticeQuestion] = []
    for q in questions:
        answer = answers.get(q.id)
        question_map.append(
            schemas.SmartPracticeQuestion(
                id=q.id,
                content=q.content,
                type=q.type,
                options=[schemas.Option(**opt) for opt in q.options or []],
                analysis=q.analysis,
                standard_answer=q.standard_answer,
                user_answer=answer.user_answer if answer else None,
                is_correct=answer.is_correct if answer else None,
                practice_count=q.practice_count,
                counted=answer.counted if answer else None,
            )
        )
    # 动态根据当前抽题范围计算剩余 0 次计数的题目数量（优先使用用户选择的题库）
    selected_bank_ids = sp_session.settings_snapshot.get("bank_ids", [])
    resolved_banks = selected_bank_ids if selected_bank_ids else _resolve_bank_ids_for_draw(db, selected_bank_ids, current_user)
    allowed_types = [t for t, v in (sp_session.settings_snapshot.get("type_ratio") or {}).items() if v]
    computed_lowest = _compute_lowest_count_remaining(db, resolved_banks, allowed_types) if resolved_banks else None
    return schemas.SmartPracticeGroup(
        session_id=sp_session.id,
        group_id=group.id,
        group_index=group.group_index,
        mode=group.mode,
        round=sp_session.round,
        total_questions=group.total_questions,
        realtime_analysis=realtime,
        current_question_index=sp_session.current_question_index,
        lowest_count_remaining=computed_lowest if computed_lowest is not None else sp_session.lowest_count_remaining,
        selection_summary=selection_summary,
        questions=question_map,
    )


def get_latest_settings(db: Session, user_id: int) -> SmartPracticeSettings | None:
    return (
        db.exec(
            select(SmartPracticeSettings)
            .where(SmartPracticeSettings.user_id == user_id)
            .order_by(SmartPracticeSettings.updated_at.desc())
        )
        .first()
    )


def save_settings(db: Session, payload: schemas.SmartPracticeSettingsPayload, user: User) -> SmartPracticeSettings:
    if not payload.bank_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个题库")
    _ensure_banks_accessible(db, payload.bank_ids, user)
    now = datetime.utcnow()
    payload.realtime_analysis = True
    settings = SmartPracticeSettings(
        user_id=user.id,
        bank_ids=payload.bank_ids,
        target_count=payload.target_count,
        guaranteed_low_count=payload.guaranteed_low_count if payload.guaranteed_low_count is not None else 20,
        type_ratio=payload.type_ratio or {},
        realtime_analysis=True,
        created_at=now,
        updated_at=now,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_active_session(db: Session, user: User) -> SmartPracticeSession | None:
    return (
        db.exec(
            select(SmartPracticeSession)
            .where(
                SmartPracticeSession.user_id == user.id,
                SmartPracticeSession.status != "completed",
            )
            .order_by(SmartPracticeSession.created_at.desc())
        )
        .first()
    )


def start_session(db: Session, user: User) -> schemas.SmartPracticeGroup:
    settings = get_latest_settings(db, user.id)
    if not settings:
        raise HTTPException(status_code=400, detail="请先配置智能刷题设置")

    active = get_active_session(db, user)
    if active and active.status in {"in_progress", "reinforce"}:
        raise HTTPException(status_code=409, detail="已有进行中的智能刷题，请先完成或继续当前刷题")

    effective_bank_ids = _resolve_bank_ids_for_draw(db, settings.bank_ids, user)
    if not effective_bank_ids:
        raise HTTPException(status_code=400, detail="暂无可用题库")

    questions = _load_questions(db, effective_bank_ids, user)
    if not questions:
        raise HTTPException(status_code=400, detail="所选题库暂无可用题目")
    selected, summary = _select_questions_by_ratio(
        questions, settings.target_count, settings.type_ratio, settings.guaranteed_low_count
    )
    if not selected:
        raise HTTPException(status_code=400, detail="无法生成题组，题库题目数量不足")

    now = datetime.utcnow()
    snapshot = settings.model_dump(exclude={"created_at", "updated_at", "id"})
    allowed_types = [t for t, v in (settings.type_ratio or {}).items() if v]
    lowest_remaining = _compute_lowest_count_remaining(db, effective_bank_ids, allowed_types)
    sp_session = SmartPracticeSession(
        id=str(uuid4()),
        user_id=user.id,
        settings_snapshot=snapshot,
        status="in_progress",
        current_group_index=0,
        current_question_index=0,
        round=1,
        realtime_analysis=True,
        lowest_count_remaining=lowest_remaining,
        created_at=now,
        updated_at=now,
    )
    db.add(sp_session)
    db.flush()  # persist session to satisfy FK before creating group
    group = _build_group(db, sp_session, selected, mode="normal", group_index=0)
    db.commit()
    db.refresh(sp_session)
    db.refresh(group)
    return _serialize_group(db, group, selected, sp_session, user, selection_summary=summary)


def get_current_group(db: Session, session_id: str, user: User) -> schemas.SmartPracticeGroup:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    group = _get_current_group(db, sp_session)
    questions = _get_questions_for_group(db, group)
    return _serialize_group(db, group, questions, sp_session, user)


def get_status(db: Session, user: User) -> schemas.SmartPracticeStatus:
    active = get_active_session(db, user)
    if not active:
        return schemas.SmartPracticeStatus(has_active=False)

    current_group = (
        db.exec(
            select(SmartPracticeGroup)
            .where(
                SmartPracticeGroup.session_id == active.id,
                SmartPracticeGroup.group_index == active.current_group_index,
            )
            .order_by(SmartPracticeGroup.group_index.desc())
        )
        .first()
        if active
        else None
    )
    pending_wrong = None
    total_answered = None
    total_correct = None
    total_wrong = None
    reinforce_remaining = None
    practice_count_stats = None
    lowest_count_remaining = None
    per_bank_stats: list[schemas.SmartPracticeBankStats] | None = None
    allowed_types = [t for t, v in (active.settings_snapshot.get("type_ratio") or {}).items() if v]
    if current_group:
        item_question_ids = {
            item.question_id
            for item in db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == current_group.id)).all()
        }
        # 仅统计当前组内、且回答时间不早于组创建时间的最新作答
        answers = db.exec(
            select(SmartPracticeAnswer).where(
                SmartPracticeAnswer.session_id == active.id,
                SmartPracticeAnswer.question_id.in_(item_question_ids),
                SmartPracticeAnswer.answered_at >= current_group.created_at,
            )
        ).all()
        answered: dict[int, SmartPracticeAnswer] = {}
        for ans in answers:
            prev = answered.get(ans.question_id)
            if not prev or ans.answered_at >= prev.answered_at:
                answered[ans.question_id] = ans

        missing = item_question_ids - set(answered.keys())
        wrong_ids = [qid for qid, ans in answered.items() if not ans.is_correct]
        pending_wrong = len(wrong_ids) + len(missing)
        total_answered = len(answered)
        total_correct = len([a for a in answered.values() if a.is_correct])
        total_wrong = len([a for a in answered.values() if not a.is_correct])
        reinforce_remaining = pending_wrong if active.status == "reinforce" else None
        # 统计当前设置题库下题目的计数分布（仅使用用户选择的题库）
        selected_bank_ids = active.settings_snapshot.get("bank_ids", [])
        if selected_bank_ids:
            stats_rows = db.exec(
                select(Question.practice_count)
                .where(
                    Question.bank_id.in_(selected_bank_ids),
                    Question.practice_count >= 0,
                    Question.type.in_(allowed_types) if allowed_types else True,
                )
                .order_by(Question.practice_count)
            ).all()
            buckets: dict[int, int] = {}
            for row in stats_rows:
                cnt = row[0] if isinstance(row, tuple) else row
                buckets[cnt] = buckets.get(cnt, 0) + 1
            practice_count_stats = buckets
            lowest_count_remaining = _compute_lowest_count_remaining(db, selected_bank_ids, allowed_types)
            # 分题库统计（仅展示用户已选题库）
            banks = db.exec(select(Bank).where(Bank.id.in_(selected_bank_ids))).all()
            bank_title_map = {b.id: b.title for b in banks}
            per_bank_stats = []
            for bid in selected_bank_ids:
                bank_rows = db.exec(
                    select(Question.practice_count)
                    .where(
                        Question.bank_id == bid,
                        Question.practice_count >= 0,
                        Question.type.in_(allowed_types) if allowed_types else True,
                    )
                    .order_by(Question.practice_count)
                ).all()
                bank_buckets: dict[int, int] = {}
                for row in bank_rows:
                    cnt = row[0] if isinstance(row, tuple) else row
                    bank_buckets[cnt] = bank_buckets.get(cnt, 0) + 1
                per_bank_stats.append(
                    schemas.SmartPracticeBankStats(
                        bank_id=bid,
                        title=bank_title_map.get(bid, f"题库 {bid}"),
                        practice_count_stats=bank_buckets,
                        lowest_count_remaining=bank_buckets.get(0, 0),
                    )
                )

    return schemas.SmartPracticeStatus(
        has_active=True,
        session_id=active.id,
        status=active.status,
        current_group_index=active.current_group_index,
        round=active.round,
        realtime_analysis=active.realtime_analysis,
        pending_wrong=pending_wrong,
        total_answered=total_answered,
        total_correct=total_correct,
        total_wrong=total_wrong,
        reinforce_remaining=reinforce_remaining,
        practice_count_stats=practice_count_stats,
        lowest_count_remaining=lowest_count_remaining if lowest_count_remaining is not None else active.lowest_count_remaining,
        per_bank_stats=per_bank_stats,
    )


def toggle_realtime_analysis(db: Session, session_id: str, value: bool, user: User) -> SmartPracticeSession:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    sp_session.realtime_analysis = True
    sp_session.updated_at = datetime.utcnow()
    db.add(sp_session)
    db.commit()
    db.refresh(sp_session)
    return sp_session


def _get_current_group(db: Session, sp_session: SmartPracticeSession) -> SmartPracticeGroup:
    group = (
        db.exec(
            select(SmartPracticeGroup)
            .where(
                SmartPracticeGroup.session_id == sp_session.id,
                SmartPracticeGroup.group_index == sp_session.current_group_index,
            )
            .order_by(SmartPracticeGroup.group_index.desc())
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="未找到当前题组")
    return group


def _get_questions_for_group(db: Session, group: SmartPracticeGroup) -> list[Question]:
    items = db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == group.id)).all()
    question_ids = [item.question_id for item in items]
    questions = db.exec(select(Question).where(Question.id.in_(question_ids))).all()
    questions_map = {q.id: q for q in questions}
    ordered = [questions_map[qid] for qid in question_ids if qid in questions_map]
    return ordered


def answer_question(
    db: Session, session_id: str, payload: schemas.SmartPracticeAnswerRequest, user: User
) -> schemas.SmartPracticeAnswerResponse:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    if sp_session.status == "completed":
        raise HTTPException(status_code=400, detail="会话已结束")

    group = _get_current_group(db, sp_session)
    items = db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == group.id)).all()
    item_ids = {item.question_id for item in items}
    if payload.question_id not in item_ids:
        raise HTTPException(status_code=400, detail="题目不属于当前题组")
    # persist当前位置
    if payload.current_index is not None:
        sp_session.current_question_index = payload.current_index
        sp_session.updated_at = datetime.utcnow()
        db.add(sp_session)

    question = db.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    raw_answer = payload.answer.strip()
    normalized_answer = _normalize_answer(raw_answer, question.type)
    normalized_standard = _normalize_answer(question.standard_answer.strip(), question.type)
    is_correct = normalized_answer == normalized_standard and normalized_standard != ""
    counted = group.mode != "reinforce" and is_correct
    if not is_correct:
        question.practice_count = 0
        db.add(question)

    existing = db.exec(
        select(SmartPracticeAnswer)
        .where(
            SmartPracticeAnswer.session_id == session_id,
            SmartPracticeAnswer.question_id == payload.question_id,
        )
        .order_by(SmartPracticeAnswer.answered_at.desc())
    ).first()
    if existing and existing.answered_at < group.created_at:
        # 旧组的答案，对当前组无效
        existing = None

    # 考试模式：仅记录最终答案，不计数，最终在组完成时统一结算
    if not sp_session.realtime_analysis:
        if existing:
            existing.user_answer = raw_answer
            existing.is_correct = is_correct
            existing.counted = False
            existing.answered_at = datetime.utcnow()
            db.add(existing)
        else:
            db.add(
                SmartPracticeAnswer(
                    session_id=session_id,
                    question_id=payload.question_id,
                    user_answer=raw_answer,
                    is_correct=is_correct,
                    counted=False,
                    answered_at=datetime.utcnow(),
                )
            )
        db.commit()
        return schemas.SmartPracticeAnswerResponse(
            is_correct=False,  # 考试模式过程不提示正误
            counted=False,
            analysis=None,
            standard_answer=None,
        )

    # 刷题模式：一旦答错，视为错题，后续修正也不计数+1
    if existing:
        if group.mode == "reinforce":
            existing.user_answer = raw_answer
            existing.is_correct = is_correct
            existing.counted = False
            existing.answered_at = datetime.utcnow()
            db.add(existing)
            if not is_correct:
                question.practice_count = 0
                db.add(question)
            db.commit()
            return schemas.SmartPracticeAnswerResponse(
                is_correct=existing.is_correct,
                counted=False,
                analysis=question.analysis if sp_session.realtime_analysis else None,
                standard_answer=question.standard_answer if sp_session.realtime_analysis else None,
            )

        if existing.counted:
            return schemas.SmartPracticeAnswerResponse(
                is_correct=existing.is_correct,
                counted=existing.counted,
                analysis=question.analysis if sp_session.realtime_analysis else None,
                standard_answer=question.standard_answer if sp_session.realtime_analysis else None,
            )
        if not existing.is_correct:
            existing.user_answer = raw_answer
            existing.is_correct = is_correct
            existing.answered_at = datetime.utcnow()
            db.add(existing)
            if not is_correct:
                question.practice_count = 0
                db.add(question)
            db.commit()
            return schemas.SmartPracticeAnswerResponse(
                is_correct=existing.is_correct,
                counted=False,
                analysis=question.analysis if sp_session.realtime_analysis else None,
                standard_answer=question.standard_answer if sp_session.realtime_analysis else None,
            )
        # 之前是未计数的正确（如刷题模式未锁定）
        existing.user_answer = raw_answer
        existing.is_correct = is_correct
        should_increment = counted and not existing.counted and group.mode != "reinforce"
        existing.counted = existing.counted or should_increment
        existing.answered_at = datetime.utcnow()
        db.add(existing)
        if should_increment:
            question.practice_count += 1
            db.add(question)
        db.commit()
        return schemas.SmartPracticeAnswerResponse(
            is_correct=existing.is_correct,
            counted=existing.counted,
            analysis=question.analysis if sp_session.realtime_analysis else None,
            standard_answer=question.standard_answer if sp_session.realtime_analysis else None,
        )

    answer_record = SmartPracticeAnswer(
        session_id=session_id,
        question_id=payload.question_id,
        user_answer=raw_answer,
        is_correct=is_correct,
        counted=counted and group.mode != "reinforce",
        answered_at=datetime.utcnow(),
    )
    db.add(answer_record)

    if answer_record.counted:
        question.practice_count += 1
        db.add(question)

    db.commit()
    return schemas.SmartPracticeAnswerResponse(
        is_correct=answer_record.is_correct,
        counted=answer_record.counted,
        analysis=question.analysis if sp_session.realtime_analysis else None,
        standard_answer=question.standard_answer if sp_session.realtime_analysis else None,
    )


def _get_question_analysis(db: Session, question_id: int) -> str | None:
    question = db.get(Question, question_id)
    return question.analysis if question else None


def _get_question_answer(db: Session, question_id: int) -> str | None:
    question = db.get(Question, question_id)
    return question.standard_answer if question else None


def _wrong_questions_for_group(db: Session, sp_session: SmartPracticeSession, group: SmartPracticeGroup) -> list[int]:
    items = db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == group.id)).all()
    item_question_ids = [item.question_id for item in items]
    answers = db.exec(
        select(SmartPracticeAnswer).where(
            SmartPracticeAnswer.session_id == sp_session.id,
            SmartPracticeAnswer.question_id.in_(item_question_ids),
        )
    ).all()
    # 只看当前组产生的作答（或更晚的更新），并保留每题最新一次
    recent_answers: dict[int, SmartPracticeAnswer] = {}
    for ans in answers:
        if ans.answered_at < group.created_at:
            continue
        prev = recent_answers.get(ans.question_id)
        if not prev or ans.answered_at >= prev.answered_at:
            recent_answers[ans.question_id] = ans
    answered_map = recent_answers
    missing = [qid for qid in item_question_ids if qid not in answered_map]
    if missing:
        raise HTTPException(status_code=400, detail="还有未作答的题目，无法进入下一组")

    # 考试模式：在提交组时统一判分并计数
    if not sp_session.realtime_analysis:
        current_answers = list(recent_answers.values())
        questions = db.exec(select(Question).where(Question.id.in_(item_question_ids))).all()
        qmap = {q.id: q for q in questions}
        for ans in current_answers:
            q = qmap.get(ans.question_id)
            if not q:
                continue
            normalized_answer = _normalize_answer(ans.user_answer.strip(), q.type)
            normalized_standard = _normalize_answer(q.standard_answer.strip(), q.type)
            is_correct = normalized_answer == normalized_standard and normalized_standard != ""
            was_counted = ans.counted
            ans.is_correct = is_correct
            ans.counted = is_correct and group.mode != "reinforce"
            ans.answered_at = datetime.utcnow()
            db.add(ans)
            if ans.counted and not was_counted:
                q.practice_count += 1
                db.add(q)
            if not is_correct:
                q.practice_count = 0
                db.add(q)
        db.commit()
        answered_map = {a.question_id: a for a in current_answers}

    wrong = [qid for qid, a in answered_map.items() if not a.is_correct]
    return wrong


def next_group(db: Session, session_id: str, user: User) -> schemas.SmartPracticeGroup:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    current_group = _get_current_group(db, sp_session)
    wrong_question_ids = _wrong_questions_for_group(db, sp_session, current_group)

    group_index = sp_session.current_group_index + 1
    questions: list[Question] = []
    mode = "normal"
    summary: list[schemas.SmartPracticeSelectionItem] | None = None

    if wrong_question_ids:
        # 进入或继续强化
        mode = "reinforce"
        sp_session.status = "reinforce"
        questions = db.exec(select(Question).where(Question.id.in_(wrong_question_ids))).all()
    else:
        # 强化结束或正常完成一组，开启下一轮
        if current_group.mode in {"reinforce", "normal"}:
            sp_session.round += 1
        sp_session.status = "in_progress"
        effective_bank_ids = _resolve_bank_ids_for_draw(
            db, sp_session.settings_snapshot.get("bank_ids", []), user  # type: ignore[arg-type]
        )
        if not effective_bank_ids:
            raise HTTPException(status_code=400, detail="暂无可用题库")
        questions = _load_questions(
            db, effective_bank_ids, user  # type: ignore[arg-type]
        )
        prefer_lowest = sp_session.round > 1
        selected, summary = _select_questions_by_ratio(
            questions,
            sp_session.settings_snapshot.get("target_count", 50),
            sp_session.settings_snapshot.get("type_ratio", {}),
            sp_session.settings_snapshot.get("guaranteed_low_count", 20),
        )
        if not selected:
            raise HTTPException(status_code=400, detail="题库题目不足，无法生成新题组")
        questions = selected
        allowed_types = [t for t, v in (sp_session.settings_snapshot.get("type_ratio", {}) or {}).items() if v]
        sp_session.lowest_count_remaining = _compute_lowest_count_remaining(
            db, effective_bank_ids, allowed_types
        )

    group = _build_group(db, sp_session, questions, mode=mode, group_index=group_index)
    sp_session.current_group_index = group_index
    sp_session.current_question_index = 0
    sp_session.updated_at = datetime.utcnow()
    db.add(sp_session)
    db.commit()
    db.refresh(group)
    return _serialize_group(
        db,
        group,
        questions,
        sp_session,
        user,
        selection_summary=summary if mode == "normal" else None,
    )


def finish_session(db: Session, session_id: str, user: User) -> None:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    sp_session.status = "completed"
    sp_session.updated_at = datetime.utcnow()
    db.add(sp_session)
    db.commit()


def feedback_and_skip(db: Session, session_id: str, payload: schemas.SmartPracticeFeedbackRequest, user: User) -> None:
    sp_session = db.get(SmartPracticeSession, session_id)
    if not sp_session or sp_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="智能刷题会话不存在")
    question = db.get(Question, payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    current_group = _get_current_group(db, sp_session)
    items = db.exec(select(SmartPracticeItem).where(SmartPracticeItem.group_id == current_group.id)).all()
    item_ids = {item.question_id for item in items}
    if payload.question_id not in item_ids:
        raise HTTPException(status_code=400, detail="题目不属于当前题组")

    # 保存反馈
    fb = SmartPracticeFeedback(
        session_id=session_id,
        user_id=user.id,
        question_id=payload.question_id,
        reason=payload.reason or "",
    )
    db.add(fb)

    # 标记为已答且正确，避免阻塞流程，但不计数，同时将计数置为 -1 以后续抽题剔除
    question.practice_count = -1
    db.add(question)
    existing = db.exec(
        select(SmartPracticeAnswer).where(
            SmartPracticeAnswer.session_id == session_id, SmartPracticeAnswer.question_id == payload.question_id
        )
    ).first()
    now = datetime.utcnow()
    if existing:
        existing.user_answer = payload.reason or "反馈剔除"
        existing.is_correct = True
        existing.counted = False
        existing.answered_at = now
        db.add(existing)
    else:
        db.add(
            SmartPracticeAnswer(
                session_id=session_id,
                question_id=payload.question_id,
                user_answer=payload.reason or "反馈剔除",
                is_correct=True,
                counted=False,
                answered_at=now,
            )
        )
    db.commit()
def reset_user_state(db: Session, user: User) -> None:
    """Remove all smart practice sessions and related records for the user."""
    sessions = db.exec(select(SmartPracticeSession).where(SmartPracticeSession.user_id == user.id)).all()
    session_ids = [s.id for s in sessions]
    if not session_ids:
        return
    group_ids = [
        g.id
        for g in db.exec(select(SmartPracticeGroup).where(SmartPracticeGroup.session_id.in_(session_ids))).all()
    ]
    if group_ids:
        db.exec(delete(SmartPracticeItem).where(SmartPracticeItem.group_id.in_(group_ids)))
        db.exec(delete(SmartPracticeGroup).where(SmartPracticeGroup.id.in_(group_ids)))
    db.exec(delete(SmartPracticeFeedback).where(SmartPracticeFeedback.session_id.in_(session_ids)))
    db.exec(delete(SmartPracticeAnswer).where(SmartPracticeAnswer.session_id.in_(session_ids)))
    db.exec(delete(SmartPracticeSession).where(SmartPracticeSession.id.in_(session_ids)))
    db.commit()
