"""Pydantic models for API request/response — mirrors frontend types."""

from pydantic import BaseModel, Field


# =============================================================================
# Enums (mirrors frontend types.ts)
# =============================================================================

RiskLevel = str  # "high" | "medium" | "low"
RiskCategory = str  # "sexual" | "violent" | "advertising" | "sensitive"
DetectionSource = str  # "rule" | "semantic"
RiskAction = str  # "block" | "desensitize" | "pass"


# =============================================================================
# Pipeline
# =============================================================================


class PipelineRequest(BaseModel):
    """Request body for POST /api/pipeline/check."""

    input: str = Field(..., min_length=1, description="用户输入文本")


class EvidenceItem(BaseModel):
    """A single piece of detection evidence."""

    source: DetectionSource
    category: RiskCategory
    confidence: float
    matchedPattern: str
    matchedText: str
    explanation: str
    step: str = ""  # normalize | rule | semantic | fusion | desensitize
    metadata: dict = {}  # structured extra data for rich visualization


class PipelineResult(BaseModel):
    """Response for POST /api/pipeline/check."""

    requestId: str
    timestamp: str
    originalInput: str
    normalizedInput: str
    riskLevel: RiskLevel
    riskCategory: RiskCategory | None = None
    confidence: float = 0.0
    action: RiskAction
    desensitizedInput: str = ""
    llmCalled: bool = False
    llmOutput: str = ""
    outputRiskLevel: RiskLevel = "low"
    outputBlocked: bool = False
    finalOutput: str = ""
    durationMs: float = 0.0
    evidenceChain: list[EvidenceItem] = []


# =============================================================================
# Statistics
# =============================================================================


class DailyStatItem(BaseModel):
    """Daily statistics point."""

    date: str
    blocked: int = 0
    desensitized: int = 0
    passed: int = 0
    outputBlocked: int = 0


class CategoryStatItem(BaseModel):
    """Per-category statistics."""

    category: RiskCategory
    label: str
    count: int
    color: str = "#64748b"


class StatsOverview(BaseModel):
    """Response for GET /api/stats/overview."""

    totalRequests: int = 0
    blockRate: float = 0.0
    falsePositiveRate: float = 0.0
    totalLlmCalls: int = 0
    outputBlockRate: float = 0.0
    dailyStats: list[DailyStatItem] = []
    categoryStats: list[CategoryStatItem] = []


# =============================================================================
# Rules
# =============================================================================


class RuleItem(BaseModel):
    """A single detection rule."""

    id: str
    pattern: str
    patternType: str
    category: RiskCategory
    riskLevel: RiskLevel
    enabled: bool
    description: str
    source: str = ""
    updatedAt: str = ""


class RulePage(BaseModel):
    """A paginated rule-list response."""

    items: list[RuleItem]
    page: int
    pageSize: int
    total: int
    version: str


class RuleSourceSummary(BaseModel):
    """Rule provenance summary."""

    source: str
    ruleCount: int
    enabledCount: int


class RuleMetadata(BaseModel):
    """Ruleset counts and current persisted version."""

    version: str
    total: int
    enabledTotal: int
    categories: list[dict]
    sources: list[RuleSourceSummary]


class SetRuleEnabledRequest(BaseModel):
    """Requested explicit enabled state guarded by a ruleset version."""

    enabled: bool
    expectedVersion: str


class RuleMutationResponse(BaseModel):
    """Response for a successful rule enable-state mutation."""

    item: RuleItem
    version: str


class ReloadRequest(BaseModel):
    """Optional current version supplied before explicit rule reload."""

    expectedVersion: str | None = None


# =============================================================================
# Feedback
# =============================================================================


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback."""

    type: str = Field(..., description="误判类型: false_positive | false_negative | wrong_category")
    requestId: str = ""
    sample: str = ""
    suggestion: str = ""
    correctCategory: str | None = None


class FeedbackItem(BaseModel):
    """Stored feedback record."""

    id: str
    timestamp: str
    type: str
    status: str = "pending"
    sample: str = ""
    suggestion: str = ""
