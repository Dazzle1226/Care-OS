import { useMemo, useState } from 'react';

import { mergeOptions } from '../lib/profileForm';

type SelectorOption = string | { value: string; hint?: string; label?: string };

interface Props {
  label: string;
  values: string[];
  options: SelectorOption[];
  onChange: (next: string[]) => void;
  helper?: string;
  customPlaceholder?: string;
  variant?: 'card' | 'pill';
}

function normalizeOption(option: SelectorOption) {
  if (typeof option === 'string') {
    return { value: option, label: option, hint: '' };
  }
  return {
    value: option.value,
    label: option.label ?? option.value,
    hint: option.hint ?? ''
  };
}

export function TagSelector({
  label,
  values,
  options,
  onChange,
  helper,
  customPlaceholder = '补充一个新选项',
  variant = 'card'
}: Props) {
  const [draft, setDraft] = useState('');
  const merged = useMemo(() => {
    const normalized = options.map(normalizeOption);
    const knownValues = normalized.map((item) => item.value);
    const customValues = mergeOptions([], values).filter((item) => !knownValues.includes(item));
    return [
      ...normalized,
      ...customValues.map((item) => ({
        value: item,
        label: item,
        hint: '来自你之前补充的自定义项'
      }))
    ];
  }, [options, values]);

  const toggle = (target: string) => {
    onChange(values.includes(target) ? values.filter((item) => item !== target) : [...values, target]);
  };

  const addCustom = () => {
    const value = draft.trim();
    if (!value) return;
    if (!values.includes(value)) {
      onChange([...values, value]);
    }
    setDraft('');
  };

  return (
    <div className="option-group">
      <span className="label">{label}</span>
      {helper ? <p className="muted option-helper">{helper}</p> : null}
      <div className={variant === 'card' ? 'option-grid' : 'pill-grid'}>
        {merged.map((option) =>
          variant === 'card' ? (
            <button
              key={option.value}
              type="button"
              className={`option-card ${values.includes(option.value) ? 'active' : ''}`}
              onClick={() => toggle(option.value)}
            >
              <strong>{option.label}</strong>
              {option.hint ? <span>{option.hint}</span> : null}
            </button>
          ) : (
            <button
              key={option.value}
              type="button"
              className={`pill-toggle ${values.includes(option.value) ? 'active' : ''}`}
              onClick={() => toggle(option.value)}
            >
              {option.label}
            </button>
          )
        )}
      </div>
      <div className="custom-entry">
        <input
          className="input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={customPlaceholder}
        />
        <button className="btn secondary" type="button" onClick={addCustom}>
          添加
        </button>
      </div>
    </div>
  );
}
