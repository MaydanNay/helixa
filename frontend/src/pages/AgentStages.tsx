import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp,
  User, Brain, Heart, BookOpen, Users, Briefcase, Activity,
  Globe, Mic, DollarSign, Database, Lock, Eye,
  LayoutList, Loader2, Zap, ListChecks, ShieldCheck
} from 'lucide-react';

const API = '/api/v1';

const STAGE_META: Record<string, { label: string; description: string; icon: any; color: string }> = {
  demographics:      { label: 'Демография',           description: 'Имя, возраст, пол, гражданство',             icon: User,         color: 'blue' },
  psychology:        { label: 'Психология',            description: 'Личность, MBTI, эмоциональный интеллект',    icon: Brain,        color: 'purple' },
  health:            { label: 'Здоровье',              description: 'Физическое и ментальное здоровье',            icon: Heart,        color: 'rose' },
  biography:         { label: 'Биография',             description: 'История жизни, ключевые события',            icon: BookOpen,     color: 'amber' },
  family:            { label: 'Семья',                 description: 'Родственные связи, отношения',               icon: Users,        color: 'green' },
  experience:        { label: 'Опыт',                  description: 'Образование, карьера, навыки',               icon: Briefcase,    color: 'cyan' },
  behavioral:        { label: 'Поведение',             description: 'Привычки, рутина, реакции',                  icon: Activity,     color: 'orange' },
  sociology:         { label: 'Социология',            description: 'Соцсети, культура, мировоззрение',           icon: Globe,        color: 'teal' },
  voice:             { label: 'Голос',                 description: 'Стиль речи, лексика, манера общения',        icon: Mic,          color: 'violet' },
  financial:         { label: 'Финансы',               description: 'Доходы, расходы, финансовые цели',           icon: DollarSign,   color: 'emerald' },
  memory:            { label: 'Память',                description: 'Автобиографические факты, эпизоды',          icon: Database,     color: 'sky' },
  private:           { label: 'Приватное',             description: 'Секреты, личная история',                    icon: Lock,         color: 'red' },
  planning_strategy: { label: 'Стратегия жизни',      description: 'Долгосрочные цели и амбиции',                icon: Zap,          color: 'yellow' },
  planning_routine:  { label: 'Рутина и привычки',    description: 'Ежедневные ритуалы и дисциплина',            icon: Clock,        color: 'indigo' },
  planning_day:      { label: 'Распорядок дня',       description: 'Детальный график активности',                icon: ListChecks,   color: 'pink' },
  ci_audit:          { label: 'Психо-аудит (QA)',     description: 'Проверка консистентности личности',          icon: ShieldCheck,  color: 'emerald' },
  ci_exam:           { label: 'Экзамен знаний (QA)',   description: 'Тест на глубину памяти и фактов',            icon: BookOpen,     color: 'cyan' },
  ci_stress:         { label: 'Стресс-тест (QA)',      description: 'Проверка эмоциональной устойчивости',        icon: Activity,     color: 'red' },
  editor:            { label: 'Финальный синтез',     description: 'Согласование всех аспектов личности',        icon: Eye,          color: 'primary' },
};

