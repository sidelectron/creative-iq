"""Enumerations for constrained string fields (API + domain)."""

from enum import Enum


class Platform(str, Enum):
    META = "meta"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"


class AdFormat(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"


class AdSource(str, Enum):
    UPLOAD = "upload"
    META_API = "meta_api"
    TIKTOK_API = "tiktok_api"


class AdStatus(str, Enum):
    INGESTED = "ingested"
    DECOMPOSING = "decomposing"
    DECOMPOSED = "decomposed"
    FAILED = "failed"


class BrandRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class EventType(str, Enum):
    PRODUCT_LAUNCH = "product_launch"
    POSITIONING_SHIFT = "positioning_shift"
    AGENCY_CHANGE = "agency_change"
    COMPETITOR_ACTION = "competitor_action"
    PERFORMANCE_ANOMALY = "performance_anomaly"
    STYLE_NOVELTY = "style_novelty"
    SINGLE_AD_OUTLIER = "single_ad_outlier"
    AB_TEST_LEARNING = "ab_test_learning"
    AB_TEST_PROPOSED = "ab_test_proposed"
    AB_TEST_ACTIVE = "ab_test_active"
    AB_TEST_COMPLETED = "ab_test_completed"
    PROFILE_COMPUTED = "profile_computed"
    USER_NOTE = "user_note"


class EventSource(str, Enum):
    AUTO_DETECTED = "auto_detected"
    USER_PROVIDED = "user_provided"


class ScoringStage(str, Enum):
    STATISTICAL = "statistical"
    ML = "ml"


class TestStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentType(str, Enum):
    ANALYSIS = "analysis"
    STRATEGY = "strategy"
    TEST_DESIGN = "test_design"
    MEMORY = "memory"
    GENERATION = "generation"


def brand_role_rank(role: BrandRole) -> int:
    """Return numeric rank for RBAC comparison (higher is more privileged)."""
    return {BrandRole.VIEWER: 1, BrandRole.EDITOR: 2, BrandRole.OWNER: 3}[role]
