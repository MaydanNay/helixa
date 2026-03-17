import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, Sparkles, CheckCircle, Loader2, XCircle, Clock, ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

const API = '/api/v1';
// Exponential back-off: starts at 2s, doubles each idle tick, caps at 15s
const POLL_MIN_MS = 2000;
const POLL_MAX_MS = 15000;

const STAGE_ORDER = [
    "demographics", "psychology", "health", "biography",
    "family", "experience", "behavioral", "sociology",
    "voice", "financial", "memory", "private", "editor"
];

const STAGE_META: Record<string, { label: string; emoji: string; desc: string }> = {
    demographics: { label: "Демография", emoji: "🌍", desc: "Имя, возраст, город, профессия" },
    psychology: { label: "Психология", emoji: "🧠", desc: "Личность, MBTI, Big5, мотивации" },
    health: { label: "Здоровье", emoji: "💪", desc: "Физические данные, биоритмы, хронотип" },
    biography: { label: "Биография", emoji: "📖", desc: "История жизни, происхождение, вехи" },
    family: { label: "Семья", emoji: "👨‍👩‍👧", desc: "Родители, братья-сёстры, домохозяйство" },
    experience: { label: "Опыт", emoji: "💼", desc: "Карьера, образование, навыки" },
    behavioral: { label: "Поведение", emoji: "🎯", desc: "Привычки, паттерны потребления, стиль решений" },
    sociology: { label: "Социология", emoji: "🌐", desc: "Социальная сеть, стиль общения" },
    voice: { label: "Голос ДНК", emoji: "🎙️", desc: "Тон, речевые паттерны, словарный запас" },
    financial: { label: "Финансы", emoji: "💰", desc: "Доход, расходы, инвестиционная стратегия" },
    memory: { label: "Память", emoji: "💾", desc: "Базовые знания, навыки, семантическая память" },
    private: { label: "Приватное", emoji: "🔐", desc: "Секреты, страхи, скрытые мотивации" },
    editor: { label: "Редактор ИИ", emoji: "✏️", desc: "Проверка согласованности, финальная полировка" },
};

type StageStatus = 'pending' | 'running' | 'done' | 'error';

const STATUS_COLOR: Record<StageStatus, string> = {
    pending: 'border-slate-700/50 bg-slate-900/30',
    running: 'border-primary-500/50 bg-primary-500/5 shadow-lg shadow-primary-500/10',
    done: 'border-emerald-500/40 bg-emerald-500/5',
    error: 'border-red-500/40 bg-red-500/5',
};

const STATUS_ICON: Record<StageStatus, React.ReactElement> = {
    pending: <Clock className="w-3.5 h-3.5 text-slate-600" />,
    running: <Loader2 className="w-3.5 h-3.5 text-primary-400 animate-spin" />,
    done: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
    error: <XCircle className="w-3.5 h-3.5 text-red-400" />,
};

const STATUS_BADGE: Record<StageStatus, string> = {
    pending: 'text-slate-600 bg-slate-800',
    running: 'text-primary-300 bg-primary-500/20 animate-pulse',
    done: 'text-emerald-400 bg-emerald-500/15',
    error: 'text-red-400 bg-red-500/15',
};

const STATUS_TEXT: Record<StageStatus, string> = {
    pending: 'Ожидает', running: 'Генерируется…', done: 'Готово', error: 'Ошибка',
};

