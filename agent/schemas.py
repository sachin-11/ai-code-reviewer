from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    STYLE = "style"


class Issue(BaseModel):
    file: str
    line_start: int
    line_end: int
    severity: Severity
    category: Category
    title: str = Field(max_length=80)
    description: str
    suggestion: str
    confidence: float = Field(ge=0, le=1)
    fixable: bool = True


class Patch(BaseModel):
    issue: Issue
    file: str
    original_snippet: str
    fixed_snippet: str
    commit_message: str
    verified: bool = False
    verify_error: Optional[str] = None


class ReviewResult(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
    patches: list[Patch] = Field(default_factory=list)
    summary: str = ""
    fix_branch: Optional[str] = None
    fix_pr_url: Optional[str] = None


class AgentState(BaseModel):
    diff: str = ""
    changed_files: list[str] = Field(default_factory=list)
    file_contents: dict[str, str] = Field(default_factory=dict)
    repo_lang: str = "mixed"
    issues: list[Issue] = Field(default_factory=list)
    patches: list[Patch] = Field(default_factory=list)
    verified_patches: list[Patch] = Field(default_factory=list)
    fix_branch: Optional[str] = None
    fix_pr_url: Optional[str] = None
    pr_number: int = 0
    head_sha: str = ""
    base_sha: str = ""
    head_branch: str = ""
    base_branch: str = ""
    repo_full_name: str = ""
    workspace: str = ""
    cost_usd: float = 0.0
    iteration_count: int = 0
    hit_max_iterations: bool = False
