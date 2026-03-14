import { useEffect, useState } from 'react';

import { ProfileForm } from '../components/ProfileForm';
import { getOnboardingFamily, isFamilyNotFoundError, upsertProfile } from '../lib/api';
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
  support: '支持卡',
  handoff: '交接卡'
};
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
          <p class="print-one-liner">${escapeHtml(card.one_liner)}</p>
          <p class="print-subtitle">先看这几条</p>
          <div class="print-chip-row">
            ${card.quick_actions.map((item) => `<span class="print-chip">${escapeHtml(item)}</span>`).join('')}
          </div>
          <div class="print-section-grid">
            ${card.sections
              .map(
                (section) => `
                  <section class="print-mini-card">
                    <h3>${escapeHtml(section.title)}</h3>
                    <ul>${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
                  </section>
                `
              )
              .join('')}
          </div>
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
          .print-one-liner { margin: 12px 0; padding: 12px 14px; border-radius: 14px; background: #eef7f2; color: #1d2b2c; }
          .print-subtitle { margin: 14px 0 8px; color: #58716d; font-size: 13px; }
          .print-chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
          .print-chip { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #f2f7f4; color: #355652; font-size: 13px; }
          .print-section-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
          .print-mini-card { border: 1px solid #dce8e2; border-radius: 14px; padding: 12px; background: #fbfdfc; }
          .print-mini-card h3 { margin: 0 0 8px; font-size: 16px; }
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

async function exportCardAsPng(familyName: string, _snapshot: OnboardingSnapshot, card: OnboardingSupportCard) {
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 1080;
  const ctx = canvas.getContext('2d');
  if (!ctx) return false;

  ctx.font = '400 28px "Noto Sans SC", sans-serif';
  const summaryLines = wrapText(ctx, card.summary, 980);
  ctx.font = '600 28px "Noto Sans SC", sans-serif';
  const oneLinerLines = wrapText(ctx, card.one_liner, 940);
  ctx.font = '400 24px "Noto Sans SC", sans-serif';
  const quickLines = wrapText(ctx, `先看这几条：${card.quick_actions.join(' / ')}`, 960);
  const sectionBlocks = card.sections.map((section) => ({
    title: section.title,
    itemLines: section.items.map((item) => wrapText(ctx, `• ${item}`, 420)),
  }));
  const sectionRows = Math.ceil(sectionBlocks.length / 2);
  const sectionHeight = sectionRows * 220;
  const contentHeight = 470 + summaryLines.length * 38 + oneLinerLines.length * 36 + quickLines.length * 30 + sectionHeight;
  canvas.height = Math.max(1080, contentHeight);

  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, '#edf8f3');
  gradient.addColorStop(1, '#d7efe6');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = '#bfd7ce';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(48, 48, 1104, canvas.height - 96, 28);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#236252';
  ctx.font = '600 24px "Noto Sans SC", sans-serif';
  ctx.fillText(cardIconLabel[card.icon], 88, 106);

  ctx.fillStyle = '#1b2d2d';
  ctx.font = '700 48px "Noto Sans SC", sans-serif';
  ctx.fillText(card.title, 88, 168);

  ctx.font = '400 28px "Noto Sans SC", sans-serif';
  summaryLines.forEach((line, index) => {
    ctx.fillText(line, 88, 228 + index * 38);
  });

  const oneLinerY = 228 + summaryLines.length * 38 + 54;
  ctx.fillStyle = '#eef7f2';
  ctx.beginPath();
  ctx.roundRect(88, oneLinerY - 26, 960, Math.max(82, oneLinerLines.length * 36 + 28), 18);
  ctx.fill();
  ctx.font = '600 28px "Noto Sans SC", sans-serif';
  ctx.fillStyle = '#1b2d2d';
  oneLinerLines.forEach((line, index) => {
    ctx.fillText(line, 112, oneLinerY + index * 36);
  });

  const quickTitleY = oneLinerY + Math.max(82, oneLinerLines.length * 36 + 28) + 38;
  ctx.fillStyle = '#1b2d2d';
  ctx.font = '600 26px "Noto Sans SC", sans-serif';
  ctx.fillText('先看这几条', 88, quickTitleY);
  ctx.font = '400 24px "Noto Sans SC", sans-serif';
  ctx.fillStyle = '#415757';
  quickLines.forEach((line, index) => {
    ctx.fillText(line, 88, quickTitleY + 40 + index * 30);
  });

  const sectionStartY = quickTitleY + 40 + quickLines.length * 30 + 44;
  const cardWidth = 470;
  sectionBlocks.forEach((section, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    const x = 88 + col * 500;
    const y = sectionStartY + row * 220;

    ctx.fillStyle = '#fbfdfc';
    ctx.strokeStyle = '#dce8e2';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(x, y, cardWidth, 188, 18);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#236252';
    ctx.font = '600 24px "Noto Sans SC", sans-serif';
    ctx.fillText(section.title, x + 20, y + 34);

    ctx.fillStyle = '#415757';
    ctx.font = '400 22px "Noto Sans SC", sans-serif';
    let lineY = y + 72;
    section.itemLines.forEach((lines) => {
      lines.forEach((line, lineIndex) => {
        ctx.fillText(line, x + 20, lineY + lineIndex * 28);
      });
      lineY += lines.length * 28 + 18;
    });
  });

  ctx.fillStyle = '#6c7e7b';
  ctx.font = '400 20px "Noto Sans SC", sans-serif';
  ctx.fillText(familyName, 88, canvas.height - 52);

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
  const [editForm, setEditForm] = useState<OnboardingSetupPayload>(buildProfileFormFromSummary(summary));

  useEffect(() => {
    setData(summary);
  }, [summary]);

  useEffect(() => {
    setEditForm(buildProfileFormFromSummary(summary ?? data));
  }, [data, summary]);

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
        if (isFamilyNotFoundError(err)) {
          setError('家庭档案不存在，正在返回首次设置页...');
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, onSummaryChange, summary, token]);

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
      if (isFamilyNotFoundError(err)) {
        setError('家庭档案不存在，正在返回首次设置页...');
        return;
      }
      setError((err as Error).message);
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <div className="content-page-shell family-page-shell">
      <div className="grid">
      {showCompletionCta ? (
        <div className="panel completion-banner">
          <div>
            <p className="eyebrow">设置完成</p>
            <h3>家庭档案已经生成</h3>
            <p className="muted">现在可以回到今天页开始签到，之后系统会按这份档案给出建议。</p>
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
          <p className="muted">先看今天最相关的提醒；需要改资料时，再展开下面的详细档案。</p>
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

      <div className="family-key-grid balanced-card-grid cols-3">
        <section className="panel detail-card">
          <p className="eyebrow">当前照护焦点</p>
          <h3>{data.snapshot.recommended_focus}</h3>
          <p className="muted">首页和高摩擦支援会优先参考这里。</p>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">高频触发器</p>
          <div className="chip-row">
            {data.snapshot.trigger_summary.map((item) => (
              <span key={item} className="info-chip warn">{item}</span>
            ))}
            {data.snapshot.sensory_summary.map((item) => (
              <span key={item} className="info-chip soft">{item}</span>
            ))}
          </div>
        </section>
        <section className="panel detail-card">
          <p className="eyebrow">有效安抚</p>
          <ul className="list">
            {data.snapshot.soothing_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
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
          <p className="eyebrow">不要做</p>
          <ul className="list">
            {data.profile.donts.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="grid family-card-grid balanced-card-grid cols-2">
        {data.support_cards.map((card) => {
          return (
            <article key={card.card_id} className="panel support-card">
              <div className="support-card-head">
                <div>
                  <p className="eyebrow">{cardIconLabel[card.icon]}</p>
                  <h3>{card.title}</h3>
                </div>
                <span className="support-badge">按档案生成</span>
              </div>
              <p>{card.summary}</p>
              <p className="support-card-one-liner">{card.one_liner}</p>
              <div className="support-card-quick">
                <span className="support-card-quick-label">先看这几条</span>
                {card.quick_actions.map((item) => (
                  <span key={item} className="info-chip ok">{item}</span>
                ))}
              </div>
              <div className="support-card-sections balanced-card-grid cols-2">
                {card.sections.map((section) => (
                  <section key={`${card.card_id}-${section.key}`} className="support-card-section">
                    <p className="support-card-section-title">{section.title}</p>
                    <ul className="support-card-section-list">
                      {section.items.map((item) => (
                        <li key={`${section.key}-${item}`}>{item}</li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
              <div className="support-actions">
                <button className="btn" type="button" onClick={() => exportCardAsPng(data.family.name, data.snapshot, card)}>
                  导出图片
                </button>
              </div>
            </article>
          );
        })}
      </section>

      <details className="panel family-details-panel">
        <summary className="family-details-summary">
          <div>
            <p className="eyebrow">完整档案</p>
            <strong>查看完整家庭画像与历史信息</strong>
            <p className="muted">展开后可查看孩子信息、兴趣偏好、健康情况、学习支持和家庭资源。</p>
          </div>
          <span className="family-details-summary-action">点此展开</span>
        </summary>

        <div className="family-summary-grid balanced-card-grid cols-3">
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

        <div className="family-summary-grid balanced-card-grid cols-3">
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
      </details>

        {error ? <div className="panel error">{error}</div> : null}
      </div>
    </div>
  );
}
