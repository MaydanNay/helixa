import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import {
    ArrowLeft, User, MapPin, Briefcase, MessageCircle,
    BrainCircuit, Users, Wallet, ShieldAlert, Trash2, CalendarClock, Zap, Beaker, ShieldCheck,
    LayoutList, Share2, Star, CheckCircle2, Loader2, Sparkles, Activity
} from 'lucide-react';
import AgentGraphView from '../components/AgentGraphView';

interface AgentData {
    id: string;
    name: string;
    role: string | null;
    avatar_url: string | null;
    created_at: string;
    agent_data: any;
    ci_score?: number | null;
    ci_passed?: boolean | null;
    ci_report?: any | null;
}

export default function AgentProfile() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [agent, setAgent] = useState<AgentData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [generatingLifecycle, setGeneratingLifecycle] = useState(false);
    const [stages, setStages] = useState<Record<string, string>>({});
    const [isPolling, setIsPolling] = useState(false);

    const handleDelete = async () => {
        if (!window.confirm('Вы уверены, что хотите удалить этого агента? Это действие необратимо.')) return;
        const apiBase = '/api/v1';
        try {
            await axios.delete(`${apiBase}/agents/${id}`);
            navigate('/');
        } catch (err: any) {
            alert(err.message || 'Ошибка удаления');
        }
    };

    useEffect(() => {
        const apiBase = '/api/v1';
        axios.get(`${apiBase}/agents/${id}`)
            .then(res => setAgent(res.data))
            .catch(err => setError(err.message || 'Failed to load agent profile'))
            .finally(() => setLoading(false));

        // Fetch initial stages
        axios.get(`${apiBase}/agents/${id}/stages`)
            .then(res => {
                const s = res.data.stages || {};
                setStages(s);
                const values = Object.values(s);
                if (values.some(v => v === 'running' || v === 'waiting')) {
                    setIsPolling(true);
                }
            })
            .catch(console.error);
    }, [id]);

    useEffect(() => {
        if (!isPolling || !id) return;

        const apiBase = '/api/v1';
        const interval = setInterval(async () => {
            try {
                const res = await axios.get(`${apiBase}/agents/${id}/stages`);
                const s = res.data.stages || {};
                setStages(s);
                const values = Object.values(s);
                const stillRunning = values.some(v => v === 'running' || v === 'waiting');
                
                // If we JUST started and s is empty, don't stop polling yet - worker might be cold
                if (!stillRunning && values.length > 0) {
                    setIsPolling(false);
                    // Refresh agent data when done
                    const agentRes = await axios.get(`${apiBase}/agents/${id}`);
                    setAgent(agentRes.data);
                }
            } catch (err) {
                console.error('Polling error:', err);
                setIsPolling(false);
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [isPolling, id]);

    const handleGenerateLifecycle = async () => {
        setGeneratingLifecycle(true);
        const apiBase = '/api/v1';
        try {
            await axios.post(`${apiBase}/generate/lifecycle`, {
                agent_id: id,
                provider: 'gemma3'
            });
            setIsPolling(true);
            // Optionally fetch immediate stages to show "waiting"
            const stRes = await axios.get(`${apiBase}/agents/${id}/stages`);
            setStages(stRes.data.stages || {});
        } catch (err: any) {
            alert('Ошибка при запуске генерации: ' + (err.response?.data?.detail || err.message));
        } finally {
            setGeneratingLifecycle(false);
        }
    };

    const getAgentStatus = (agent: any) => {
        if (agent.ci_score === null || agent.ci_score === undefined) return { label: 'ЧЕРНОВИК', class: 'draft-badge', icon: ShieldAlert };
        if (agent.ci_score >= 80) return { label: 'ИДЕАЛЬНЫЙ', class: 'ideal-badge', icon: Star };
        if (agent.ci_score >= 70) return { label: 'СТАБИЛЬНЫЙ', class: 'stable-badge', icon: ShieldCheck };
        return { label: 'ДОРАБОТКА', class: 'bg-amber-500/80 shadow-lg shadow-amber-500/20', icon: Zap };
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-48 space-y-4">
                <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary-500"></div>
                <div className="text-slate-500 font-bold tracking-widest uppercase text-xs">Загрузка цифрового сознания...</div>
            </div>
        );
    }

    if (error || !agent) {
        return (
            <div className="text-center py-20 space-y-4">
                <h2 className="text-2xl font-bold text-red-400">Ошибка загрузки профиля</h2>
                <p className="text-slate-400">{error || 'Агент не найден'}</p>
                <Link to="/" className="inline-flex items-center gap-2 text-primary-400 hover:text-primary-300 transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Вернуться в галерею
                </Link>
            </div>
        );
    }

    const { agent_data: data } = agent;
    const legacy = data?.editor || {};
    const rootDemo = data?.demographics || {};
    const demo = rootDemo?.demographics || rootDemo || legacy;
    const psych = data?.psychology || legacy?.personality || {};
    const voice = data?.voice || legacy?.preferences || {};
    const exp = data?.experience?.length ? data.experience[0] : (data?.experience || legacy?.experience?.[0] || {});
    const soc = data?.sociology || {};
    const fin = data?.financial || {};
    const behavioral = data?.behavioral_main || {};
    const planning = data?.planning || {};
    const metrics = agent.ci_report?.metrics || {};

    const resolvedName = rootDemo?.agent_name || rootDemo?.name || legacy?.name || (agent.name !== "Unknown" ? agent.name : 'Безымянный синтез');
    const resolvedRole = rootDemo?.agent_role || rootDemo?.role || legacy?.role || (agent.role !== "AI Agent" ? agent.role : 'Профессия не указана');
    const displayAge = demo?.age || (legacy?.birth ? (new Date().getFullYear() - parseInt(legacy.birth?.split('-')[0] || "1990")) : undefined);

    const status = getAgentStatus(agent);

    const StatPanel = ({ title, icon: Icon, children, color = "primary" }: any) => {
        const colorClasses: Record<string, string> = {
            primary: "border-primary-500/20 shadow-primary-500/5",
            emerald: "border-emerald-500/20 shadow-emerald-500/5",
            purple: "border-purple-500/20 shadow-purple-500/5",
            blue: "border-blue-500/20 shadow-blue-500/5",
            rose: "border-rose-500/20 shadow-rose-500/5",
            amber: "border-amber-500/20 shadow-amber-500/5",
        };

        const iconColors: Record<string, string> = {
            primary: "text-primary-400",
            emerald: "text-emerald-400",
            purple: "text-purple-400",
            blue: "text-blue-400",
            rose: "text-rose-400",
            amber: "text-amber-400",
        };

        return (
            <motion.div
                whileHover={{ y: -4 }}
                className={`glass-panel rounded-3xl p-6 border ${colorClasses[color]} shadow-xl transition-all duration-300 bg-slate-900/40 backdrop-blur-2xl`}
            >
                <div className="flex items-center gap-3 mb-6">
                    <div className={`p-2.5 rounded-2xl bg-slate-800/50 border border-white/5`}>
                        <Icon className={`w-5 h-5 ${iconColors[color]}`} />
                    </div>
                    <h3 className="font-bold text-lg text-white/90 tracking-tight">{title}</h3>
                </div>
                <div className="space-y-4">
                    {children}
                </div>
            </motion.div>
        );
    };

    const InfoRow = ({ label, value }: { label: string, value: any }) => {
        if (value === undefined || value === null || value === '') return null;
        return (
            <div className="flex flex-col gap-1 group/row">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{label}</span>
                <span className="font-medium text-slate-200 text-sm group-hover/row:text-primary-300 transition-colors">{String(value)}</span>
            </div>
        );
    };

    const LifecycleProgress = () => {
        if (!isPolling && Object.keys(stages).length === 0) return null;
        
        const trackedStages = [
            'planning_strategy', 'planning_routine', 'planning_day', 
            'episodic_memory', 'narrative_memory', 'knowledge_graph'
        ];
        
        const currentStages = trackedStages.filter(s => stages[s]);
        
        // Show progress if polling is active, even if stages are empty (preparing)
        if (currentStages.length === 0 && !isPolling) return null;

        const doneCount = currentStages.filter(s => stages[s] === 'done').length;
        const total = trackedStages.length; // Use fixed 6 stages for correct percentage baseline
        const progress = Math.round((doneCount / total) * 100);

        const getStageLabel = (s: string) => {
            const labels: Record<string, string> = {
                planning_strategy: 'Стратегия планирования',
                planning_routine: 'Распорядок дня',
                planning_day: 'Детализация задач',
                episodic_memory: 'Эпизодическая память',
                narrative_memory: 'Нарратив и цели',
                knowledge_graph: 'Граф знаний'
            };
            return labels[s] || s;
        };

        return (
            <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-panel rounded-3xl p-6 border border-primary-500/30 shadow-2xl shadow-primary-500/10 mb-8 bg-gradient-to-br from-slate-900/60 to-primary-900/20"
            >
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className="bg-primary-500/20 p-2 rounded-xl">
                            <Sparkles className="w-5 h-5 text-primary-400 animate-pulse" />
                        </div>
                        <div>
                            <h3 className="font-bold text-lg text-white">Синтез Жизненного Цикла</h3>
                            <p className="text-xs text-slate-400">Формирование сознания и структуры памяти агента...</p>
                        </div>
                    </div>
                    <div className="text-right">
                        <span className="text-2xl font-black text-primary-400">{progress}%</span>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="h-3 bg-slate-800/50 rounded-full overflow-hidden border border-white/5 mb-6">
                    <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        className="h-full bg-gradient-to-r from-primary-500 to-emerald-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]"
                    />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {trackedStages.map(s => {
                        const status = stages[s] || (isPolling ? 'running' : 'waiting');
                        return (
                            <div key={s} className="flex items-center gap-3 p-3 rounded-2xl bg-slate-800/30 border border-white/5 transition-all">
                                {status === 'done' ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                ) : status === 'running' || status === 'preparing' ? (
                                    <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
                                ) : (
                                    <Activity className="w-4 h-4 text-slate-600" />
                                )}
                                <span className={`text-xs font-medium ${status === 'done' ? 'text-emerald-400' : (status === 'running' ? 'text-primary-300' : 'text-slate-500')}`}>
                                    {getStageLabel(s)}
                                    {status === 'running' && isPolling && Object.keys(stages).length === 0 && " (подбор ключей...)"}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </motion.div>
        );
    };

    const PillList = ({ items }: { items: string[] }) => {
        if (!items || !items.length) return <span className="text-slate-500 italic text-xs">None</span>;
        return (
            <div className="flex flex-wrap gap-2 mt-1">
                {items.map((i, idx) => (
                    <span key={idx} className="bg-white/5 border border-white/10 px-3 py-1 rounded-xl text-slate-300 text-xs font-bold hover:bg-white/10 transition-colors">
                        {i}
                    </span>
                ))}
            </div>
        );
    };

    return (
        <div className="relative min-h-screen">
            {/* Immersive Backdrop */}
            <div className="fixed inset-0 z-[-1] pointer-events-none overflow-hidden">
                {agent.avatar_url && (
                    <div 
                        className="absolute inset-x-0 top-0 h-[80vh] opacity-20 blur-[120px] scale-125"
                        style={{ 
                            backgroundImage: `url(${agent.avatar_url})`,
                            backgroundPosition: 'center',
                            backgroundSize: 'cover'
                        }}
                    />
                )}
                <div className="absolute inset-0 bg-slate-950/40" />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-10"
            >
                {/* Navigation & Global Actions */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
                    <Link to="/" className="group flex items-center gap-3 glass-panel px-4 py-2 rounded-2xl border-white/5 hover:border-primary-500/50 transition-all">
                        <ArrowLeft className="w-4 h-4 text-slate-400 group-hover:text-primary-400" />
                        <span className="text-sm font-bold text-slate-300 group-hover:text-white transition-colors">Вернуться в реестр</span>
                    </Link>

                    <div className="flex flex-wrap gap-3">
                        <Link
                            to={`/agent/${id}/stages`}
                            className="p-2.5 glass-panel rounded-2xl text-slate-400 hover:text-white hover:bg-white/5 border-white/5 transition-all shadow-lg"
                            title="Этапы генерации"
                        >
                            <LayoutList className="w-5 h-5" />
                        </Link>
                        <button className="p-2.5 glass-panel rounded-2xl text-slate-400 hover:text-white hover:bg-white/5 border-white/5 transition-all shadow-lg">
                            <Share2 className="w-5 h-5" />
                        </button>
                        <button
                            onClick={handleDelete}
                            className="p-2.5 glass-panel rounded-2xl text-slate-400 hover:text-red-400 hover:bg-red-500/5 border-white/5 transition-all shadow-lg"
                        >
                            <Trash2 className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                <LifecycleProgress />

                {/* Primary Identity Header */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
                    {/* Basics */}
                    <div className="lg:col-span-12 xl:col-span-5 flex flex-col gap-8 items-center lg:items-start text-center lg:text-left">
                        <div className="space-y-6 flex-1 w-full">
                            <div className="space-y-2">
                                <div className="flex flex-wrap justify-center lg:justify-start items-center gap-3 mb-1">
                                    <div className={`px-3 py-1 rounded-xl flex items-center gap-2 text-white text-[10px] font-black uppercase tracking-widest ${status.class}`}>
                                        <status.icon className="w-3 h-3" />
                                        {status.label}
                                    </div>
                                    <span className="text-slate-500 font-mono text-[10px] tracking-tight">ID: {agent.id.slice(0, 8)}...</span>
                                </div>
                                <h1 className="text-5xl sm:text-7xl font-black text-glow tracking-tight text-white leading-tight">
                                    {resolvedName}
                                </h1>
                                <p className="text-xl font-bold text-primary-400 tracking-wide uppercase italic">
                                    {resolvedRole}
                                </p>
                            </div>

                            <div className="flex flex-wrap justify-center lg:justify-start items-center gap-6 text-slate-300 font-bold">
                                <div className="flex items-center gap-2 glass-panel px-4 py-2 rounded-2xl border-white/5">
                                    <MapPin className="w-4 h-4 text-emerald-400 shadow-glow" />
                                    <span className="text-sm">{demo.location?.city || 'Неизвестно'}, {demo.location?.country || 'Земля'}</span>
                                </div>
                                <div className="flex items-center gap-2 glass-panel px-4 py-2 rounded-2xl border-white/5">
                                    <CalendarClock className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm">{displayAge} лет</span>
                                </div>
                            </div>

                            <div className="flex flex-wrap justify-center lg:justify-start gap-3 pt-2">
                                <Link
                                    to={`/agent/${id}/graph`}
                                    className="px-6 py-3 bg-primary-500 hover:bg-primary-600 text-white rounded-2xl font-black text-xs transition-all shadow-xl shadow-primary-500/20 flex items-center gap-2 group"
                                >
                                    <BrainCircuit className="w-4 h-4 group-hover:rotate-12 transition-transform" />
                                    ПОГРУЖЕНИЕ В ПАМЯТЬ
                                </Link>
                                <Link
                                    to={`/agent/${id}/labs`}
                                    className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-2xl font-black text-xs transition-all flex items-center gap-2 shadow-xl"
                                >
                                    <Beaker className="w-4 h-4 text-purple-400" />
                                    SOUL LABS (QA)
                                </Link>
                            </div>
                        </div>
                    </div>

                    {/* CI Metrics Overdrive */}
                    <div className="lg:col-span-7 h-full">
                        <div className="glass-panel p-8 rounded-[40px] border-white/5 h-full flex flex-col justify-center bg-slate-900/60 backdrop-blur-2xl relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                                <Zap className="w-32 h-32 text-primary-500" />
                            </div>
                            
                            <div className="mb-8">
                                <div className="text-xs font-black text-slate-500 uppercase tracking-[0.3em] mb-2 flex items-center gap-2">
                                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                                    Целостность Цифрового Сознания
                                </div>
                                <div className="flex items-end gap-3">
                                    <div className="text-7xl font-black text-white leading-none">
                                        {agent.ci_score || 0}
                                    </div>
                                    <div className="text-primary-400 font-black text-xl mb-1 uppercase tracking-widest">
                                        очк.
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-6 relative z-10">
                                {[
                                    { label: 'Консистентность', val: metrics.consistency || 0, color: 'from-emerald-500 to-emerald-400' },
                                    { label: 'Глубина Сознания', val: metrics.depth || 0, color: 'from-purple-600 to-purple-400' },
                                    { label: 'Устойчивость (Стресс)', val: metrics.stress_score || 0, color: 'from-blue-600 to-blue-400' }
                                ].map((m, idx) => (
                                    <div key={idx} className="space-y-2">
                                        <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                                            <span className="text-slate-400">{m.label}</span>
                                            <span className="text-white">{m.val}%</span>
                                        </div>
                                        <div className="h-3 bg-white/5 rounded-full overflow-hidden border border-white/5 p-[1px]">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${m.val}%` }}
                                                transition={{ duration: 1, delay: 0.2 + idx * 0.1 }}
                                                className={`h-full bg-gradient-to-r ${m.color} rounded-full`}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Secondary Info / Bio Summary */}
                <div className="glass-panel p-8 rounded-3xl border-white/5 bg-slate-900/40 relative overflow-hidden group">
                    <div className="absolute top-4 right-4 animate-pulse">
                        <MessageCircle className="w-6 h-6 text-primary-500/20" />
                    </div>
                    <div className="text-xs font-black text-primary-500 uppercase tracking-widest mb-4">Автобиографический очерк</div>
                    <p className="text-slate-200 text-xl font-medium leading-relaxed italic line-clamp-4 group-hover:line-clamp-none transition-all duration-700">
                        «{demo.bio_summary || data?.biography?.summary || 'Биография в процессе восстановления...'}»
                    </p>
                </div>

                {/* Detailed Data Matrix */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                    <StatPanel title="Демография" icon={User} color="blue">
                        <InfoRow label="Пол" value={demo?.gender} />
                        <InfoRow label="Этнос" value={demo?.nationality || demo?.ethnicity} />
                        <InfoRow label="Вероисповедание" value={psych?.religion} />
                        <InfoRow label="Образование" value={demo.education?.level} />
                        <InfoRow label="Семейный статус" value={demo.marital_status} />
                    </StatPanel>

                    <StatPanel title="Психо-профиль" icon={BrainCircuit} color="purple">
                        <InfoRow label="Архетип / MBTI" value={psych.personality_type?.code || psych.personality_type || psych.character} />
                        <div className="space-y-2 py-2">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Метрики Большой Пятерки</span>
                            {(psych.personality?.big5 || psych.big5_traits || psych.Big5 || legacy?.personality?.Big5) && (
                                <div className="space-y-2 mt-1">
                                    {Object.entries(psych.personality?.big5 || psych.big5_traits || psych.Big5 || legacy?.personality?.Big5).map(([trait, val]: any) => (
                                        <div key={trait} className="flex flex-col gap-1">
                                            <div className="flex justify-between text-[8px] font-bold uppercase text-slate-400">
                                                <span>{trait === 'Openness' ? 'Открытость' : 
                                                       trait === 'Conscientiousness' ? 'Добросовестность' : 
                                                       trait === 'Extraversion' ? 'Экстраверсия' : 
                                                       trait === 'Agreeableness' ? 'Доброжелательность' : 
                                                       trait === 'Neuroticism' ? 'Нейротизм' : trait}</span>
                                                <span>{Math.round((val > 1 ? val / 100 : val) * 100)}%</span>
                                            </div>
                                            <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                                                <div className="h-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]" style={{ width: `${(val > 1 ? val / 100 : val) * 100}%` }} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </StatPanel>

                    <StatPanel title="Опыт & Навыки" icon={Briefcase} color="emerald">
                        <InfoRow label="Специализация" value={exp?.employment?.current_occupation || exp?.title || legacy?.role} />
                        <InfoRow label="Стаж" value={exp?.employment?.years_experience ? `${exp.employment.years_experience} лет` : null} />
                        <div>
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Матрица навыков</span>
                            <PillList items={exp?.capabilities?.hard_skills || exp?.skills || legacy?.skills || []} />
                        </div>
                    </StatPanel>

                    <StatPanel title="Гардероб & Стиль" icon={Zap} color="amber">
                        <InfoRow label="Манера речи" value={soc?.communication?.communication_style || voice?.vocabulary || legacy?.preferences?.communication_style} />
                        <InfoRow label="Громкость голоса" value={voice?.volume || 'Средняя'} />
                        <div className="py-1">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Гайд по стилю</span>
                            <ul className="space-y-1.5">
                                {voice.style_guide?.slice(0, 3).map((sg: string, i: number) => (
                                    <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                                        <div className="w-1 h-1 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                                        {sg}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </StatPanel>

                    <StatPanel title="Поведенческая Матрица" icon={Zap} color="rose">
                        <InfoRow label="Когнитивные искажения" value={behavioral.cognitive_biases?.[0]} />
                        <InfoRow label="Эмоциональные привычки" value={behavioral.emotional_habits?.[0]} />
                        <div className="py-1">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Реакции на стресс</span>
                            <ul className="space-y-1.5">
                                {behavioral.stress_reactions?.slice(0, 3).map((sr: string, i: number) => (
                                    <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                                        <div className="w-1 h-1 rounded-full bg-rose-500 mt-1.5 shrink-0" />
                                        {sr}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </StatPanel>

                    <StatPanel title="Рутины & Планирование" icon={CalendarClock} color="blue">
                        <InfoRow label="Стратегический приоритет" value={planning.strategic_priorities?.[0]} />
                        <div className="py-1">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Ежедневный распорядок</span>
                            <ul className="space-y-1.5">
                                {planning.routines?.slice(0, 3).map((r: string, i: number) => (
                                    <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                                        <div className="w-1 h-1 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                                        {r}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </StatPanel>

                    <StatPanel title="Социальный Капитал" icon={Users} color="rose">
                        <InfoRow label="Взгляды" value={soc.social_and_relationships?.political_views?.description} />
                        <InfoRow label="Репутация" value={soc.communication?.online_presence?.reputation} />
                        <div className="grid grid-cols-2 gap-3 mt-2">
                            <div className="bg-white/5 p-3 rounded-2xl border border-white/5 text-center">
                                <div className="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-0.5">Друзья</div>
                                <div className="text-xl font-black text-white">{soc.social_and_relationships?.social_circle_size?.best_friends || 0}</div>
                            </div>
                            <div className="bg-white/5 p-3 rounded-2xl border border-white/5 text-center">
                                <div className="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-0.5">Враги</div>
                                <div className="text-xl font-black text-rose-500">{soc.social_and_relationships?.social_circle_size?.enemies || 0}</div>
                            </div>
                        </div>
                    </StatPanel>

                    <StatPanel title="Финансовый Баланс" icon={Wallet} color="primary">
                        <div className="flex justify-between items-end p-4 bg-primary-500/10 rounded-2xl border border-primary-500/20 mb-4">
                            <div>
                                <div className="text-[8px] font-black uppercase text-primary-400 tracking-widest mb-1">Ежемесячный доход</div>
                                <div className="text-2xl font-black text-white">{fin.income?.income_monthly || 0} <span className="text-xs font-bold text-primary-400">{fin.income?.currency || 'USD'}</span></div>
                            </div>
                            <Wallet className="w-8 h-8 text-primary-500/30" />
                        </div>
                        <InfoRow label="Крупный Актив" value={fin.property?.[0]?.item} />
                        <InfoRow label="Долги / Обязательства" value={fin.debts?.[0]?.debt_type} />
                    </StatPanel>
                </div>

                {/* Knowledge Graph Immersive */}
                <div className="pt-10 space-y-6">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-primary-500/10 rounded-2xl border border-primary-500/20">
                            <BrainCircuit className="w-6 h-6 text-primary-400 animate-pulse" />
                        </div>
                        <div>
                            <h2 className="text-3xl font-black text-white">Внутренняя Архитектура</h2>
                            <p className="text-slate-500 font-bold text-sm tracking-widest uppercase">Визуализатор Графа Знаний v2.0</p>
                        </div>
                    </div>
                    <div className="glass-panel p-2 rounded-[40px] border-white/5 bg-slate-900/40 relative overflow-hidden shadow-2xl">
                        <AgentGraphView agentId={agent.id} />
                        <div className="absolute bottom-10 right-10 z-20">
                            <Link 
                                to={`/agent/${id}/graph`}
                                className="px-6 py-3 glass-panel rounded-2xl border-white/10 hover:border-primary-500 text-xs font-black transition-all hover:bg-primary-500/10 flex items-center gap-2 group"
                            >
                                <LayoutList className="w-4 h-4 group-hover:scale-110 transition-transform" />
                                ПОЛНОЭКРАННЫЙ РЕЖИМ
                            </Link>
                        </div>
                    </div>
                </div>

                {/* Footer Actions */}
                <div className="flex justify-center pt-10">
                    <button
                        onClick={handleGenerateLifecycle}
                        disabled={generatingLifecycle || isPolling}
                        className="group relative flex items-center gap-4 glass-panel px-10 py-5 rounded-[30px] border-white/10 hover:border-blue-500/50 disabled:opacity-80 disabled:hover:border-white/10 transition-all overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent group-hover:opacity-100 transition-opacity" />
                        <CalendarClock className={`w-8 h-8 ${generatingLifecycle || isPolling ? 'animate-spin text-primary-400' : 'group-hover:rotate-12 text-blue-400'} transition-all`} />
                        <div className="text-left relative z-10">
                            <div className="text-xs font-black text-blue-400 uppercase tracking-widest mb-0.5">Life Cycle Synthesis</div>
                            <div className="text-xl font-black text-white">
                                {generatingLifecycle ? 'ИНИЦИАЛИЗАЦИЯ...' : isPolling ? 'СИНТЕЗ В ПРОЦЕССЕ...' : 'СГЕНЕРИРОВАТЬ ЦИКЛ ЖИЗНИ'}
                            </div>
                        </div>
                        <ArrowLeft className={`w-5 h-5 rotate-180 text-slate-500 ${!isPolling && !generatingLifecycle ? 'group-hover:translate-x-2' : ''} transition-transform`} />
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
