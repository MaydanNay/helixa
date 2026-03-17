
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Users, Sparkles, CheckCircle, Loader2, XCircle,
    MapPin, BrainCircuit, Globe, Zap, LayoutGrid,
    ChevronRight, ShieldCheck
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

const API = '/api/v1';
const POLL_MIN_MS = 3000;
const POLL_MAX_MS = 20000;

type JobStatus = 'queued' | 'in_progress' | 'complete' | 'error' | 'not_found';

interface JobCard {
    job_id: string;
    agent_id?: string;
    index: number;
    status: JobStatus;
    name?: string;
    role?: string;
    completed_stages: number;
}

const STATUS_ICON: Record<JobStatus, React.ReactElement> = {
    queued: <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />,
    in_progress: <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />,
    complete: <CheckCircle className="w-5 h-5 text-emerald-400" />,
    error: <XCircle className="w-5 h-5 text-red-400" />,
    not_found: <XCircle className="w-5 h-5 text-red-400" />,
};

export default function BatchCreate() {
    const navigate = useNavigate();
    const [theme, setTheme] = useState('');
    const [count, setCount] = useState(5);
    const [personalityHint, setPersonalityHint] = useState('');
    const [visualDna, setVisualDna] = useState('');
    const [countryHint, setCountryHint] = useState('');
    const [cityHint, setCityHint] = useState('');
    const [generationMode, setGenerationMode] = useState('staged');
    const [launching, setLaunching] = useState(false);
    const [launched, setLaunched] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [jobs, setJobs] = useState<JobCard[]>([]);
    
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollIntervalRef = useRef<number>(POLL_MIN_MS);
    const prevPendingCountRef = useRef<number>(-1);
    const jobsRef = useRef<JobCard[]>([]);
    jobsRef.current = jobs;

    const allDone = jobs.length > 0 && jobs.every((j: JobCard) => j.status === 'complete' || j.status === 'error' || j.status === 'not_found');

    useEffect(() => {
        if (!launched) return;

        const poll = async () => {
            const pending = jobsRef.current.filter((j: JobCard) => j.status === 'queued' || j.status === 'in_progress');
            if (pending.length === 0) return;

            const updates = [];
            for (const j of pending) {
                try {
                    const res = await axios.get(`${API}/jobs/${j.job_id}`);
                    const d = res.data;
                    const status: JobStatus = d.status === 'complete' ? 'complete'
                        : d.status === 'in_progress' ? 'in_progress'
                        : d.status === 'not_found' ? 'not_found'
                        : d.status === 'failed' ? 'error'
                        : 'queued';
                    
                    let completed_stages = j.completed_stages;
                    let jobName = j.name;
                    let jobRole = j.role;

                    if (generationMode === 'staged' && j.agent_id && (status === 'in_progress' || status === 'queued')) {
                        try {
                            const stageRes = await axios.get(`${API}/agents/${j.agent_id}/stages`);
                            const stagesObj = stageRes.data.stages || {};
                            const completedCount = Object.values(stagesObj).filter(v => v === 'ok' || v === 'true').length;
                            completed_stages = completedCount;
                            if (stageRes.data.name && stageRes.data.name !== 'Generating…') jobName = stageRes.data.name;
                            if (stageRes.data.role && stageRes.data.role !== 'Staged Generation') jobRole = stageRes.data.role;
                        } catch (e) {}
                    }

                    if (status === 'complete') completed_stages = 13;

                    updates.push({
                        job_id: j.job_id,
                        status,
                        name: d.result?.name || d.result?.agent_name || jobName,
                        role: d.result?.role || d.result?.agent_role || jobRole,
                        completed_stages,
                    });
                } catch {
                    updates.push({ job_id: j.job_id, status: 'error' as JobStatus, completed_stages: j.completed_stages });
                }
            }

            const completedNow = updates.filter((u: any) => u.status === 'complete' || u.status === 'error').length;
            if (completedNow !== prevPendingCountRef.current) {
                pollIntervalRef.current = POLL_MIN_MS;
                prevPendingCountRef.current = completedNow;
            } else {
                pollIntervalRef.current = Math.min(pollIntervalRef.current * 1.5, POLL_MAX_MS);
            }

            setJobs((prev: JobCard[]) => prev.map((j: JobCard) => {
                const u = updates.find((upd: any) => upd.job_id === j.job_id);
                return u ? { ...j, ...u } as JobCard : j;
            }));

            timeoutRef.current = setTimeout(poll, pollIntervalRef.current);
        };

        timeoutRef.current = setTimeout(poll, POLL_MIN_MS);
        return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
    }, [launched, generationMode]);

    const handleLaunch = async () => {
        setLaunching(true);
        setError(null);
        try {
            const res = await axios.post(`${API}/generate/batch-soul`, {
                count,
                theme: theme || undefined,
                personality_hint: personalityHint || undefined,
                visual_dna: visualDna || undefined,
                country_hint: countryHint || undefined,
                city_hint: cityHint || undefined,
                mode: generationMode,
            });
            const cards: JobCard[] = (res.data.jobs as { job_id: string, agent_id: string }[]).map((job: any, i: number) => ({
                job_id: job.job_id,
                agent_id: job.agent_id,
                index: i + 1,
                status: 'queued' as JobStatus,
                completed_stages: 0,
            }));
            setJobs(cards);
            setLaunched(true);
        } catch (e: any) {
            setError(e?.response?.data?.detail || e.message);
        } finally {
            setLaunching(false);
        }
    };

    const completedCount = jobs.filter(j => j.status === 'complete').length;
    const TOTAL_STAGES_PER_AGENT = 13;
    const totalPossibleStages = jobs.length * TOTAL_STAGES_PER_AGENT;
    let totalCompletedStages = 0;
    jobs.forEach(j => {
        totalCompletedStages += j.completed_stages;
    });

    const progressPct = jobs.length > 0 ? (generationMode === 'staged'
        ? Math.round((totalCompletedStages / totalPossibleStages) * 100)
        : Math.round((completedCount / jobs.length) * 100)) : 0;

    return (
        <div className="relative min-h-screen">
            {/* Background Lab matrix effect */}
            <div className="fixed inset-0 z-[-1] pointer-events-none opacity-20">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(168,85,247,0.15),transparent_70%)]" />
                <div className="absolute inset-0 bg-slate-950" />
            </div>

            <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="max-w-6xl mx-auto px-4 py-10 space-y-12"
            >
                {/* Header Section */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 border-b border-white/5 pb-10">
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-purple-500/10 rounded-2xl border border-purple-500/20 shadow-glow shadow-purple-500/10">
                                <Users className="w-8 h-8 text-purple-400" />
                            </div>
                            <div>
                                <h1 className="text-4xl sm:text-5xl font-black text-white tracking-tight">
                                    Фабрика <span className="text-purple-500">Душ</span>
                                </h1>
                                <p className="text-slate-500 font-bold uppercase tracking-[0.2em] text-[10px] mt-1">Протокол Мульти-Агентного Синтеза</p>
                            </div>
                        </div>
                    </div>
                    
                    {!launched && (
                        <Link to="/" className="group flex items-center gap-2 glass-panel px-4 py-2 rounded-xl text-slate-400 hover:text-white border-white/5 hover:border-primary-500/50 transition-all font-bold text-xs uppercase tracking-widest">
                            ← В Реестр
                        </Link>
                    )}
                </div>

                {!launched ? (
                    <div className="grid grid-cols-1 xl:grid-cols-12 gap-10">
                        {/* Config Form */}
                        <motion.div 
                            initial={{ x: -20, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            className="xl:col-span-8 space-y-8"
                        >
                            {error && (
                                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-2xl text-red-200 text-sm flex items-center gap-3 animate-pulse">
                                    <XCircle className="w-5 h-5 text-red-400 shadow-glow" />
                                    <span className="font-bold tracking-tight">{error}</span>
                                </div>
                            )}

                            {/* Phase 1: Identity & Context */}
                            <div className="glass-panel p-8 rounded-[32px] border-white/5 bg-slate-900/40 space-y-6">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/20 flex items-center justify-center text-xs font-black text-purple-400">01</div>
                                    <h3 className="text-xl font-black text-white/90 uppercase tracking-widest">Идентичность Группы</h3>
                                </div>
                                
                                <div className="space-y-2 group">
                                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 transition-colors group-focus-within:text-purple-400 flex items-center gap-2">
                                        <Globe className="w-3 h-3" /> Основная тема / Контекст
                                    </label>
                                    <input
                                        type="text"
                                        value={theme}
                                        onChange={e => setTheme(e.target.value)}
                                        className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 transition-all font-medium text-white placeholder-slate-600 shadow-inner"
                                        placeholder="Киберпанк-наемники, научные исследователи..."
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-2 group">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 transition-colors group-focus-within:text-emerald-400 flex items-center gap-2">
                                            <BrainCircuit className="w-3 h-3" /> Черты личности
                                        </label>
                                        <textarea
                                            value={personalityHint}
                                            onChange={e => setPersonalityHint(e.target.value)}
                                            rows={3}
                                            className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all font-medium text-white placeholder-slate-600 resize-none shadow-inner"
                                            placeholder="Разнообразный микс архетипов..."
                                        />
                                    </div>
                                    <div className="space-y-2 group">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 transition-colors group-focus-within:text-blue-400 flex items-center gap-2">
                                            <Sparkles className="w-3 h-3" /> Визуальная ДНК
                                        </label>
                                        <textarea
                                            value={visualDna}
                                            onChange={e => setVisualDna(e.target.value)}
                                            rows={3}
                                            className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all font-medium text-white placeholder-slate-600 resize-none shadow-inner"
                                            placeholder="Неоновые акценты, обтекаемая броня..."
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-2 group">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 transition-colors group-focus-within:text-slate-300 flex items-center gap-2">
                                            <MapPin className="w-3 h-3" /> Регион / Страна
                                        </label>
                                        <input
                                            type="text"
                                            value={countryHint}
                                            onChange={e => setCountryHint(e.target.value)}
                                            className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-white/20 transition-all font-medium text-white placeholder-slate-700"
                                            placeholder="Япония, колония на Марсе..."
                                        />
                                    </div>
                                    <div className="space-y-2 group">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1 transition-colors group-focus-within:text-slate-300 flex items-center gap-2">
                                            <LayoutGrid className="w-3 h-3" /> Город / Локация
                                        </label>
                                        <input
                                            type="text"
                                            value={cityHint}
                                            onChange={e => setCityHint(e.target.value)}
                                            className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-white/20 transition-all font-medium text-white placeholder-slate-700"
                                            placeholder="Нео-Токио, Сектор 7..."
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Phase 2: Engine Config */}
                            <div className="glass-panel p-8 rounded-[32px] border-white/5 bg-slate-900/40 space-y-6">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className="w-8 h-8 rounded-full bg-blue-500/20 border border-blue-500/20 flex items-center justify-center text-xs font-black text-blue-400">02</div>
                                    <h3 className="text-xl font-black text-white/90 uppercase tracking-widest">Ядро Синтеза</h3>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Тип Протокола</label>
                                        <select
                                            value={generationMode}
                                            onChange={e => setGenerationMode(e.target.value)}
                                            className="w-full bg-slate-900/60 border border-white/5 rounded-2xl px-5 py-4 focus:outline-none focus:border-blue-500/50 transition-all font-bold text-slate-200 appearance-none cursor-pointer"
                                        >
                                            <option value="staged">Полное Погружение (13 этапов)</option>
                                            <option value="fast">Быстрый Прототип (1 этап)</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Sidebar: Summary & Launch */}
                        <div className="xl:col-span-4 space-y-6">
                            <div className="glass-panel p-8 rounded-[40px] border-white/5 bg-slate-900/60 backdrop-blur-3xl sticky top-24 space-y-8 shadow-2xl overflow-hidden group">
                                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                                    <Zap className="w-32 h-32 text-purple-500" />
                                </div>

                                <div className="space-y-2">
                                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] flex justify-between">
                                        <span>Количество Юнитов</span>
                                        <span className="text-purple-400 text-lg">{count}</span>
                                    </label>
                                    <input
                                        type="range"
                                        min={1} max={50} step={1}
                                        value={count}
                                        onChange={e => setCount(Number(e.target.value))}
                                        className="w-full accent-purple-500 h-1.5 cursor-pointer bg-white/5 rounded-full"
                                    />
                                    <div className="flex justify-between text-[10px] font-black text-slate-700 tracking-widest">
                                        <span>01</span><span>25</span><span>50</span>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest pb-2 border-b border-white/5">Обзор Протокола Группы</div>
                                    <div className="space-y-4">
                                        {[
                                            { label: 'Всего операций', value: count * (generationMode === 'staged' ? 13 : 1), color: 'text-purple-400' },
                                            { label: 'Ожидаемое время', value: generationMode === 'staged' ? `${Math.ceil(count * 0.8)} мин` : '< 1 мин', color: 'text-slate-300' },
                                            { label: 'Глубина интеллекта', value: generationMode === 'staged' ? 'Максимум' : 'Черновик', color: 'text-emerald-400' }
                                        ].map((stat, i) => (
                                            <div key={i} className="flex justify-between items-center">
                                                <span className="text-xs font-bold text-slate-400">{stat.label}</span>
                                                <span className={`text-xs font-black ${stat.color}`}>{stat.value}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <button
                                    onClick={handleLaunch}
                                    disabled={launching}
                                    className="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-5 rounded-[24px] flex items-center justify-center gap-3 transition-all transform active:scale-95 shadow-xl shadow-purple-500/20 disabled:opacity-50 group/btn overflow-hidden relative"
                                >
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover/btn:translate-x-full duration-1000 transition-transform" />
                                    {launching ? (
                                        <Loader2 className="w-6 h-6 animate-spin" />
                                    ) : (
                                        <>
                                            <Sparkles className="w-5 h-5 text-white shadow-glow" />
                                            <span className="tracking-widest uppercase text-sm">Запустить Протокол Синтеза</span>
                                        </>
                                    )}
                                </button>
                                
                                <p className="text-[10px] text-center text-slate-600 font-bold leading-relaxed px-4">
                                    Запуск этого протокола выделит ресурсы кластера для синтеза {count} уникальных цифровых личностей.
                                </p>
                            </div>
                        </div>
                    </div>
                ) : (
                    /* Dashboard Mode */
                    <motion.div
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="space-y-12"
                    >
                        {/* Global Progress Dashboard */}
                        <div className="glass-panel p-10 rounded-[48px] border-white/5 shadow-2xl relative overflow-hidden bg-slate-900/60 backdrop-blur-3xl">
                             <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-10 mb-12">
                                <div className="space-y-4">
                                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-[0.4em] mb-2 flex items-center gap-2">
                                        <Loader2 className={`w-4 h-4 ${allDone ? 'text-emerald-500' : 'animate-spin text-purple-500'}`} />
                                        Статус группы: {allDone ? 'Завершено' : 'В Процессе'}
                                    </div>
                                    <div className="flex items-end gap-3 leading-none">
                                        <div className="text-8xl font-black text-white">{progressPct}</div>
                                        <div className="text-purple-500 font-black text-3xl mb-2">%</div>
                                    </div>
                                </div>

                                <div className="flex-1 max-w-lg w-full space-y-6">
                                    <div className="flex justify-between text-xs font-black uppercase tracking-widest">
                                        <span className="text-slate-400">Операций Завершено</span>
                                        <span className="text-white">{completedCount} / {jobs.length} Агентов</span>
                                    </div>
                                    <div className="h-4 bg-white/5 rounded-full overflow-hidden border border-white/10 p-[2px]">
                                        <motion.div
                                            className="h-full bg-gradient-to-r from-purple-600 via-primary-500 to-emerald-400 rounded-full shadow-[0_0_15px_rgba(168,85,247,0.4)]"
                                            initial={{ width: 0 }}
                                            animate={{ width: `${progressPct}%` }}
                                            transition={{ duration: 0.8 }}
                                        />
                                    </div>
                                    {generationMode === 'staged' && (
                                        <div className="text-[9px] font-bold text-slate-600 uppercase tracking-[0.2em] text-right">
                                            Синтезировано {totalCompletedStages} из {totalPossibleStages} нейронных этапов
                                        </div>
                                    )}
                                </div>
                             </div>

                             {allDone && (
                                <motion.div 
                                    initial={{ y: 20, opacity: 0 }}
                                    animate={{ y: 0, opacity: 1 }}
                                    className="flex flex-col sm:flex-row gap-4 pt-6 mt-10 border-t border-white/5"
                                >
                                    <button
                                        onClick={() => navigate('/')}
                                        className="flex-1 flex items-center justify-center gap-3 bg-emerald-600 hover:bg-emerald-500 text-white font-black py-5 rounded-[24px] shadow-xl shadow-emerald-600/20 group"
                                    >
                                        <ShieldCheck className="w-5 h-5 group-hover:scale-110 transition-transform" />
                                        <span className="tracking-widest uppercase text-sm">Открыть Реестр</span>
                                    </button>
                                    <button
                                        onClick={() => { setLaunched(false); setJobs([]); }}
                                        className="px-10 py-5 glass-panel rounded-[24px] text-slate-400 hover:text-white border-white/10 hover:border-white/20 font-black transition-all uppercase tracking-widest text-sm"
                                    >
                                        Новая Группа
                                    </button>
                                </motion.div>
                             )}
                        </div>

                        {/* Agents Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                            <AnimatePresence mode="popLayout">
                                {jobs.map((job, i) => (
                                    <motion.div
                                        key={job.job_id}
                                        layout
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ duration: 0.4, delay: i * 0.02 }}
                                        className={`glass-panel rounded-3xl p-6 border group transition-all duration-500 hover:shadow-2xl ${
                                            job.status === 'complete' ? 'border-emerald-500/20 bg-emerald-500/5' :
                                            job.status === 'error' ? 'border-red-500/20 bg-red-500/5' :
                                            'border-white/5 bg-slate-900/40'
                                        }`}
                                    >
                                        <div className="flex items-center justify-between mb-5">
                                            <div className="w-10 h-10 rounded-2xl bg-slate-800/80 border border-white/5 flex items-center justify-center text-[10px] font-black text-slate-500">
                                                {String(job.index).padStart(2, '0')}
                                            </div>
                                            <div className={`${job.status === 'in_progress' ? 'filter drop-shadow-[0_0_8px_rgba(14,165,233,0.5)]' : ''}`}>
                                                {STATUS_ICON[job.status]}
                                            </div>
                                        </div>

                                        <div className="space-y-1 mb-6">
                                            <h4 className="font-black text-lg text-white group-hover:text-primary-400 transition-colors truncate">
                                                {job.name || `Юнит ${job.index}`}
                                            </h4>
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest truncate">
                                                {job.role || 'Выделение нейронного пространства...'}
                                            </p>
                                        </div>

                                        <div className="space-y-3">
                                            <div className="flex justify-between items-center text-[9px] font-black uppercase tracking-widest">
                                                <span className={`${
                                                    job.status === 'complete' ? 'text-emerald-500' :
                                                    job.status === 'error' ? 'text-red-500' :
                                                    'text-slate-500'
                                                }`}>
                                                    {job.status === 'complete' ? 'Синтез Завершен' : 
                                                     job.status === 'in_progress' ? 'Mapping Нейронов' : 
                                                     job.status === 'queued' ? 'В Ожидании' : 'Сбой Системы'}
                                                </span>
                                                {generationMode === 'staged' && (
                                                    <span className="text-white">{job.completed_stages}/13</span>
                                                )}
                                            </div>

                                            {generationMode === 'staged' && (
                                                <div className="relative">
                                                     <div className="h-1.5 bg-white/5 rounded-full overflow-hidden p-[1px]">
                                                        <motion.div
                                                            className={`h-full rounded-full ${
                                                                job.status === 'complete' ? 'bg-emerald-500' :
                                                                job.status === 'error' ? 'bg-red-500' :
                                                                'bg-primary-500'
                                                            }`}
                                                            initial={{ width: 0 }}
                                                            animate={{ width: `${Math.round((job.completed_stages / 13) * 100)}%` }}
                                                            transition={{ duration: 0.5 }}
                                                        />
                                                    </div>
                                                    
                                                    {/* Stage Pips */}
                                                    <div className="flex justify-between mt-2 px-0.5">
                                                        {Array.from({ length: 13 }).map((_, stepIdx) => (
                                                            <div 
                                                                key={stepIdx} 
                                                                className={`w-1 h-1 rounded-full transition-all duration-500 ${
                                                                    stepIdx < job.completed_stages 
                                                                        ? (job.status === 'complete' ? 'bg-emerald-500' : 'bg-primary-400 shadow-[0_0_5px_rgba(14,165,233,0.8)]') 
                                                                        : 'bg-white/5'
                                                                }`}
                                                            />
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        {job.status === 'complete' && job.agent_id && (
                                            <Link 
                                                to={`/agent/${job.agent_id}`}
                                                className="mt-6 flex items-center justify-center gap-2 py-3 bg-white/5 hover:bg-white/10 rounded-2xl text-[10px] font-black text-slate-400 hover:text-white transition-all border border-white/5"
                                            >
                                                ПРОСМОТР СОЗНАНИЯ <ChevronRight className="w-3 h-3" />
                                            </Link>
                                        )}
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                )}
            </motion.div>
        </div>
    );
}