export default function StagedCreate() {
    const navigate = useNavigate();
    const [form, setForm] = useState({ name_hint: '', role_hint: '', personality_hint: '', country_hint: '', city_hint: '' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [agentId, setAgentId] = useState<string | null>(null);
    const [agentName, setAgentName] = useState<string>('');
    const [stages, setStages] = useState<Record<string, StageStatus>>({});
    const [complete, setComplete] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollIntervalRef = useRef<number>(POLL_MIN_MS);
    const prevStagesRef = useRef<string>('');

    useEffect(() => {
        if (!agentId || complete) {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            return;
        }

        const poll = async () => {
            try {
                const res = await axios.get(`${API}/agents/${agentId}/stages`);
                const d = res.data;
                const newStagesStr = JSON.stringify(d.stages || {});

                // Reset back-off if something changed, otherwise grow interval
                if (newStagesStr !== prevStagesRef.current) {
                    pollIntervalRef.current = POLL_MIN_MS;
                    prevStagesRef.current = newStagesStr;
                } else {
                    pollIntervalRef.current = Math.min(pollIntervalRef.current * 1.5, POLL_MAX_MS);
                }

                setStages(d.stages || {});
                if (d.name && d.name !== 'Generating…') setAgentName(d.name);
                if (d.complete) {
                    setComplete(true);
                    return; // stop polling
                }
            } catch (e) { console.error(e); }
            timeoutRef.current = setTimeout(poll, pollIntervalRef.current);
        };

        timeoutRef.current = setTimeout(poll, POLL_MIN_MS);
        return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
    }, [agentId, complete]);

    const doneCount = Object.values(stages).filter(s => s === 'done').length;
    const pct = STAGE_ORDER.length > 0 ? Math.round((doneCount / STAGE_ORDER.length) * 100) : 0;

    const handleLaunch = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post(`${API}/generate/staged-soul`, {
                ...form,
            });
            setAgentId(res.data.agent_id);
            setStages(res.data.stages || {});
        } catch (e: any) {
            setError(e?.response?.data?.detail || e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-5xl mx-auto mt-4"
        >
            {/* Заголовок */}
            <div className="flex items-center gap-4 mb-8">
                <div className="bg-primary-500/20 p-3 rounded-2xl">
                    <BrainCircuit className="w-8 h-8 text-primary-400" />
                </div>
                <div>
                    <h2 className="text-3xl font-bold bg-gradient-to-r from-primary-400 to-emerald-400 bg-clip-text text-transparent">
                        Глубокий Синтез — 13 Этапов
                    </h2>
                    <p className="text-slate-400 mt-1">Полная поэтапная генерация в стиле Mimora с живым прогрессом</p>
                </div>
                <Link to="/create" className="ml-auto text-sm text-slate-400 hover:text-primary-400 transition-colors">
                    ← Быстрая генерация
                </Link>
            </div>

            {/* Форма */}
            {!agentId && (
                <motion.div className="glass-panel rounded-2xl p-8 border border-primary-500/20 shadow-2xl shadow-primary-500/10 space-y-5 mb-8">
                    {error && (
                        <div className="p-4 bg-red-500/10 border border-red-500/40 rounded-xl text-red-200 text-sm flex gap-2 items-start">
                            <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
                        </div>
                    )}
                    <div className="grid grid-cols-2 gap-5">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">Имя (необязательно)</label>
                            <input type="text" value={form.name_hint} onChange={e => setForm({ ...form, name_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Айко" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">Роль / Профессия</label>
                            <input type="text" value={form.role_hint} onChange={e => setForm({ ...form, role_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Кибер-хакер" />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-5">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">🌍 Страна</label>
                            <input type="text" value={form.country_hint} onChange={e => setForm({ ...form, country_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Япония" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">🏙️ Город</label>
                            <input type="text" value={form.city_hint} onChange={e => setForm({ ...form, city_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Токио" />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-300 ml-1">Черты личности</label>
                        <textarea value={form.personality_hint} onChange={e => setForm({ ...form, personality_hint: e.target.value })}
                            rows={3}
                            className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600 resize-none"
                            placeholder="например: Интроверт, аналитик, тёмный юмор, высокий интеллект…" />
                    </div>
                    <button onClick={handleLaunch} disabled={loading}
                        className="w-full mt-2 bg-gradient-to-r from-primary-600 to-emerald-600 hover:from-primary-500 hover:to-emerald-500 text-white font-bold text-lg py-4 rounded-xl flex items-center justify-center gap-3 transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-xl shadow-primary-500/25 disabled:opacity-50 disabled:pointer-events-none">
                        {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : <><Sparkles className="w-6 h-6" /><span>Начать Глубокий Синтез</span></>}
                    </button>
                </motion.div>
            )}

            {/* Прогресс */}
            <AnimatePresence>
                {agentId && (
                    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

                        {/* Общий прогресс */}
                        <div className="glass-panel rounded-2xl p-5 border border-primary-500/20">
                            <div className="flex justify-between items-center mb-3">
                                <div>
                                    <span className="font-semibold text-slate-200">
                                        {complete && agentName ? `${agentName} — Готово` : `Этап ${doneCount} из ${STAGE_ORDER.length}`}
                                    </span>
                                    {agentName && !complete && <span className="ml-2 text-slate-500 text-sm">(генерируется…)</span>}
                                </div>
                                <span className="text-primary-400 font-bold">{pct}%</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-2.5">
                                <motion.div
                                    className="bg-gradient-to-r from-primary-500 to-emerald-500 h-2.5 rounded-full"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${pct}%` }}
                                    transition={{ duration: 0.5 }}
                                />
                            </div>
                            {complete && (
                                <div className="mt-4 flex gap-3">
                                    <button onClick={() => navigate(`/`)}
                                        className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition-all">
                                        <span>Открыть в Галерее</span><ArrowRight className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Карточки этапов */}
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                            {STAGE_ORDER.map((stage, i) => {
                                const status = (stages[stage] as StageStatus) || 'pending';
                                const meta = STAGE_META[stage];
                                return (
                                    <motion.div
                                        key={stage}
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: i * 0.04 }}
                                        className={`rounded-xl p-3.5 border transition-all ${STATUS_COLOR[status]}`}
                                    >
                                        <div className="flex items-start justify-between mb-2">
                                            <span className="text-xl">{meta.emoji}</span>
                                            {STATUS_ICON[status]}
                                        </div>
                                        <div className="font-semibold text-sm text-slate-200 mb-0.5">{meta.label}</div>
                                        <div className="text-xs text-slate-500 leading-tight mb-2">{meta.desc}</div>
                                        <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full font-semibold ${STATUS_BADGE[status]}`}>
                                            {STATUS_TEXT[status]}
                                        </span>
                                    </motion.div>
                                );
                            })}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}
