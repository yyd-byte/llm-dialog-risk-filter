"""用户反馈端点。"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from src.api.bootstrap import AppComponents
from src.api.models import FeedbackRequest, FeedbackItem

router = APIRouter()


@router.post("/api/feedback", response_model=FeedbackItem)
def submit_feedback(req: FeedbackRequest):
    """提交误判反馈。

    反馈数据同时写入内存存储和 data/feedback/feedback.jsonl 文件。

    Args:
        req: 包含反馈类型、样本和建议的请求体。

    Returns:
        包含反馈 ID 和时间戳的 FeedbackItem。
    """
    components = AppComponents.get()
    feedback_id = str(uuid.uuid4())[:8]
    record = {
        "id": feedback_id,
        "timestamp": datetime.now().isoformat(),
        "type": req.type,
        "status": "pending",
        "sample": req.sample,
        "suggestion": req.suggestion,
        "requestId": req.requestId,
        "correctCategory": req.correctCategory,
    }
    components.feedback_store.append(record)

    # 持久化到反馈 JSONL 文件
    feedback_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "feedback"
    feedback_path.mkdir(parents=True, exist_ok=True)
    with open(feedback_path / "feedback.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return FeedbackItem(
        id=feedback_id,
        timestamp=record["timestamp"],
        type=record["type"],
        status="pending",
        sample=record["sample"],
        suggestion=record["suggestion"],
    )