const SECTION_GROUPS = [
  {
    title: 'Core DNA Profile',
    stages: ['demographics', 'psychology', 'health', 'biography', 'family', 'experience', 'behavioral', 'sociology', 'voice', 'financial', 'memory', 'private']
  },
  {
    title: 'Жизненный Цикл и Планирование',
    stages: ['planning_strategy', 'planning_routine', 'planning_day']
  },
  {
    title: 'Контроль Качества и Тюнинг',
    stages: ['ci_audit', 'ci_exam', 'ci_stress', 'editor']
  }
];
// ↑ Must match STAGE_ORDER in app/services/utils.py exactly

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  blue:    { bg: 'bg-blue-500/10',    border: 'border-blue-500/30',    text: 'text-blue-300',    badge: 'bg-blue-500/20' },
  purple:  { bg: 'bg-purple-500/10',  border: 'border-purple-500/30',  text: 'text-purple-300',  badge: 'bg-purple-500/20' },
  rose:    { bg: 'bg-rose-500/10',    border: 'border-rose-500/30',    text: 'text-rose-300',    badge: 'bg-rose-500/20' },
  amber:   { bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   text: 'text-amber-300',   badge: 'bg-amber-500/20' },
  green:   { bg: 'bg-green-500/10',   border: 'border-green-500/30',   text: 'text-green-300',   badge: 'bg-green-500/20' },
  cyan:    { bg: 'bg-cyan-500/10',    border: 'border-cyan-500/30',    text: 'text-cyan-300',    badge: 'bg-cyan-500/20' },
  orange:  { bg: 'bg-orange-500/10',  border: 'border-orange-500/30',  text: 'text-orange-300',  badge: 'bg-orange-500/20' },
  teal:    { bg: 'bg-teal-500/10',    border: 'border-teal-500/30',    text: 'text-teal-300',    badge: 'bg-teal-500/20' },
  violet:  { bg: 'bg-violet-500/10',  border: 'border-violet-500/30',  text: 'text-violet-300',  badge: 'bg-violet-500/20' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-300', badge: 'bg-emerald-500/20' },
  sky:     { bg: 'bg-sky-500/10',     border: 'border-sky-500/30',     text: 'text-sky-300',     badge: 'bg-sky-500/20' },
  red:     { bg: 'bg-red-500/10',     border: 'border-red-500/30',     text: 'text-red-300',     badge: 'bg-red-500/20' },
  indigo:  { bg: 'bg-indigo-500/10',  border: 'border-indigo-500/30',  text: 'text-indigo-300',  badge: 'bg-indigo-500/20' },
  pink:    { bg: 'bg-pink-500/10',    border: 'border-pink-500/30',    text: 'text-pink-300',    badge: 'bg-pink-500/20' },
  yellow:  { bg: 'bg-yellow-500/10',  border: 'border-yellow-500/30',  text: 'text-yellow-300',  badge: 'bg-yellow-500/20' },
  primary: { bg: 'bg-primary-500/10', border: 'border-primary-500/30', text: 'text-primary-300', badge: 'bg-primary-500/20' },
};

interface StageData {
  agent_id: string;
  name: string;
  role: string;
  generation_mode: string;
  stages: Record<string, string>;
  complete: boolean;
}

function statusIcon(status: string) {
  if (status === 'ok' || status === 'done') return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
  if (status === 'error' || status === 'failed') return <XCircle className="w-5 h-5 text-red-400" />;
  if (status === 'running' || status === 'processing') return <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />;
  return <Clock className="w-5 h-5 text-slate-500" />;
}

function statusLabel(status: string) {
  if (status === 'ok' || status === 'done') return { text: '✅ Готово', cls: 'text-emerald-400' };
  if (status === 'error' || status === 'failed') return { text: '❌ Ошибка', cls: 'text-red-400' };
  if (status === 'running' || status === 'processing') return { text: '⏳ Генерируется', cls: 'text-yellow-400' };
  return { text: '⬜ Ожидание', cls: 'text-slate-500' };
}

