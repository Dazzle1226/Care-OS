from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models import ContextSignalFrame, MultimodalIngestion
from app.schemas.domain import ContextSignalRead, MultimodalIngestionRequest, MultimodalIngestionResponse
from app.schemas.domain import ContextFrameRead
from app.services.knowledge_corpus import KnowledgeCorpusService
from app.services.multimodal_file_parser import ExtractedMultimodalInput
from app.services.llm_client import LLMClient, LLMUnavailableError


DOCUMENT_SIGNAL_MAP = {
    "change": ("schedule_change", "日程变化"),
    "作业": ("task_load", "任务负荷"),
    "考试": ("time_pressure", "时间压力"),
    "通知": ("school_signal", "学校协同"),
    "家长": ("school_signal", "学校协同"),
    "提前": ("time_pressure", "时间压力"),
    "调整": ("schedule_change", "日程变化"),
}

AUDIO_SIGNAL_MAP = {
    "太吵": ("noise_level", "环境噪声"),
    "吵": ("noise_level", "环境噪声"),
    "快点": ("escalation_words", "升级关键词"),
    "不行": ("escalation_words", "升级关键词"),
    "我很累": ("caregiver_stress", "照护者压力"),
    "撑不住": ("caregiver_stress", "照护者压力"),
    "不知道": ("confidence_drift", "执行信心下降"),
    "怎么办": ("confidence_drift", "执行信心下降"),
}


