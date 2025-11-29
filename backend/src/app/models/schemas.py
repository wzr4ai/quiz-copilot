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
