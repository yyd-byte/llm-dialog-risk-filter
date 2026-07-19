"""API 请求/响应数据模型（Pydantic）。

所有模型与前端 frontend/src/types.ts 中的类型定义保持同步。
"""

from pydantic import BaseModel, Field


# =============================================================================
# 枚举类型（与前端 types.ts 同步）
# =============================================================================

RiskLevel = str  # "high" | "medium" | "low"
RiskCategory = str  # "sexual" | "violent" | "advertising" | "sensitive"
DetectionSource = str  # "rule" | "semantic"
RiskAction = str  # "block" | "desensitize" | "pass"


# =============================================================================
# 流水线检测
# =============================================================================


class PipelineRequest(BaseModel):
    """请求体：POST /api/pipeline/check。"""

    input: str = Field(..., min_length=1, description="用户输入文本")


class EvidenceItem(BaseModel):
    """一条检测证据。"""

    source: DetectionSource
    category: RiskCategory
    confidence: float
    matchedPattern: str
    matchedText: str
    explanation: str
    step: str = ""  # normalize | rule | semantic | fusion | desensitize
    metadata: dict = {}  # structured extra data for rich visualization


class PipelineResult(BaseModel):
    """响应：POST /api/pipeline/check。

    包含从输入规范化到最终输出的全链路信息。
    """

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
# 统计
# =============================================================================


class DailyStatItem(BaseModel):
    """每日统计数据点。"""

    date: str
    blocked: int = 0
    desensitized: int = 0
    passed: int = 0
    outputBlocked: int = 0


class CategoryStatItem(BaseModel):
    """按风险类别的统计。"""

    category: RiskCategory
    label: str
    count: int
    color: str = "#64748b"


class StatsOverview(BaseModel):
    """响应：GET /api/stats/overview。"""

    totalRequests: int = 0
    blockRate: float = 0.0
    falsePositiveRate: float = 0.0
    totalLlmCalls: int = 0
    outputBlockRate: float = 0.0
    dailyStats: list[DailyStatItem] = []
    categoryStats: list[CategoryStatItem] = []


# =============================================================================
# 规则管理
# =============================================================================


class RuleItem(BaseModel):
    """一条检测规则。"""

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
    """分页规则列表响应。"""

    items: list[RuleItem]
    page: int
    pageSize: int
    total: int
    version: str


class RuleSourceSummary(BaseModel):
    """规则来源摘要。"""

    source: str
    ruleCount: int
    enabledCount: int


class RuleMetadata(BaseModel):
    """规则集统计及当前持久化版本号。"""

    version: str
    total: int
    enabledTotal: int
    categories: list[dict]
    sources: list[RuleSourceSummary]


class SetRuleEnabledRequest(BaseModel):
    """请求显式设置启用状态，并附带规则集版本校验。"""

    enabled: bool
    expectedVersion: str


class RuleMutationResponse(BaseModel):
    """操作成功的规则启用状态变更响应。"""

    item: RuleItem
    version: str


class ReloadRequest(BaseModel):
    """可选：重载前提交当前版本号以做冲突检测。"""

    expectedVersion: str | None = None


# =============================================================================
# 反馈
# =============================================================================


class FeedbackRequest(BaseModel):
    """请求体：POST /api/feedback。"""

    type: str = Field(..., description="误判类型: false_positive | false_negative | wrong_category")
    requestId: str = ""
    sample: str = ""
    suggestion: str = ""
    correctCategory: str | None = None


class FeedbackItem(BaseModel):
    """已存储的反馈记录。"""

    id: str
    timestamp: str
    type: str
    status: str = "pending"
    sample: str = ""
    suggestion: str = ""
