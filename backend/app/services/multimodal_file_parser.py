from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None

from app.core.config import settings
from app.services.llm_client import LLMClient, LLMUnavailableError


class MultimodalExtractionError(RuntimeError):
    pass


@dataclass(slots=True)
class ExtractedMultimodalInput:
    family_id: int
    source_type: str
    content_name: str
    raw_text: str
    confidence: float
    manual_review_required: bool
    meta: dict[str, object]


class MultimodalFileParser:
    document_mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".pdf": "application/pdf",
    }
    audio_mime_types = {
        ".m4a": "audio/m4a",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
    }
    max_document_bytes = 8 * 1024 * 1024
    max_audio_bytes = 15 * 1024 * 1024

    def __init__(self) -> None:
        self.llm = LLMClient(timeout_seconds=45)

    def extract_document(
        self,
        *,
        family_id: int,
        filename: str,
        content_type: str | None,
        payload: bytes,
        content_name: str = "",
    ) -> ExtractedMultimodalInput:
        suffix = Path(filename).suffix.lower()
        mime = self._resolve_mime_type(suffix=suffix, content_type=content_type, mapping=self.document_mime_types)
        self._ensure_payload_size(payload=payload, max_bytes=self.max_document_bytes, label="文档")

        if mime == "application/pdf":
            text = self._extract_pdf_text(payload)
            if text:
                return self._build_result(
                    family_id=family_id,
                    source_type="document",
                    content_name=content_name or filename or "上传文档",
                    raw_text=text[:4000],
                    confidence=0.92 if len(text) >= 120 else 0.6,
                    manual_review_required=len(text) < 120,
                    meta={"source": "pdf_text", "filename": filename, "mime_type": mime},
                )

        return self._extract_document_via_model(
            family_id=family_id,
            filename=filename,
            mime=mime,
            payload=payload,
            content_name=content_name or filename or "上传文档",
        )

    def extract_audio(
        self,
        *,
        family_id: int,
        filename: str,
        content_type: str | None,
        payload: bytes,
        content_name: str = "",
    ) -> ExtractedMultimodalInput:
        suffix = Path(filename).suffix.lower()
        mime = self._resolve_mime_type(suffix=suffix, content_type=content_type, mapping=self.audio_mime_types)
        self._ensure_payload_size(payload=payload, max_bytes=self.max_audio_bytes, label="音频")
        data_url = self._to_data_url(payload=payload, mime=mime)

        try:
            raw = self.llm.generate_multimodal_json(
                model=settings.openai_audio_model,
                system_prompt=(
                    "你是 ASD 家庭照护场景里的语音转写与上下文提取器。"
                    "只输出 JSON。"
                    "不要编造听不清的内容。"
                ),
                user_content=[
                    {
                        "type": "text",
                        "text": (
                            "请把音频转成适合照护决策的短文本。"
                            "输出格式必须是 JSON："
                            '{"raw_text":"尽量保留原始说法","confidence":0.8,"manual_review_required":false}'
                        ),
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": data_url.split(",", 1)[1],
                            "format": suffix.lstrip(".") or "wav",
                        },
                    },
                ],
                stream=True,
            )
        except LLMUnavailableError as exc:
            raise MultimodalExtractionError("音频解析失败，请改用手动粘贴语音摘要。") from exc

        return self._normalize_model_result(
            raw=raw,
            family_id=family_id,
            source_type="audio",
            content_name=content_name or filename or "上传语音",
            meta={"source": "audio_model", "filename": filename, "mime_type": mime, "model": settings.openai_audio_model},
        )

    def _extract_document_via_model(
        self,
        *,
        family_id: int,
        filename: str,
        mime: str,
        payload: bytes,
        content_name: str,
    ) -> ExtractedMultimodalInput:
        data_url = self._to_data_url(payload=payload, mime=mime)
        try:
            raw = self.llm.generate_multimodal_json(
                model=settings.openai_vision_model,
                system_prompt=(
                    "你是 ASD 家庭照护场景里的文档/OCR 解析器。"
                    "只输出 JSON。"
                    "优先保留通知、作业、日程、时间变化、要求变化等原文。"
                ),
                user_content=[
                    {
                        "type": "text",
                        "text": (
                            "请从图片或文档中提取可供后续照护决策使用的原始文本。"
                            "输出 JSON："
                            '{"raw_text":"原始关键信息","confidence":0.8,"manual_review_required":false}'
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
                stream=False,
            )
        except LLMUnavailableError as exc:
            if mime.startswith("image/"):
                return self._build_result(
                    family_id=family_id,
                    source_type="document",
                    content_name=content_name,
                    raw_text=(
                        f"已上传图片文档《{content_name}》，但当前环境未能自动提取图片文字。"
                        "请结合原图手动确认关键信息。"
                    ),
                    confidence=0.2,
                    manual_review_required=True,
                    meta={
                        "source": "vision_model_fallback",
                        "filename": filename,
                        "mime_type": mime,
                        "model": settings.openai_vision_model,
                        "parse_error": str(exc),
                    },
                )
            raise MultimodalExtractionError("文档解析失败，请改用手动粘贴通知摘要。") from exc

        return self._normalize_model_result(
            raw=raw,
            family_id=family_id,
            source_type="document",
            content_name=content_name,
            meta={"source": "vision_model", "filename": filename, "mime_type": mime, "model": settings.openai_vision_model},
        )

    @staticmethod
    def _extract_pdf_text(payload: bytes) -> str:
        if PdfReader is None:
            return ""
        try:
            reader = PdfReader(io.BytesIO(payload))
        except Exception:
            return ""
        chunks: list[str] = []
        for page in reader.pages[:6]:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                chunks.append(text.strip())
        return "\n".join(chunks).strip()

    @staticmethod
    def _ensure_payload_size(*, payload: bytes, max_bytes: int, label: str) -> None:
        if not payload:
            raise MultimodalExtractionError(f"{label}内容为空，请重新上传。")
        if len(payload) > max_bytes:
            raise MultimodalExtractionError(f"{label}文件过大，请压缩后重试。")

    @staticmethod
    def _resolve_mime_type(*, suffix: str, content_type: str | None, mapping: dict[str, str]) -> str:
        if suffix in mapping:
            return mapping[suffix]
        if content_type and content_type in mapping.values():
            return content_type
        raise MultimodalExtractionError("文件格式暂不支持，请改用图片、PDF 或常见音频格式。")

    @staticmethod
    def _to_data_url(*, payload: bytes, mime: str) -> str:
        return f"data:{mime};base64,{base64.b64encode(payload).decode('utf-8')}"

    def _normalize_model_result(
        self,
        *,
        raw: dict,
        family_id: int,
        source_type: str,
        content_name: str,
        meta: dict[str, object],
    ) -> ExtractedMultimodalInput:
        raw_text = str(raw.get("raw_text") or raw.get("transcript") or raw.get("text") or "").strip()
        if not raw_text:
            raise MultimodalExtractionError("未能从文件中提取可用文本，请改用手动粘贴摘要。")
        try:
            confidence = max(0.0, min(float(raw.get("confidence", 0.6)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.6
        manual_review_required = bool(raw.get("manual_review_required", confidence < settings.multimodal_auto_include_confidence))
        if confidence < settings.multimodal_auto_include_confidence:
            manual_review_required = True
        return self._build_result(
            family_id=family_id,
            source_type=source_type,
            content_name=content_name,
            raw_text=raw_text[:4000],
            confidence=confidence,
            manual_review_required=manual_review_required,
            meta=meta,
        )

    @staticmethod
    def _build_result(
        *,
        family_id: int,
        source_type: str,
        content_name: str,
        raw_text: str,
        confidence: float,
        manual_review_required: bool,
        meta: dict[str, object],
    ) -> ExtractedMultimodalInput:
        return ExtractedMultimodalInput(
            family_id=family_id,
            source_type=source_type,
            content_name=content_name.strip() or ("上传文档" if source_type == "document" else "上传语音"),
            raw_text=raw_text,
            confidence=confidence,
            manual_review_required=manual_review_required,
            meta=meta,
        )
