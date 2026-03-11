const markdownHeadingPrefix = /^\s{0,3}#{1,6}\s+/;
const priorityScenarioLabel = /\s*[（(]\s*优先场景\s*[:：]\s*[^)）]+[)）]\s*/g;

export function sanitizeDisplayText(value?: string | null) {
  if (!value) return '';

  return value
    .replace(markdownHeadingPrefix, '')
    .replace(priorityScenarioLabel, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
