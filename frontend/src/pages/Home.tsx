import { useEffect, useRef, useState } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';

import { DailyFlowPage } from '../components/DailyFlowPage';
import { type ActionFlowContext, type CareTab } from '../lib/flow';
import { getHomeSurfaceRecommendation } from '../lib/homeSurface';
import type { OnboardingSummary } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  familySummary: OnboardingSummary | null;
  actionContext: ActionFlowContext | null;
  lowStim: boolean;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

export function HomePage({ token, familyId, familySummary, actionContext, lowStim, onNavigate, onActionContextChange }: Props) {
  const [showNowFlow, setShowNowFlow] = useState(false);
  const [openCheckinSignal, setOpenCheckinSignal] = useState(0);
  const flowRef = useRef<HTMLDivElement | null>(null);
  const hubRef = useRef<HTMLDivElement | null>(null);
  const galleryRef = useRef<HTMLElement | null>(null);
  const [focusedStage, setFocusedStage] = useState<'core' | 'left' | 'right'>('core');

  const { scrollYProgress: hubScroll } = useScroll({
    target: hubRef,
    offset: ['start start', 'end start']
  });
  const { scrollYProgress: galleryScroll } = useScroll({
    target: galleryRef,
    offset: ['start end', 'end start']
  });

  const heroParallaxY = useTransform(hubScroll, [0, 1], [0, lowStim ? -18 : -90]);
  const heroOpacity = useTransform(hubScroll, [0, 0.72], [1, lowStim ? 0.8 : 0.58]);
  const galleryParallaxY = useTransform(galleryScroll, [0, 1], [lowStim ? 18 : 56, lowStim ? -10 : -32]);
  const galleryGlow = useTransform(galleryScroll, [0, 0.55, 1], lowStim ? [0.06, 0.1, 0.04] : [0.18, 0.42, 0.12]);

  useEffect(() => {
    if (!showNowFlow || !flowRef.current) return;
    flowRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [showNowFlow]);

  const launchNowFlow = (captureState: boolean) => {
    setShowNowFlow(true);
    if (captureState) {
      setOpenCheckinSignal((current) => current + 1);
    }
  };

  const familyLabel = familySummary?.family.name ?? (familyId ? `家庭 #${familyId}` : '等待家庭建档');
  const stageLabel = actionContext ? '继续推进' : showNowFlow ? '正在进行' : '准备开始';
  const stageNote = actionContext
    ? '系统已保留上一次动作脉络'
    : showNowFlow
      ? 'AI 正在主卡里继续今天的路径'
      : '先用最短路径判断今天的起点';

  const riskLevel = actionContext ? '观察中' : showNowFlow ? '进行中' : '待判断';
  const riskTone = actionContext ? 'warn' : showNowFlow ? 'safe' : 'muted';
  const featuredSurface = getHomeSurfaceRecommendation({
    familyId,
    actionContext,
    isTodayFlowOpen: showNowFlow
  });

  const motionIn = {
    initial: { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const }
  };

  const floatingMotion = {
    animate: { y: [0, -10, 0], rotate: [-2, 0, -2] },
    transition: { duration: 8, repeat: Infinity, ease: 'easeInOut' as const }
  };

  const routeCards = [
    {
      id: 'core' as const,
      index: '01',
      eyebrow: 'Quick Access',
      title: '今日开始',
      description: '回到 AI 主卡，让系统决定现在显示签到、今日行动流还是下一步建议。',
      meta: showNowFlow ? '主卡正在推进' : '首页主路径',
      tone: 'sunrise'
    },
    {
      id: 'left' as const,
      index: '02',
      eyebrow: 'Quick Access',
      title: '高摩擦支持',
      description: '知道现场卡在哪里时，直接进入脚本和即时支援，不绕路。',
      meta: '适合已知场景',
      tone: 'petal'
    },
    {
      id: 'right' as const,
      index: '03',
      eyebrow: 'Quick Access',
      title: '训练指导',
      description: '查看今天训练重点、最近调整方向和系统保留的推进脉络。',
      meta: '适合计划推进',
      tone: 'mint'
    }
  ];

  const handleFeaturedAction = () => {
    if (featuredSurface.kind === 'setup') {
      onNavigate('family');
      return;
    }
    if (featuredSurface.kind === 'checkin' || featuredSurface.kind === 'todayFlow') {
      launchNowFlow(true);
      return;
    }
    onNavigate(featuredSurface.kind === 'training' ? 'plan' : 'review');
  };

  return (
    <div className={`care-hub ${lowStim ? 'care-hub-low-stim' : ''}`} ref={hubRef}>
      <motion.section
        className={`home-stage-hex mode-${focusedStage}`}
        {...motionIn}
        transition={{ ...motionIn.transition, delay: 0.08 }}
        style={{ y: heroParallaxY, opacity: heroOpacity }}
      >
        <div className="home-stage-nav">
          <div className="home-stage-brand">
            <span className="home-stage-brand-dot" aria-hidden="true" />
            <span>赫兹 Hertz</span>
          </div>
          <div className="home-stage-nav-links" aria-label="首页章节">
            <span>Today</span>
            <span>Support</span>
            <span>Plan</span>
          </div>
        </div>

        <div className="home-stage-hero">
          <div className="home-stage-backdrop" aria-hidden="true">
            <span className="home-stage-orb orb-one" />
            <span className="home-stage-orb orb-two" />
            <span className="home-stage-grid" />
            <span className="home-stage-particle particle-a" />
            <span className="home-stage-particle particle-b" />
            <span className="home-stage-particle particle-c" />
          </div>

          <div className="home-stage-copy">
            <div className="home-stage-topline">
              <span className="stage-paper-tag">Hertz Surface 2026</span>
            </div>

            <div className="home-stage-headline">
              <p className="eyebrow">赫兹 Hertz / Decision Surface</p>
              <h1>
                不用自己判断，
                <span>首页会直接带你进入现在最该处理的内容。</span>
              </h1>
              <p className="home-stage-intro">
                最大这张动态主卡不再只是展示，而是根据今天的状态与已有动作脉络，优先呈现今日签到、今日行动流、训练指导或复盘。
              </p>
            </div>

            <div className="home-stage-actions">
              <button type="button" className="btn home-stage-cta" onClick={handleFeaturedAction}>
                {featuredSurface.ctaLabel}
              </button>
              <button type="button" className="home-stage-secondary" onClick={() => onNavigate('family')}>
                查看家庭档案
              </button>
            </div>

            <div className="home-stage-meta-line" aria-label="首页关键信息">
              <span>{familyLabel}</span>
              <span>{stageLabel}</span>
              <span>{stageNote}</span>
            </div>
          </div>

          <div className="home-stage-visual" aria-label="首页 AI 主卡">
            <motion.div className="home-ai-surface" {...floatingMotion} ref={flowRef}>
              <div className="home-ai-surface-head">
                <div>
                  <p className="eyebrow">{featuredSurface.eyebrow}</p>
                  <h2>{featuredSurface.title}</h2>
                </div>
                <div className="home-ai-surface-meta">
                  <span className={`glass-status-pill tone-${riskTone}`}>{riskLevel}</span>
                  <span className="date-pill subtle">{showNowFlow ? '主卡进行中' : 'AI 当前推荐'}</span>
                </div>
              </div>

              <p className="home-ai-surface-summary">{featuredSurface.summary}</p>
              <p className="home-ai-surface-detail">{featuredSurface.detail}</p>
              <div className="home-ai-surface-body">
                {featuredSurface.kind === 'checkin' || featuredSurface.kind === 'todayFlow' ? (
                  <DailyFlowPage
                    token={token}
                    familyId={familyId}
                    onNavigate={onNavigate}
                    onActionContextChange={onActionContextChange}
                    openCheckinSignal={openCheckinSignal}
                    variant="embedded"
                  />
                ) : (
                  <div className="home-ai-surface-fallback">
                    <div className="glass-panel-metric">
                      <span>{featuredSurface.kind === 'training' ? 'Training Continuity' : 'Review Readiness'}</span>
                      <div className="glass-panel-bar">
                        <span className={actionContext ? 'is-continuing' : ''} />
                      </div>
                    </div>
                    <p>{featuredSurface.summary}</p>
                    <button type="button" className="btn home-stage-cta" onClick={handleFeaturedAction}>
                      {featuredSurface.ctaLabel}
                    </button>
                  </div>
                )}
              </div>
            </motion.div>

            <div className="home-stage-radar" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        ref={galleryRef}
        className="home-gallery-stage"
        {...motionIn}
        transition={{ ...motionIn.transition, delay: 0.15 }}
        style={{ y: galleryParallaxY, ['--gallery-glow' as string]: galleryGlow }}
      >
        <div className="home-gallery-heading">
          <p className="eyebrow">Quick Access</p>
          <h2>三个快速进入的关键功能</h2>
        </div>

        <div className="home-route-grid">
          {routeCards.map((card) => (
            <section
              key={card.id}
              className={`home-route-card tone-${card.tone} ${focusedStage === card.id ? 'is-active' : ''}`}
              onMouseEnter={() => setFocusedStage(card.id)}
              style={{ ['--card-delay' as string]: Number(card.index) * 0.06 }}
            >
              <div className="home-route-card-top">
                <span className="route-card-index">{card.index}</span>
                <span className="route-card-line" aria-hidden="true" />
              </div>
              <p className="eyebrow">{card.eyebrow}</p>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <div className="home-route-card-meta">
                <span>{card.meta}</span>
                {card.id === 'core' ? (
                  <button type="button" className="home-route-link" onClick={() => launchNowFlow(true)}>
                    打开 AI 主卡
                  </button>
                ) : card.id === 'left' ? (
                  <button type="button" className="home-route-link" onClick={() => onNavigate('scripts')}>
                    打开高摩擦支持
                  </button>
                ) : (
                  <button type="button" className="home-route-link" onClick={() => onNavigate('plan')}>
                    打开训练指导
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      </motion.section>
    </div>
  );
}