class MultimodalIngestionService:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def ingest(self, db: Session, payload: MultimodalIngestionRequest) -> MultimodalIngestionResponse:
        return self.ingest_extracted(
            db=db,
            extracted=ExtractedMultimodalInput(
                family_id=payload.family_id,
                source_type=payload.source_type,
                content_name=payload.content_name.strip(),
                raw_text=payload.raw_text,
                confidence=0.9,
                manual_review_required=False,
                meta={"source": "manual_text"},
            ),
        )

    def ingest_extracted(self, db: Session, extracted: ExtractedMultimodalInput) -> MultimodalIngestionResponse:
        if extracted.source_type == "document":
            parsed = self._parse_document(extracted.raw_text)
        else:
            parsed = self._parse_audio(extracted.raw_text)

        final_confidence = round(min(parsed["confidence"], extracted.confidence), 2)
        manual_review_required = (
            bool(parsed["manual_review_required"])
            or bool(extracted.manual_review_required)
            or final_confidence < settings.multimodal_auto_include_confidence
        )

        row = MultimodalIngestion(
            family_id=extracted.family_id,
            source_type=extracted.source_type,
            content_name=extracted.content_name.strip(),
            raw_excerpt=extracted.raw_text[:500],
            normalized_summary=parsed["normalized_summary"],
            confidence=final_confidence,
            manual_review_required=manual_review_required,
            meta_json={"signals": parsed["signals"], **extracted.meta},
        )
        db.add(row)
        db.flush()

        signal_rows: list[ContextSignalRead] = []
        for item in parsed["signals"]:
            db.add(
                ContextSignalFrame(
                    ingestion_id=row.id,
                    signal_key=item["signal_key"],
                    signal_label=item["signal_label"],
                    signal_value=item["signal_value"],
                    confidence=item["confidence"],
                )
            )
            signal_rows.append(ContextSignalRead(**item))
        db.flush()

        return MultimodalIngestionResponse(
            ingestion_id=row.id,
            family_id=extracted.family_id,
            source_type=extracted.source_type,
            content_name=row.content_name,
            raw_excerpt=row.raw_excerpt,
            normalized_summary=row.normalized_summary,
            context_signals=signal_rows,
            confidence=row.confidence,
            manual_review_required=row.manual_review_required,
            created_at=row.created_at,
        )

    def get(self, db: Session, ingestion_id: int) -> MultimodalIngestionResponse | None:
        row = db.get(MultimodalIngestion, ingestion_id)
        if row is None:
            return None
        signals = [
            ContextSignalRead(
                signal_key=item.signal_key,
                signal_label=item.signal_label,
                signal_value=item.signal_value,
                confidence=item.confidence,
            )
            for item in row.signals
        ]
        return MultimodalIngestionResponse(
            ingestion_id=row.id,
            family_id=row.family_id,
            source_type=row.source_type,
            content_name=row.content_name,
            raw_excerpt=row.raw_excerpt,
            normalized_summary=row.normalized_summary,
            context_signals=signals,
            confidence=row.confidence,
            manual_review_required=row.manual_review_required,
            created_at=row.created_at,
        )

    def merge_context(self, db: Session, ingestion_ids: list[int]) -> tuple[str, list[int]]:
        frame = self.merge_context_frame(db, ingestion_ids)
        return frame.summary_text, frame.ingestion_ids

    def merge_context_frame(self, db: Session, ingestion_ids: list[int]) -> ContextFrameRead:
        frame = KnowledgeCorpusService().build_context_frame(db, ingestion_ids)
        return ContextFrameRead(
            summary_text=frame.summary_text,
            signal_keys=frame.signal_keys,
            signal_labels=frame.signal_labels,
            ingestion_ids=frame.ingestion_ids,
        )

    def _parse_document(self, text: str) -> dict[str, Any]:
        return self._parse_with_rules(text, DOCUMENT_SIGNAL_MAP, "document")

    def _parse_audio(self, text: str) -> dict[str, Any]:
        return self._parse_with_rules(text, AUDIO_SIGNAL_MAP, "audio")

    def _parse_with_rules(self, text: str, rule_map: dict[str, tuple[str, str]], source_type: str) -> dict[str, Any]:
        llm_parsed = self._attempt_llm_parse(text=text, source_type=source_type)
        if llm_parsed is not None:
            return llm_parsed

        signals: list[dict[str, Any]] = []
        lowered = text.strip()
        for marker, (signal_key, signal_label) in rule_map.items():
            if marker not in lowered:
                continue
            signals.append(
                {
                    "signal_key": signal_key,
                    "signal_label": signal_label,
                    "signal_value": marker,
                    "confidence": 0.72,
                }
            )
        if not signals:
            signals.append(
                {
                    "signal_key": f"{source_type}_summary",
                    "signal_label": "摘要线索",
                    "signal_value": lowered[:80] or "未识别出明确信号",
                    "confidence": 0.35,
                }
            )

        summary_prefix = "学校/日程输入显示" if source_type == "document" else "现场语音显示"
        normalized_summary = f"{summary_prefix}{'；'.join(item['signal_label'] for item in signals[:3])}。"
        confidence = min(0.9, 0.35 + len(signals) * 0.18)
        return {
            "normalized_summary": normalized_summary,
            "signals": signals[:6],
            "confidence": round(confidence, 2),
            "manual_review_required": confidence < 0.55,
        }

    def _attempt_llm_parse(self, text: str, source_type: str) -> dict[str, Any] | None:
        system_prompt = "你是多模态照护上下文解析器。只输出 JSON。"
        user_prompt = json.dumps(
            {
                "source_type": source_type,
                "text": text,
                "output_contract": {
                    "normalized_summary": "一句中文摘要",
                    "signals": [
                        {
                            "signal_key": "固定英文标识",
                            "signal_label": "中文标签",
                            "signal_value": "原始证据短句",
                            "confidence": 0.8,
                        }
                    ],
                    "confidence": 0.8,
                    "manual_review_required": False,
                },
            },
            ensure_ascii=False,
        )
        try:
            raw = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        except LLMUnavailableError:
            return None
        except Exception:
            return None

        try:
            signals = [
                ContextSignalRead.model_validate(item).model_dump()
                for item in list(raw.get("signals", []))[:6]
            ]
            if not signals:
                return None
            return {
                "normalized_summary": str(raw.get("normalized_summary") or "").strip() or "多模态输入已转成结构化摘要。",
                "signals": signals,
                "confidence": max(0.0, min(float(raw.get("confidence", 0.75)), 1.0)),
                "manual_review_required": bool(raw.get("manual_review_required", False)),
            }
        except Exception:
            return None
