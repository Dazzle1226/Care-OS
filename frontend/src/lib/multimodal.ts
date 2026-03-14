import type { MultimodalIngestionResponse } from './types';

export const MULTIMODAL_AUTO_INCLUDE_CONFIDENCE = 0.65;

export function shouldAutoIncludeIngestion(
  ingestion: Pick<MultimodalIngestionResponse, 'confidence' | 'manual_review_required'>
): boolean {
  return !ingestion.manual_review_required && ingestion.confidence >= MULTIMODAL_AUTO_INCLUDE_CONFIDENCE;
}

export function getAutoIncludedIngestionIds(
  ingestions: Array<Pick<MultimodalIngestionResponse, 'ingestion_id' | 'confidence' | 'manual_review_required'>>
): number[] {
  return ingestions.filter(shouldAutoIncludeIngestion).map((item) => item.ingestion_id);
}
