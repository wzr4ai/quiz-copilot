from __future__ import annotations

import random
from datetime import datetime
from typing import Dict, List

from app.models.schemas import (
    Bank,
    BankCreate,
    BankUpdate,
    Question,
    QuestionCreate,
    QuestionUpdate,
    WrongQuestionSummary,
)


class InMemoryStore:
    """Simple in-memory data holder to unblock frontend integration before DB lands."""

    def __init__(self) -> None:
        self.banks: Dict[int, Bank] = {}
        self.questions: Dict[int, Question] = {}
        self.wrong_records: List[WrongQuestionSummary] = []
        self._bank_id = 1
        self._question_id = 1
        self._seed()

    def _seed(self) -> None:
        bank = self.create_bank(BankCreate(title="示例题库 A", description="AI 生成示例"))
        self.create_question(
            QuestionCreate(
                bank_id=bank.id,
                type="choice_single",
                content="下列哪种水果是红色的？",
                options=[
                    {"key": "A", "text": "苹果"},
                    {"key": "B", "text": "香蕉"},
                    {"key": "C", "text": "葡萄"},
                ],
                standard_answer="A",
                analysis="苹果通常是红色的，香蕉是黄色，葡萄多为紫色/绿色。",
            )
        )
        self.create_question(
            QuestionCreate(
                bank_id=bank.id,
                type="short_answer",
                content="简述“智能刷题”的两个核心价值点。",
                standard_answer="录题更快；判分更智能。",
                analysis="强调 AI 导入题库与 AI 判分两条线。",
            )
        )

    def create_bank(self, payload: BankCreate) -> Bank:
        bank = Bank(id=self._bank_id, **payload.model_dump())
        self.banks[bank.id] = bank
        self._bank_id += 1
        return bank

    def delete_bank(self, bank_id: int) -> None:
        self.banks.pop(bank_id, None)
        self.questions = {qid: q for qid, q in self.questions.items() if q.bank_id != bank_id}
        self.wrong_records = [record for record in self.wrong_records if record.question.bank_id != bank_id]

    def update_bank(self, bank_id: int, payload: BankUpdate) -> Bank:
        bank = self.banks.get(bank_id)
        if bank is None:
            raise KeyError("bank not found")
        update_data = payload.model_dump(exclude_none=True)
        updated = Bank(id=bank.id, **{**bank.model_dump(), **update_data})
        self.banks[bank_id] = updated
        return updated

    def list_banks(self) -> List[Bank]:
        return list(self.banks.values())

    def create_question(self, payload: QuestionCreate) -> Question:
        question = Question(id=self._question_id, **payload.model_dump())
        self.questions[question.id] = question
        self._question_id += 1
        return question

    def update_question(self, question_id: int, payload: QuestionUpdate) -> Question:
        question = self.questions.get(question_id)
        if question is None:
            raise KeyError("question not found")

        update_data = payload.model_dump(exclude_none=True)
        question_data = question.model_dump()
        question_data.update(update_data)
        updated = Question(**question_data)
        self.questions[question_id] = updated

        # also update any wrong records to keep content in sync
        for idx, record in enumerate(self.wrong_records):
            if record.question.id == question_id:
                self.wrong_records[idx] = WrongQuestionSummary(
                    question=updated,
                    user_answer=record.user_answer,
                    correct_answer=updated.standard_answer,
                    created_at=record.created_at,
                )
        return updated

    def list_questions(self, bank_id: int | None = None) -> List[Question]:
        if bank_id is None:
            return list(self.questions.values())
        return [q for q in self.questions.values() if q.bank_id == bank_id]

    def delete_question(self, question_id: int) -> None:
        if question_id in self.questions:
            del self.questions[question_id]
        self.wrong_records = [record for record in self.wrong_records if record.question.id != question_id]

    def get_question(self, question_id: int) -> Question | None:
        return self.questions.get(question_id)

    def get_wrong_question_ids(self) -> List[int]:
        latest: Dict[int, WrongQuestionSummary] = {}
        for record in self.wrong_records:
            latest[record.question.id] = record
        return [qid for qid, record in latest.items() if record.user_answer != record.correct_answer]

    def record_answer(
        self,
        question: Question,
        user_answer: str,
        is_correct: bool,
    ) -> WrongQuestionSummary | None:
        summary = WrongQuestionSummary(
            question=question,
            user_answer=user_answer,
            correct_answer=question.standard_answer,
            created_at=datetime.utcnow(),
        )
        self.wrong_records.append(summary)
        if is_correct:
            # keep a "correct" record to overwrite older wrong states
            summary.user_answer = question.standard_answer
        return None if is_correct else summary

    def list_wrong_records(self) -> List[WrongQuestionSummary]:
        latest: Dict[int, WrongQuestionSummary] = {}
        for record in self.wrong_records:
            latest[record.question.id] = record
        return list(latest.values())

    def pick_questions_for_session(self, bank_id: int, mode: str = "random") -> List[Question]:
        questions = self.list_questions(bank_id=bank_id)
        if mode == "wrong":
            wrong_ids = set(self.get_wrong_question_ids())
            questions = [q for q in questions if q.id in wrong_ids]
        if mode == "random":
            random.shuffle(questions)
        return questions


store = InMemoryStore()
