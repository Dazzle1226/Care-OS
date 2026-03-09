import { useEffect, useState } from 'react';

import { ProfileForm } from '../components/ProfileForm';
import { getOnboardingFamily, upsertProfile } from '../lib/api';
import { buildProfileFormFromSummary } from '../lib/profileForm';
import type { OnboardingSetupPayload, OnboardingSnapshot, OnboardingSummary, OnboardingSupportCard } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  summary: OnboardingSummary | null;
  onSummaryChange: (summary: OnboardingSummary) => void;
  showCompletionCta: boolean;
  onFinishSetup: () => void;
}

const cardIconLabel: Record<OnboardingSupportCard['icon'], string> = {
  child: '孩子支持',
  parent: '家长支持',
  team: '家庭协作'
};

function savedCardKey(familyId: number) {
  return `care_os_saved_support_cards_${familyId}`;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function openPrintableWindow(title: string, snapshot: OnboardingSnapshot, cards: OnboardingSupportCard[]) {
  const popup = window.open('', '_blank', 'noopener,noreferrer,width=960,height=900');
  if (!popup) return false;

  const snapshotItems = [
    ...snapshot.child_overview.map((item) => `<li>${escapeHtml(item)}</li>`),
    ...snapshot.resource_summary.map((item) => `<li>${escapeHtml(item)}</li>`)
  ].join('');
  const cardSections = cards
    .map(
      (card) => `
        <section class="print-card">
          <p class="print-label">${escapeHtml(cardIconLabel[card.icon])}</p>
          <h2>${escapeHtml(card.title)}</h2>
          <p>${escapeHtml(card.summary)}</p>
          <ul>${card.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </section>
      `
    )
    .join('');

  popup.document.write(`
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>${escapeHtml(title)}</title>
        <style>
          body { font-family: "Noto Sans SC", sans-serif; margin: 0; color: #1d2b2c; background: #f6fbf8; }
          main { max-width: 860px; margin: 0 auto; padding: 28px 24px 40px; }
          h1, h2 { margin: 0 0 12px; }
          p, li { line-height: 1.7; }
          .print-cover { border: 1px solid #c9ddd6; border-radius: 18px; padding: 24px; background: #ffffff; margin-bottom: 16px; }
          .print-card { border: 1px solid #c9ddd6; border-radius: 18px; padding: 20px; background: #ffffff; margin-bottom: 14px; }
          .print-label { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #dceee6; color: #246152; font-size: 12px; margin-bottom: 10px; }
          ul { margin: 0; padding-left: 18px; }
        </style>
      </head>
      <body>
        <main>
          <section class="print-cover">
            <p class="print-label">家庭画像</p>
            <h1>${escapeHtml(title)}</h1>
            <p>${escapeHtml(snapshot.recommended_focus)}</p>
            <ul>${snapshotItems}</ul>
          </section>
          ${cardSections}
        </main>
      </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
  popup.setTimeout(() => popup.print(), 200);
  return true;
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const words = text.split('');
  const lines: string[] = [];
  let current = '';

  words.forEach((word) => {
    const next = current + word;
    if (ctx.measureText(next).width > maxWidth && current) {
      lines.push(current);
      current = word;
      return;
    }
    current = next;
  });

  if (current) lines.push(current);
  return lines;
}

async function exportCardAsPng(familyName: string, snapshot: OnboardingSnapshot, card: OnboardingSupportCard) {
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 820;
  const ctx = canvas.getContext('2d');
  if (!ctx) return false;

  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, '#edf8f3');
  gradient.addColorStop(1, '#d7efe6');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = '#bfd7ce';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(48, 48, 1104, 724, 28);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#236252';
  ctx.font = '600 24px "Noto Sans SC", sans-serif';
  ctx.fillText(cardIconLabel[card.icon], 88, 106);

  ctx.fillStyle = '#1b2d2d';
  ctx.font = '700 48px "Noto Sans SC", sans-serif';
  ctx.fillText(card.title, 88, 168);

  ctx.font = '400 28px "Noto Sans SC", sans-serif';
  wrapText(ctx, card.summary, 980).forEach((line, index) => {
    ctx.fillText(line, 88, 228 + index * 38);
  });

  ctx.font = '600 26px "Noto Sans SC", sans-serif';
  ctx.fillStyle = '#236252';
  ctx.fillText('推荐焦点', 88, 336);
  ctx.font = '400 24px "Noto Sans SC", sans-serif';
  ctx.fillStyle = '#415757';
  wrapText(ctx, snapshot.recommended_focus, 980).forEach((line, index) => {
    ctx.fillText(line, 88, 376 + index * 34);
  });

  ctx.fillStyle = '#1b2d2d';
  ctx.font = '600 26px "Noto Sans SC", sans-serif';
  ctx.fillText('行动要点', 88, 474);
  ctx.font = '400 24px "Noto Sans SC", sans-serif';
  card.bullets.forEach((bullet, index) => {
    wrapText(ctx, `• ${bullet}`, 960).forEach((line, lineIndex) => {
      ctx.fillText(line, 88, 516 + index * 72 + lineIndex * 30);
    });
  });

  ctx.fillStyle = '#6c7e7b';
  ctx.font = '400 20px "Noto Sans SC", sans-serif';
  ctx.fillText(familyName, 88, 734);

  const dataUrl = canvas.toDataURL('image/png');
  const anchor = document.createElement('a');
  anchor.href = dataUrl;
  anchor.download = `${familyName}-${card.title}.png`;
  anchor.click();
  return true;
}

export function FamilyPage({
  token,
  familyId,
  summary,
  onSummaryChange,
  showCompletionCta,
  onFinishSetup
}: Props) {
  const [data, setData] = useState<OnboardingSummary | null>(summary);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [savedCards, setSavedCards] = useState<string[]>([]);
  const [editForm, setEditForm] = useState<OnboardingSetupPayload>(buildProfileFormFromSummary(summary));

  useEffect(() => {
    setData(summary);
  }, [summary]);

  useEffect(() => {
    setEditForm(buildProfileFormFromSummary(summary ?? data));
  }, [data, summary]);

  useEffect(() => {
    if (!familyId) {
      setSavedCards([]);
      return;
    }
    const raw = localStorage.getItem(savedCardKey(familyId));
    setSavedCards(raw ? JSON.parse(raw) : []);
  }, [familyId]);

  useEffect(() => {
    let cancelled = false;

    if (!familyId) {
      setData(null);
      return () => {
        cancelled = true;
      };
    }

    if (summary?.family.family_id === familyId) {
      setData(summary);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setError('');
    getOnboardingFamily(token, familyId)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        onSummaryChange(response);
      })
      .catch((err) => {
        if (cancelled) return;
        setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, onSummaryChange, summary, token]);

  const toggleSaveCard = (cardId: string) => {
    if (!familyId) return;
    const next = savedCards.includes(cardId)
      ? savedCards.filter((item) => item !== cardId)
      : [...savedCards, cardId];
    setSavedCards(next);
    localStorage.setItem(savedCardKey(familyId), JSON.stringify(next));
  };

  if (!familyId) {
    return (
      <div className="panel">
        <h3>还没有家庭档案</h3>
        <p className="muted">请先完成初次设置，系统才能生成家庭画像和支持卡。</p>
      </div>
    );
  }

  if (loading && !data) {
    return <div className="panel">正在读取家庭画像...</div>;
  }

  if (!data) {
    return error ? <div className="panel error">{error}</div> : null;
  }

  const exportFamilyPdf = () => {
    openPrintableWindow(`${data.family.name} · 家庭画像`, data.snapshot, data.support_cards);
  };

  const exportCardPdf = (card: OnboardingSupportCard) => {
    openPrintableWindow(`${data.family.name} · ${card.title}`, data.snapshot, [card]);
  };

  const saveProfile = async () => {
    if (!familyId) return;
    setSavingProfile(true);
    setError('');
    try {
      await upsertProfile(token, { family_id: familyId, ...editForm });
      const refreshed = await getOnboardingFamily(token, familyId);
      setData(refreshed);
      setEditForm(buildProfileFormFromSummary(refreshed));
      onSummaryChange(refreshed);
      setEditing(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <div className="grid">
      {showCompletionCta ? (
        <div className="panel completion-banner">
          <div>
            <p className="eyebrow">设置完成</p>
            <h3>家庭档案已经生成</h3>
            <p className="muted">你现在可以继续进入主界面，系统也已经准备好今日支持与高摩擦场景支援。</p>
          </div>
          <button className="btn" type="button" onClick={onFinishSetup}>
            完成设置，进入今天
          </button>
        </div>
      ) : null}

      <section className="panel family-hero">
        <div>
          <p className="eyebrow">家庭画像</p>
          <h2>{data.family.name}</h2>
          <p>{data.snapshot.recommended_focus}</p>
        </div>
        <div className="hero-side">
          <span className="date-pill">family_id #{data.family.family_id}</span>
          <button className="btn secondary" type="button" onClick={() => setEditing((current) => !current)}>
            {editing ? '收起档案编辑' : '编辑详细档案'}
          </button>
          <button className="btn secondary" type="button" onClick={exportFamilyPdf}>
            导出家庭档案 PDF
          </button>
        </div>
      </section>

      {editing ? (
        <section className="panel onboarding-shell">
          <div className="onboarding-section">
            <div>
              <p className="eyebrow">档案更新</p>
              <h3>根据孩子的变化持续修正资料</h3>
              <p className="muted">你补充过的新项会和当前档案一起保留下来，方便下次继续修改。</p>
            </div>
          </div>
          <ProfileForm form={editForm} onChange={(patch) => setEditForm((current) => ({ ...current, ...patch }))} />
          <div className="onboarding-footer">
            <div className="footer-actions">
              <button className="btn secondary" type="button" onClick={() => setEditing(false)}>
                取消
              </button>
              <button className="btn" type="button" onClick={saveProfile} disabled={savingProfile}>
                {savingProfile ? '保存中...' : '保存档案更新'}
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <div className="family-summary-grid">
        <section className="panel detail-card">
          <p className="eyebrow">孩子信息</p>
          <ul className="list">
            {data.snapshot.child_overview.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">兴趣与偏好</p>
          <ul className="list">
            {data.snapshot.preference_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">健康情况</p>
          <ul className="list">
            {data.snapshot.health_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">触发器与感官敏感</p>
          <div className="chip-row">
            {data.snapshot.trigger_summary.map((item) => (
              <span key={item} className="info-chip">{item}</span>
            ))}
            {data.snapshot.sensory_summary.map((item) => (
              <span key={item} className="info-chip soft">{item}</span>
            ))}
          </div>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">当前可用资源</p>
          <ul className="list">
            {data.snapshot.resource_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <div className="family-summary-grid">
        <section className="panel detail-card">
          <p className="eyebrow">安抚方式</p>
          <ul className="list">
            {data.snapshot.soothing_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">行为与情绪</p>
          <ul className="list">
            {data.snapshot.behavior_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">学习支持</p>
          <ul className="list">
            {data.snapshot.learning_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">家长压力源</p>
          <div className="chip-row">
            {data.snapshot.caregiver_pressure.map((item) => (
              <span key={item} className="info-chip warn">{item}</span>
            ))}
          </div>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">可用支持者</p>
          <div className="chip-row">
            {data.snapshot.supporter_summary.map((item) => (
              <span key={item} className="info-chip ok">{item}</span>
            ))}
          </div>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">教育与社交</p>
          <ul className="list">
            {data.snapshot.social_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">家长支持情况</p>
          <ul className="list">
            {data.snapshot.parent_support_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="grid family-card-grid">
        {data.support_cards.map((card) => {
          const saved = savedCards.includes(card.card_id);
          return (
            <article key={card.card_id} className="panel support-card">
              <div className="support-card-head">
                <div>
                  <p className="eyebrow">{cardIconLabel[card.icon]}</p>
                  <h3>{card.title}</h3>
                </div>
                <span className="support-badge">{saved ? '已保存' : '建议查看'}</span>
              </div>
              <p>{card.summary}</p>
              <ul className="list">
                {card.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="support-actions">
                <button className="btn secondary" type="button" onClick={() => toggleSaveCard(card.card_id)}>
                  {saved ? '取消保存' : '保存'}
                </button>
                <button
                  className="btn secondary"
                  type="button"
                  onClick={() => exportCardPdf(card)}
                >
                  导出 PDF
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={() => exportCardAsPng(data.family.name, data.snapshot, card)}
                >
                  导出图片
                </button>
              </div>
            </article>
          );
        })}
      </section>

      {error ? <div className="panel error">{error}</div> : null}
    </div>
  );
}