export default function AgentStages() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<StageData | null>(null);
  const [agentData, setAgentData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      axios.get(`${API}/agents/${id}/stages`),
      axios.get(`${API}/agents/${id}`),
    ]).then(([stagesRes, agentRes]) => {
      setData(stagesRes.data);
      setAgentData(agentRes.data?.agent_data || {});
    }).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 text-primary-400 animate-spin" />
          <p className="text-slate-400">Загрузка этапов...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-slate-400">Агент не найден</p>
      </div>
    );
  }

  const stages = data.stages;
  const stageKeys = Object.keys(STAGE_META);

  // Count statuses
  const okCount = stageKeys.filter(k => stages[k] === 'ok' || stages[k] === 'done').length;
  const errorCount = stageKeys.filter(k => stages[k] === 'error' || stages[k] === 'failed').length;
  const pendingCount = stageKeys.filter(k => !stages[k] || stages[k] === 'pending').length;
  const totalStages = stageKeys.length;
  const progressPct = Math.round((okCount / totalStages) * 100);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Link
            to={`/agent/${id}`}
            className="p-2 glass-panel rounded-xl hover:border-primary-500/50 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <LayoutList className="w-6 h-6 text-primary-400" />
              <h2 className="text-2xl font-bold">Этапы генерации</h2>
            </div>
            <p className="text-slate-400 text-sm">
              <span className="text-white font-medium">{data.name}</span>
              {data.role && <span> · {data.role}</span>}
              <span className="ml-2 px-2 py-0.5 rounded-full bg-slate-700 text-xs text-slate-300 uppercase tracking-wider font-bold">
                {data.generation_mode || 'staged'} mode
              </span>
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="hidden md:flex items-center gap-3 text-sm">
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5" /> {okCount} готово
          </span>
          {errorCount > 0 && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-300">
              <XCircle className="w-3.5 h-3.5" /> {errorCount} ошибок
            </span>
          )}
          {pendingCount > 0 && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-700 border border-slate-600 text-slate-400">
              <Clock className="w-3.5 h-3.5" /> {pendingCount} ожидают
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="glass-panel rounded-2xl p-5">
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm text-slate-400 font-medium">Общий прогресс синтеза</span>
          <span className="text-sm font-bold text-white">{okCount} / {totalStages} этапов</span>
        </div>
        <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
            className="h-full bg-gradient-to-r from-primary-500 to-emerald-500 rounded-full"
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-slate-500">
          <span>0%</span>
          <span className="font-semibold text-primary-300">{progressPct}%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Sections and Stages grid */}
      <div className="space-y-12">
        {SECTION_GROUPS.map((section) => (
          <div key={section.title} className="space-y-6">
            <div className="flex items-center gap-4">
              <h3 className="text-xl font-bold text-slate-200">{section.title}</h3>
              <div className="h-px flex-1 bg-gradient-to-r from-slate-700 to-transparent" />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {section.stages.map((key, i) => {
          const meta = STAGE_META[key];
          const status = stages[key] || 'pending';
          const colors = COLOR_MAP[meta.color];
          const isOk = status === 'ok' || status === 'done';
          const isError = status === 'error' || status === 'failed';
          const isExpanded = expanded === key;
          const Icon = meta.icon;
          const stageDataPayload = agentData?.[key];
          const hasData = stageDataPayload !== undefined && stageDataPayload !== null;
          const sl = statusLabel(status);

          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className={`glass-panel rounded-2xl overflow-hidden border transition-all ${
                isOk ? 'border-emerald-500/20 hover:border-emerald-500/40' :
                isError ? 'border-red-500/30 bg-red-500/3' :
                'border-slate-700/50 hover:border-slate-600/50'
              }`}
            >
              {/* Card header */}
              <div
                className={`p-4 flex items-start justify-between cursor-pointer ${isOk ? 'hover:bg-emerald-500/5' : ''}`}
                onClick={() => setExpanded(isExpanded ? null : key)}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-xl ${colors.bg} ${colors.border} border`}>
                    <Icon className={`w-4 h-4 ${colors.text}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{meta.label}</span>
                      <span className={`text-xs font-medium ${sl.cls}`}>{sl.text}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{meta.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-0.5 flex-shrink-0">
                  {statusIcon(status)}
                  {hasData && (
                    isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Expandable JSON preview */}
              <AnimatePresence>
                {isExpanded && hasData && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden"
                  >
                    <div className={`border-t ${colors.border} mx-4`} />
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-xs font-semibold uppercase tracking-wider ${colors.text}`}>
                          Данные этапа
                        </span>
                        <span className="text-xs text-slate-500">
                          {typeof stageDataPayload === 'object'
                            ? `${Array.isArray(stageDataPayload) ? stageDataPayload.length : Object.keys(stageDataPayload).length} ${Array.isArray(stageDataPayload) ? 'эл.' : 'поле(й)'}`
                            : ''}
                        </span>
                      </div>
                      <pre className={`text-xs ${colors.text} bg-slate-900/60 rounded-xl p-3 overflow-auto max-h-64 scrollbar-thin scrollbar-thumb-slate-700 leading-relaxed`}>
                        {JSON.stringify(stageDataPayload, null, 2)}
                      </pre>
                    </div>
                  </motion.div>
                )}
                {isExpanded && !hasData && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden"
                  >
                    <div className={`border-t border-slate-700 mx-4`} />
                    <div className="p-4 text-center text-slate-500 text-sm py-6">
                      Данных нет — этап ещё не был сгенерирован
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Back link */}
      <div className="flex justify-center pt-4">
        <Link
          to={`/agent/${id}`}
          className="flex items-center gap-2 text-slate-400 hover:text-primary-300 transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад к профилю агента
        </Link>
      </div>
    </div>
  );
}
