import { TagSelector } from './TagSelector';
import {
  allergyOptions,
  behaviorPatternOptions,
  behaviorRiskOptions,
  coexistingConditionOptions,
  familyMemberOptions,
  familyNamePreview,
  foodPreferenceOptions,
  frictionScenarioOptions,
  interestOptions,
  learningNeedOptions,
  likeOptions,
  dislikeOptions,
  medicalNeedOptions,
  emotionPatternOptions,
  parentEmotionalSupportOptions,
  parentScheduleOptions,
  parentStressorOptions,
  parentSupportActionOptions,
  schoolTypeOptions,
  sensoryOptions,
  sleepChallengeOptions,
  socialTrainingOptions,
  soothingOptions,
  supporterOptions,
  triggerOptions
} from '../lib/profileForm';
import type { OnboardingSetupPayload } from '../lib/types';

interface Props {
  form: OnboardingSetupPayload;
  onChange: (patch: Partial<OnboardingSetupPayload>) => void;
}

export function ProfileForm({ form, onChange }: Props) {
  const update = <K extends keyof OnboardingSetupPayload>(key: K, value: OnboardingSetupPayload[K]) => {
    onChange({ [key]: value });
  };

  return (
    <div className="profile-form-stack">
      <section className="onboarding-section">
        <div>
          <p className="eyebrow">基础信息</p>
          <h3>先建立孩子和家庭的基础画像</h3>
          <p className="muted">尽量用选择完成，只有补充说明才需要输入文字。</p>
        </div>
        <div className="grid two">
          <label>
            <span className="label">孩子姓名</span>
            <input
              className="input"
              value={form.child_name ?? ''}
              onChange={(e) => update('child_name', e.target.value)}
              placeholder="例如：小雨"
            />
          </label>
          <label>
            <span className="label">家庭名称</span>
            <input
              className="input"
              value={form.family_name ?? familyNamePreview(form.child_name)}
              onChange={(e) => update('family_name', e.target.value)}
              placeholder={familyNamePreview(form.child_name)}
            />
          </label>
          <label className="range-field">
            <div className="field-head">
              <span>孩子年龄</span>
              <strong>{form.child_age ?? 6} 岁</strong>
            </div>
            <input
              type="range"
              min="0"
              max="12"
              step="1"
              value={form.child_age ?? 6}
              onChange={(e) => update('child_age', Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">孩子性别</span>
            <select
              className="input"
              value={form.child_gender ?? ''}
              onChange={(e) => update('child_gender', (e.target.value || undefined) as OnboardingSetupPayload['child_gender'])}
            >
              <option value="">暂不填写</option>
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            <span className="label">主要照护者</span>
            <select
              className="input"
              value={form.primary_caregiver ?? ''}
              onChange={(e) =>
                update('primary_caregiver', (e.target.value || undefined) as OnboardingSetupPayload['primary_caregiver'])
              }
            >
              <option value="">暂不填写</option>
              <option value="parents">父母</option>
              <option value="grandparents">祖父母</option>
              <option value="relative">亲戚</option>
              <option value="other">其他照护者</option>
            </select>
          </label>
          <label>
            <span className="label">沟通能力</span>
            <select
              className="input"
              value={form.communication_level ?? 'short_sentence'}
              onChange={(e) =>
                update('communication_level', e.target.value as OnboardingSetupPayload['communication_level'])
              }
            >
              <option value="none">无语言</option>
              <option value="single_word">少量词汇</option>
              <option value="short_sentence">短句流利</option>
              <option value="fluent">流利语言</option>
            </select>
          </label>
          <label>
            <span className="label">诊断情况</span>
            <select
              className="input"
              value={form.diagnosis_status ?? ''}
              onChange={(e) =>
                update('diagnosis_status', (e.target.value || undefined) as OnboardingSetupPayload['diagnosis_status'])
              }
            >
              <option value="">暂不填写</option>
              <option value="asd">自闭症谱系障碍（ASD）</option>
              <option value="none">没有诊断</option>
              <option value="under_assessment">评估中</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label className="full-span">
            <span className="label">诊断补充说明</span>
            <textarea
              className="input"
              rows={3}
              value={form.diagnosis_notes ?? ''}
              onChange={(e) => update('diagnosis_notes', e.target.value)}
              placeholder="例如：ASD 伴焦虑；评估报告里重点提示睡眠和过渡困难。"
            />
          </label>
        </div>

        <TagSelector
          label="共病 / 伴随问题"
          values={form.coexisting_conditions ?? []}
          options={coexistingConditionOptions}
          onChange={(next) => update('coexisting_conditions', next)}
          customPlaceholder="补充共病或伴随问题"
          variant="pill"
        />
        <TagSelector
          label="家庭成员"
          values={form.family_members ?? []}
          options={familyMemberOptions}
          onChange={(next) => update('family_members', next)}
          customPlaceholder="补充家庭成员称呼"
          variant="pill"
        />
        <div className="grid two">
          <TagSelector
            label="兴趣爱好"
            values={form.interests ?? []}
            options={interestOptions}
            onChange={(next) => update('interests', next)}
            customPlaceholder="补充兴趣爱好"
            variant="pill"
          />
          <TagSelector
            label="喜欢的事物"
            values={form.likes ?? []}
            options={likeOptions}
            onChange={(next) => update('likes', next)}
            customPlaceholder="补充喜欢的事物"
            variant="pill"
          />
        </div>
        <TagSelector
          label="不喜欢 / 尽量避免"
          values={form.dislikes ?? []}
          options={dislikeOptions}
          onChange={(next) => update('dislikes', next)}
          customPlaceholder="补充不喜欢的事物"
          variant="pill"
        />
      </section>

      <section className="onboarding-section">
        <div>
          <p className="eyebrow">健康状况</p>
          <h3>记录睡眠、饮食、过敏和医疗信息</h3>
        </div>
        <div className="grid two">
          <TagSelector
            label="睡眠问题"
            values={form.sleep_challenges ?? []}
            options={sleepChallengeOptions}
            onChange={(next) => update('sleep_challenges', next)}
            customPlaceholder="补充睡眠问题"
          />
          <TagSelector
            label="饮食偏好"
            values={form.food_preferences ?? []}
            options={foodPreferenceOptions}
            onChange={(next) => update('food_preferences', next)}
            customPlaceholder="补充饮食偏好"
          />
          <TagSelector
            label="过敏情况"
            values={form.allergies ?? []}
            options={allergyOptions}
            onChange={(next) => update('allergies', next)}
            customPlaceholder="补充过敏信息"
            variant="pill"
          />
          <TagSelector
            label="特殊医疗需求"
            values={form.medical_needs ?? []}
            options={medicalNeedOptions}
            onChange={(next) => update('medical_needs', next)}
            customPlaceholder="补充医疗需求"
            variant="pill"
          />
          <TagSelector
            label="药物治疗"
            values={form.medications ?? []}
            options={[]}
            onChange={(next) => update('medications', next)}
            customPlaceholder="例如：药名 + 剂量 + 时间"
            variant="pill"
          />
          <TagSelector
            label="其他健康问题"
            values={form.health_conditions ?? []}
            options={[]}
            onChange={(next) => update('health_conditions', next)}
            customPlaceholder="例如：便秘、湿疹、慢性鼻炎"
            variant="pill"
          />
        </div>
      </section>

      <section className="onboarding-section">
        <div>
          <p className="eyebrow">行为与情绪</p>
          <h3>记录触发器、行为模式和学习障碍</h3>
        </div>
        <div className="grid two">
          <TagSelector
            label="常见触发器"
            values={form.triggers ?? []}
            options={triggerOptions}
            onChange={(next) => update('triggers', next)}
            customPlaceholder="补充触发器"
          />
          <TagSelector
            label="感官敏感"
            values={form.sensory_flags ?? []}
            options={sensoryOptions}
            onChange={(next) => update('sensory_flags', next)}
            customPlaceholder="补充感官敏感项"
          />
          <TagSelector
            label="有效安抚方式"
            values={form.soothing_methods ?? []}
            options={soothingOptions}
            onChange={(next) => update('soothing_methods', next)}
            customPlaceholder="补充安抚方式"
          />
          <TagSelector
            label="固定行为模式"
            values={form.behavior_patterns ?? []}
            options={behaviorPatternOptions}
            onChange={(next) => update('behavior_patterns', next)}
            customPlaceholder="补充行为模式"
          />
          <TagSelector
            label="需要特别留意的行为"
            values={form.behavior_risks ?? []}
            options={behaviorRiskOptions}
            onChange={(next) => update('behavior_risks', next)}
            customPlaceholder="补充高风险行为"
          />
          <TagSelector
            label="情绪波动类型"
            values={form.emotion_patterns ?? []}
            options={emotionPatternOptions}
            onChange={(next) => update('emotion_patterns', next)}
            customPlaceholder="补充情绪类型"
          />
          <TagSelector
            label="学习支持需求"
            values={form.learning_needs ?? []}
            options={learningNeedOptions}
            onChange={(next) => update('learning_needs', next)}
            customPlaceholder="补充学习需求"
          />
          <TagSelector
            label="高摩擦场景"
            values={form.high_friction_scenarios ?? []}
            options={frictionScenarioOptions.map((item) => ({ value: item.value, label: item.label }))}
            onChange={(next) => update('high_friction_scenarios', next)}
            customPlaceholder="补充场景键，如 transition"
            variant="pill"
          />
        </div>
        <label>
          <span className="label">禁忌行为 / 明确不要做的事</span>
          <textarea
            className="input"
            rows={3}
            value={form.taboo_behaviors ?? ''}
            onChange={(e) => update('taboo_behaviors', e.target.value)}
            placeholder="例如：不要突然拉走；不要在很多人面前催促；不要连续追问。"
          />
        </label>
      </section>

      <section className="onboarding-section">
        <div>
          <p className="eyebrow">社交与教育</p>
          <h3>补充学校、训练和社交圈信息</h3>
        </div>
        <div className="grid two">
          <label>
            <span className="label">教育环境</span>
            <select
              className="input"
              value={form.school_type ?? ''}
              onChange={(e) => update('school_type', (e.target.value || undefined) as OnboardingSetupPayload['school_type'])}
            >
              <option value="">暂不填写</option>
              {schoolTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <TagSelector
            label="正在接受的训练 / 支持"
            values={form.social_training ?? []}
            options={socialTrainingOptions}
            onChange={(next) => update('social_training', next)}
            customPlaceholder="补充训练或支持活动"
            variant="pill"
          />
        </div>
        <label>
          <span className="label">学校情况、朋友和社交圈</span>
          <textarea
            className="input"
            rows={4}
            value={form.school_notes ?? ''}
            onChange={(e) => update('school_notes', e.target.value)}
            placeholder="例如：在普通小学融合班，和 1 位固定同学关系较好；午休和集体活动较容易紧张。"
          />
        </label>
      </section>

      <section className="onboarding-section">
        <div>
          <p className="eyebrow">家长情况</p>
          <h3>补充时间安排、压力与支持网络</h3>
        </div>
        <div className="grid two">
          <TagSelector
            label="家长时间安排"
            values={form.parent_schedule ?? []}
            options={parentScheduleOptions}
            onChange={(next) => update('parent_schedule', next)}
            customPlaceholder="补充时间安排"
            variant="pill"
          />
          <TagSelector
            label="当前主要压力"
            values={form.parent_stressors ?? []}
            options={parentStressorOptions}
            onChange={(next) => update('parent_stressors', next)}
            customPlaceholder="补充压力来源"
            variant="pill"
          />
          <TagSelector
            label="已参与的支持性活动"
            values={form.parent_support_actions ?? []}
            options={parentSupportActionOptions}
            onChange={(next) => update('parent_support_actions', next)}
            customPlaceholder="补充支持性活动"
            variant="pill"
          />
          <TagSelector
            label="家长情感支持来源"
            values={form.parent_emotional_supports ?? []}
            options={parentEmotionalSupportOptions}
            onChange={(next) => update('parent_emotional_supports', next)}
            customPlaceholder="补充情感支持来源"
            variant="pill"
          />
        </div>
        <TagSelector
          label="可用支持者"
          values={form.available_supporters ?? []}
          options={supporterOptions}
          onChange={(next) => update('available_supporters', next)}
          customPlaceholder="补充可用支持者"
          variant="pill"
        />
      </section>
    </div>
  );
}
