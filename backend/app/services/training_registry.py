from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingDomainDefinition:
    area_key: str
    title: str
    summary: str
    importance: str
    related_challenges: tuple[str, ...]
    principles: tuple[str, ...]
    suggested_scenarios: tuple[str, ...]
    cautions: tuple[str, ...]
    method_examples: tuple[str, ...]
    fallback_options: tuple[str, ...]


DOMAIN_REGISTRY: dict[str, TrainingDomainDefinition] = {
    "emotion_regulation": TrainingDomainDefinition(
        area_key="emotion_regulation",
        title="情绪调节",
        summary="帮助孩子更早识别情绪波动，并在升级前找到可接受的降温动作。",
        importance="情绪先稳住，沟通、任务和社交训练才更容易真正进入。",
        related_challenges=("突然崩溃", "一被提醒就升级", "切换前情绪拉扯"),
        principles=("先共调再训练", "只给两个可选降温动作", "把恢复速度看得比讲道理更重要"),
        suggested_scenarios=("起冲突前 3 分钟", "放学后恢复时段", "被拒绝或等待前"),
        cautions=("不要连续追问原因", "不要在升级时讲规则", "孩子状态差时先停训练"),
        method_examples=("情绪温度计", "两选一降温动作", "先命名感受再行动"),
        fallback_options=("只做家长命名情绪", "直接去安静角落", "先结束要求，晚点再练"),
    ),
    "transition_flexibility": TrainingDomainDefinition(
        area_key="transition_flexibility",
        title="过渡与变化适应",
        summary="把切换前的不可预期，变成可预告、可准备、可完成的小步骤。",
        importance="过渡变稳后，出门、收尾、睡前和任务启动都会更顺。",
        related_challenges=("停不下喜欢的活动", "一变动就崩溃", "出门前拉扯"),
        principles=("提前预告", "视觉提示优先", "切换前不追加新要求"),
        suggested_scenarios=("出门前", "关屏前", "从玩到任务前"),
        cautions=("不要临时改下一步", "不要一边催一边收", "过渡前不要加码"),
        method_examples=("视觉倒计时", "先后卡", "收尾 1 步法"),
        fallback_options=("只做口头预告", "一起收 1 件物品", "缩短倒计时"),
    ),
    "communication": TrainingDomainDefinition(
        area_key="communication",
        title="功能性沟通/表达需求",
        summary="让孩子把拉扯、哭闹或僵住，逐步替换成可理解的表达方式。",
        importance="需求表达更清楚后，很多高摩擦场景会直接降级。",
        related_challenges=("不会主动求助", "只会哭闹表达", "听懂但不会说"),
        principles=("先给明确表达入口", "自然机会里练", "有任何主动表达就及时回应"),
        suggested_scenarios=("想要东西时", "需要帮助时", "不想继续时"),
        cautions=("不要追求完整长句", "不要抢答", "不要在孩子未进入时高频提问"),
        method_examples=("二选一表达", "指物/图片卡", "一句请求脚手架"),
        fallback_options=("先允许指物", "先做手势", "只保留一个词"),
    ),
    "waiting_tolerance": TrainingDomainDefinition(
        area_key="waiting_tolerance",
        title="等待与延迟满足",
        summary="把‘马上要’练成‘能等一下’，帮助孩子在高频等待场景里更稳定。",
        importance="等待能力增强后，排队、轮流、外出和家务协作都会轻松很多。",
        related_challenges=("一等就急", "排队崩溃", "轮不到自己就抗拒"),
        principles=("从极短等待开始", "等待时给可做的小动作", "一旦做到立刻确认成功"),
        suggested_scenarios=("拿零食前", "排队时", "轮流游戏时"),
        cautions=("不要一上来拉长等待", "不要只说‘等一下’没有支撑", "不要在高负荷时硬练"),
        method_examples=("等待倒计时", "手里有事做", "完成后即时确认"),
        fallback_options=("等待 3 秒也算", "先看卡片等", "换到更安静场景"),
    ),
    "task_initiation": TrainingDomainDefinition(
        area_key="task_initiation",
        title="作业/任务启动",
        summary="训练孩子更容易开始任务，而不是一开始就卡在起步阶段。",
        importance="很多家庭不是做不完，而是根本开始不了；起步能力是执行的入口。",
        related_challenges=("作业开始困难", "一提任务就逃开", "坐不下来"),
        principles=("先练起步，不追求做满", "步骤拆小", "完成第一步就算成功"),
        suggested_scenarios=("作业开始前", "坐下任务前", "晚间流程启动时"),
        cautions=("不要一次给完整任务", "不要起步前讲太多", "不要把没做完等同失败"),
        method_examples=("第一步卡", "10 秒起步", "做完一格就停"),
        fallback_options=("家长带着起步", "缩到 1 步", "换到更容易开始的时段"),
    ),
    "bedtime_routine": TrainingDomainDefinition(
        area_key="bedtime_routine",
        title="睡前流程配合",
        summary="让睡前切换更可预期，减少洗澡、刷牙、上床时的反复拉扯。",
        importance="睡前更顺，第二天整体负荷往往也会下降。",
        related_challenges=("洗澡抗拒", "拖延上床", "一到睡前就升级"),
        principles=("固定顺序", "视觉流程", "每晚只盯一个卡点优化"),
        suggested_scenarios=("洗澡前", "刷牙时", "熄灯前"),
        cautions=("不要睡前临时加内容", "不要一直催", "状态差时优先缩流程"),
        method_examples=("睡前流程卡", "固定收尾动作", "睡前选择题"),
        fallback_options=("先做 1 个环节", "缩短流程", "只保留安静收尾"),
    ),
    "daily_living": TrainingDomainDefinition(
        area_key="daily_living",
        title="日常自理",
        summary="把洗澡、刷牙、穿衣等拆成能进入的小步骤，降低家长全程接管的压力。",
        importance="自理更稳，家庭节奏和孩子独立性都会提升。",
        related_challenges=("刷牙抗拒", "穿衣拖延", "洗澡过程冲突"),
        principles=("先拆步", "每次只盯一个环节", "固定提示词"),
        suggested_scenarios=("晨起", "洗澡前后", "出门前穿衣"),
        cautions=("不要一次练完整流程", "不要边做边加要求", "先保成功体验"),
        method_examples=("步骤卡", "示范 1 次", "共同完成 1 步"),
        fallback_options=("只练第 1 步", "家长协助更多", "改到低压力时段"),
    ),
    "social_interaction": TrainingDomainDefinition(
        area_key="social_interaction",
        title="社交回应/轮流",
        summary="让孩子在低压力场景里练回应、轮流和共同注意，而不是直接上高难社交。",
        importance="社交回应更稳，外出、同伴和家庭互动都会更顺。",
        related_challenges=("不回应别人", "轮流困难", "共同注意维持短"),
        principles=("短回合", "低压力", "先共同注意再轮流"),
        suggested_scenarios=("和家长玩 3 回合", "看同一件东西时", "同伴活动前热身"),
        cautions=("不要一次塞太多社交目标", "不要强迫眼神接触", "不在高压场景硬练"),
        method_examples=("三回合轮流", "共同看同一物件", "回应名字小游戏"),
        fallback_options=("先只共同注意", "只轮 1 回合", "先和熟悉照护者练"),
    ),
    "sensory_regulation": TrainingDomainDefinition(
        area_key="sensory_regulation",
        title="感官调节",
        summary="帮助家长和孩子更早发现感官过载前兆，并提前做降刺激处理。",
        importance="感官调节更稳后，很多看似‘不配合’的问题会明显减轻。",
        related_challenges=("声音一大就崩", "环境变化后很难恢复", "人多场景抗拒"),
        principles=("提前识别前兆", "固定降载动作", "把环境改造看得和训练同样重要"),
        suggested_scenarios=("放学后", "外出前", "家里变吵前"),
        cautions=("不要要求孩子硬忍", "不要把过载当态度问题", "出现明显过载就停普通训练"),
        method_examples=("前兆识别", "固定安静动作", "先降刺激再继续"),
        fallback_options=("只练去安静点", "缩短停留时间", "先撤离再记录"),
    ),
    "simple_compliance": TrainingDomainDefinition(
        area_key="simple_compliance",
        title="遵从简单指令",
        summary="练的是孩子更容易听懂并开始做，不是无条件服从。",
        importance="简单指令更好进入后，家庭协作和安全指令会更稳定。",
        related_challenges=("提醒很多次才动", "一说就反抗", "指令太长就断开"),
        principles=("一句一事", "先确认听到", "动作成功比口头答应更重要"),
        suggested_scenarios=("收玩具前", "出门前", "坐下前"),
        cautions=("不要多句连发", "不要一边命令一边解释一堆", "状态差时先减要求"),
        method_examples=("一句一事", "动作示范", "完成即确认"),
        fallback_options=("缩到一个动作", "家长同步做", "换成视觉提示"),
    ),
}


SCENARIO_LABELS: dict[str, str] = {
    "transition": "活动切换/出门前",
    "bedtime": "睡前流程",
    "homework": "学习或坐下任务前",
    "outing": "外出或社交活动前",
    "meltdown": "情绪升级前",
}


def get_domain(area_key: str) -> TrainingDomainDefinition:
    return DOMAIN_REGISTRY[area_key]


def all_domains() -> list[TrainingDomainDefinition]:
    return list(DOMAIN_REGISTRY.values())
