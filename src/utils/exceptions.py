"""Custom exceptions for the risk filtering system."""


class RiskFilterError(Exception):
    """Base exception for all risk filter errors."""


class ConfigurationError(RiskFilterError):
    """Raised when configuration is invalid or missing."""


class RuleLoadError(RiskFilterError):
    """Raised when rule files cannot be loaded or parsed."""


class DetectionError(RiskFilterError):
    """Raised when detection pipeline encounters an error."""


class ModelNotAvailableError(RiskFilterError):
    """Raised when semantic model is not loaded or available."""


class LLMServiceError(RiskFilterError):
    """Raised when LLM service call fails."""


class AuditLogError(RiskFilterError):
    """Raised when audit logging fails."""