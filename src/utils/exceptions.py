"""风险过滤系统自定义异常。"""


class RiskFilterError(Exception):
    """所有风险过滤异常的基类。"""


class ConfigurationError(RiskFilterError):
    """配置无效或缺失时抛出。"""


class RuleLoadError(RiskFilterError):
    """规则文件加载或解析失败时抛出。"""


class DetectionError(RiskFilterError):
    """检测流水线遇到错误时抛出。"""


class ModelNotAvailableError(RiskFilterError):
    """语义模型未加载或不可用时抛出。"""


class LLMServiceError(RiskFilterError):
    """大模型服务调用失败时抛出。"""


class AuditLogError(RiskFilterError):
    """审计日志写入失败时抛出。"""