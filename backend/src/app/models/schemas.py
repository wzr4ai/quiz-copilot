from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Option(BaseModel):
    key: str = Field(..., description="选项标识，如 A/B/C")
    text: str = Field(..., description="选项内容")


class Bank(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_public: bool = False


class BankCreate(BaseModel):
    title: str
    description: Optional[str] = None
    is_public: bool = False


class BankUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class BankMergeRequest(BaseModel):
    title: str
    description: Optional[str] = None
    is_public: bool = False
    source_bank_ids: List[int]


class BankMergeResponse(BaseModel):
    bank: Bank
    merged_questions: int
    source_bank_ids: List[int]


class QuestionBase(BaseModel):
    bank_id: int
    type: str = Field(..., description="choice_single | choice_multi | short_answer")
    content: str
    options: List[Option] = Field(default_factory=list)
    standard_answer: str
    analysis: Optional[str] = None
    is_favorited: bool = False


class Question(QuestionBase):
    id: int


class QuestionCreate(QuestionBase):
    """Payload when creating a question manually or via AI."""


class QuestionUpdate(BaseModel):
    bank_id: Optional[int] = None
    type: Optional[str] = None
    content: Optional[str] = None
    options: Optional[List[Option]] = None
    standard_answer: Optional[str] = None
    analysis: Optional[str] = None


class ManualQuestionRequest(QuestionCreate):
    """Alias kept for clarity in API signatures."""


class PaginatedQuestions(BaseModel):
    items: List[Question]
    total: int
    page: int
    page_size: int


class AIQuizRequest(BaseModel):
    bank_id: int
    text: str


class AIImageQuizRequest(BaseModel):
    bank_id: int
    image_base64: str


class BatchImportRequest(BaseModel):
    bank_id: int
    directory: str
    recursive: bool = True


class BatchImportFileResult(BaseModel):
    filename: str
    imported: int = 0
    duplicates: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class BatchImportResponse(BaseModel):
    total_files: int
    processed_files: int
    imported_questions: int
    duplicate_questions: int
    failed_files: int
    file_results: List[BatchImportFileResult]


class StudyQuestion(BaseModel):
    id: int
    content: str
    type: str
    options: List[Option] = Field(default_factory=list)
    standard_answer: Optional[str] = None
    analysis: Optional[str] = None
    is_favorited: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    questions: List[StudyQuestion]


class SubmitAnswer(BaseModel):
    question_id: int
    answer: str


class SubmitRequest(BaseModel):
    session_id: str
    answers: List[SubmitAnswer]


class WrongQuestionSummary(BaseModel):
    question: Question
    user_answer: str
    correct_answer: str
    created_at: datetime


class SubmitResult(BaseModel):
    correct_count: int
    total: int
    score: int
    wrong_questions: List[WrongQuestionSummary] = Field(default_factory=list)


class WrongRecord(BaseModel):
    question_id: int
    user_answer: str
    correct_answer: str
    is_correct: bool
    created_at: datetime


class QuestionIssue(BaseModel):
    id: int
    question_id: int
    bank_id: int
    reason: str
    status: str
    created_at: datetime


class QuestionIssueUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


class QuestionIssueWithQuestion(QuestionIssue):
    question: Question


class SmartPracticeSettingsPayload(BaseModel):
    bank_ids: List[int] = Field(default_factory=list)
    target_count: int = Field(default=50, ge=1)
    guaranteed_low_count: int = Field(default=20, ge=0, description="每批保底抽取的低计数题数量")
    type_ratio: dict = Field(default_factory=dict)
    realtime_analysis: bool = False


class SmartPracticeSettingsResponse(SmartPracticeSettingsPayload):
    id: int
    updated_at: datetime


class SmartPracticeStatus(BaseModel):
    has_active: bool
    session_id: Optional[str] = None
    status: Optional[str] = None
    current_group_index: Optional[int] = None
    round: Optional[int] = None
    realtime_analysis: Optional[bool] = None
    pending_wrong: Optional[int] = None
    total_answered: Optional[int] = None
    total_correct: Optional[int] = None
    total_wrong: Optional[int] = None
    reinforce_remaining: Optional[int] = None
    practice_count_stats: Optional[dict[int, int]] = None
    lowest_count_remaining: Optional[int] = None
    per_bank_stats: Optional[list["SmartPracticeBankStats"]] = None


class SmartPracticeBankStats(BaseModel):
    bank_id: int
    title: str
    practice_count_stats: dict[int, int] = Field(default_factory=dict)
    lowest_count_remaining: Optional[int] = None


class SmartPracticeQuestion(BaseModel):
    id: int
    content: str
    type: str
    options: List[Option] = Field(default_factory=list)
    analysis: Optional[str] = None
    standard_answer: Optional[str] = None
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    practice_count: Optional[int] = None
    counted: Optional[bool] = None


class SmartPracticeSelectionItem(BaseModel):
    type: str
    count_min: int
    count_next: int
    count_by_level: dict[int, int] = Field(default_factory=dict)


class SmartPracticeGroup(BaseModel):
    session_id: str
    group_id: int
    group_index: int
    mode: str
    round: int
    total_questions: int
    realtime_analysis: bool
    current_question_index: Optional[int] = None
    lowest_count_remaining: Optional[int] = None
    selection_summary: Optional[List[SmartPracticeSelectionItem]] = None
    questions: List[SmartPracticeQuestion]


class SmartPracticeAnswerRequest(BaseModel):
    question_id: int
    answer: str
    current_index: Optional[int] = None


class SmartPracticeAnswerResponse(BaseModel):
    is_correct: bool
    counted: bool
    analysis: Optional[str] = None
    standard_answer: Optional[str] = None


class SmartPracticeToggleRequest(BaseModel):
    realtime_analysis: bool


class SmartPracticeFeedbackRequest(BaseModel):
    question_id: int
    reason: str = Field(default="")
