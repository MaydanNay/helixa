import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    ArrowLeft, Beaker, Play, ShieldCheck,
    Terminal, User, BarChart3, Fingerprint, Layers,
    Zap, Activity, Database
} from 'lucide-react';

type Module = 'audit' | 'knowledge' | 'stress' | 'evolve' | 'turing';

interface TuringSession {
    agent_id: string;
    is_soul_a: boolean;
    history: { role: string; content: string; entity?: string }[];
}

interface EvolutionResult {
    status: string;
    summary: string;
    updates: {
        psychology: any;
        bio: any;
    };
}

interface AuditReport {
    score: number;
    metrics: {
        consistency: number;
        depth: number;
        style: number;
    };
    glitches: string[];
    summary: string;
}

interface AuditResult {
    agent_id: string;
    transcript: { role: string; content: string }[];
    report: AuditReport;
}

interface KnowledgeExamResult {
    score: number;
    summary: string;
    results: {
        fact: string;
        question: string;
        answer: string;
        accuracy: number;
        reason: string;
    }[];
}

interface StressTestResult {
    agent_id: string;
    pain_point: string;
    transcript: { role: string; content: string }[];
    report: {
        resilience_score: number;
        emotional_depth: number;
        vulnerability_analysis: string;
        summary: string;
    };
}

export default function SoulLabs() {
    const { id } = useParams();
    const [isRunning, setIsRunning] = useState(false);
    const [activeModule, setActiveModule] = useState<Module>('audit');
    const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
    const [knowledgeResult, setKnowledgeResult] = useState<KnowledgeExamResult | null>(null);
    const [stressResult, setStressResult] = useState<StressTestResult | null>(null);
    const [evolutionResult, setEvolutionResult] = useState<EvolutionResult | null>(null);
    const [turingSession, setTuringSession] = useState<TuringSession | null>(null);
    const [turingInput, setTuringInput] = useState('');
    const [turingIsLoading, setTuringIsLoading] = useState(false);
    const [agentInfo, setAgentInfo] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<'details' | 'process'>('details');

    const apiBase = '/api/v1';

    useEffect(() => {
        axios.get(`${apiBase}/agents/${id}`)
            .then(res => {
                const data = res.data;
                setAgentInfo(data);
                
                // If we have a stored CI report, pre-fill the states
                if (data.ci_report) {
                    if (data.ci_report.audit) setAuditResult(data.ci_report.audit);
                    if (data.ci_report.exam) setKnowledgeResult(data.ci_report.exam);
                    if (data.ci_report.stress) setStressResult(data.ci_report.stress);
                }
            })
            .catch(err => console.error(err));
    }, [id]);

    const runModule = async () => {
        setIsRunning(true);
        // Reset only current selected results
        if (activeModule === 'audit') setAuditResult(null);
        if (activeModule === 'knowledge') setKnowledgeResult(null);
        if (activeModule === 'stress') setStressResult(null);
        if (activeModule === 'evolve') setEvolutionResult(null);
        if (activeModule !== 'turing') setTuringSession(null);

        try {
            if (activeModule === 'turing') {
                const res = await axios.post(`${apiBase}/agents/${id}/labs/turing/init`);
                setTuringSession(res.data);
                setActiveTab('details');
                return;
            }

            const endpoint = activeModule === 'audit' 
                ? `${apiBase}/agents/${id}/audit`
                : activeModule === 'knowledge'
                ? `${apiBase}/agents/${id}/labs/knowledge-exam`
                : activeModule === 'stress'
                ? `${apiBase}/agents/${id}/labs/stress-test`
                : `${apiBase}/agents/${id}/labs/evolve`;

            const res = await axios.post(endpoint);
            
            if (activeModule === 'audit') setAuditResult(res.data);
            if (activeModule === 'knowledge') setKnowledgeResult(res.data);
            if (activeModule === 'stress') setStressResult(res.data);
            if (activeModule === 'evolve') setEvolutionResult(res.data);
            
            setActiveTab('details');
        } catch (err: any) {
            alert('Ошибка верификации: ' + (err.response?.data?.detail || err.message));
        } finally {
            setIsRunning(false);
        }
    };

    const sendTuringMessage = async () => {
        if (!turingInput.trim() || !turingSession) return;
        setTuringIsLoading(true);
        const userMsg = turingInput;
        setTuringInput('');

        try {
            // Get responses from both entities sequentially (or parallel)
            const [resA, resB] = await Promise.all([
                axios.post(`${apiBase}/agents/${id}/labs/turing/chat`, {
                    agent_id: id,
                    entity: 'A',
                    message: userMsg,
                    is_soul_a: turingSession.is_soul_a,
                    history: turingSession.history
                }),
                axios.post(`${apiBase}/agents/${id}/labs/turing/chat`, {
                    agent_id: id,
                    entity: 'B',
                    message: userMsg,
                    is_soul_a: turingSession.is_soul_a,
                    history: turingSession.history
                })
            ]);

            setTuringSession(prev => {
                if (!prev) return prev;
                return {
                    ...prev,
                    history: [
                        ...prev.history,
                        { role: 'user', content: userMsg },
                        { role: 'agent', entity: 'A', content: resA.data.content },
                        { role: 'agent', entity: 'B', content: resB.data.content }
                    ]
                };
            });
        } catch (err) {
            console.error(err);
        } finally {
            setTuringIsLoading(false);
        }
    };

    const handleTuringGuess = (guessA: boolean) => {
        const isCorrect = guessA === turingSession?.is_soul_a;
        alert(isCorrect ? 'ВЕРНО! Вы узнали настоящую Душу.' : 'ОШИБКА. Алгоритм оказался убедительнее.');
        setTuringSession(null);
        setActiveModule('audit');
    };

    const modules = [
        { id: 'audit', name: 'Психо-Аудит', icon: ShieldCheck, color: 'indigo', desc: 'Проверка консистентности личности через интервью.' },
        { id: 'knowledge', name: 'Экзамен Знаний', icon: Database, color: 'emerald', desc: 'Проверка фактической памяти по графу Neo4j.' },
        { id: 'stress', name: 'Стресс-Тест', icon: Activity, color: 'rose', desc: 'Проверка устойчивости персонажа под давлением.' },
        { id: 'evolve', name: 'Состояние Сна', icon: Zap, color: 'amber', desc: 'Консолидация памяти и эволюция личности.' },
        { id: 'turing', name: 'Слепая Оценка', icon: Fingerprint, color: 'purple', desc: 'Тест Тьюринга: отличите Душу от алгоритма.' },
    ];

    const currentResult = activeModule === 'audit' ? auditResult : activeModule === 'knowledge' ? knowledgeResult : activeModule === 'stress' ? stressResult : evolutionResult;

    return (
        <div className="max-w-6xl mx-auto space-y-6 pb-20">
            {/* Lab Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-slate-900/40 p-6 rounded-3xl border border-indigo-500/20 backdrop-blur-md gap-4">
                <div className="flex items-center gap-4">
                    <Link to={`/agent/${id}`} className="p-2 hover:bg-white/5 rounded-xl transition-colors">
                        <ArrowLeft className="w-5 h-5 text-slate-400" />
                    </Link>
                    <div className="flex items-center gap-3">
                        <div className="bg-indigo-500/20 p-3 rounded-2xl border border-indigo-500/30">
                            <Beaker className="w-8 h-8 text-indigo-400" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                                Soul Labs <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">v2.0</span>
                            </h1>
                            <p className="text-sm text-slate-400">Комплексная верификация ИИ-сущностей</p>
                        </div>
                    </div>
                </div>
                
                <button
                    onClick={runModule}
                    disabled={isRunning}
                    className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white px-8 py-4 rounded-2xl transition-all shadow-xl shadow-indigo-900/30 font-bold group w-full md:w-auto justify-center"
                >
                    {isRunning ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Процесс сканирования...
                        </>
                    ) : (
                        <>
                            <Play className="w-4 h-4 group-hover:scale-125 transition-transform" />
                            Запустить: {modules.find(m => m.id === activeModule)?.name}
                        </>
                    )}
                </button>

                {agentInfo?.ci_score !== null && agentInfo?.ci_score !== undefined && (
                    <div className="flex items-center gap-4 bg-white/5 px-6 py-3 rounded-2xl border border-white/5">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Общий Счет CI</span>
                            <div className="flex items-center gap-2">
                                <span className={`text-2xl font-black ${agentInfo.ci_passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {agentInfo.ci_score}
                                </span>
                                <span className={`text-[10px] px-2 py-0.5 rounded border uppercase font-bold ${
                                    agentInfo.ci_passed ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' : 'bg-rose-500/10 border-rose-500/20 text-rose-500'
                                }`}>
                                    {agentInfo.ci_passed ? 'Пройден' : 'Сбой'}
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Panel: Module Selection & Specs */}
                <div className="lg:col-span-1 space-y-6">
                    {/* Module Selector */}
                    <div className="glass-panel p-4 rounded-3xl border border-white/5 space-y-2">
                        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-2 mb-2">Выбор модуля</h3>
                        {modules.map(mod => (
                            <button
                                key={mod.id}
                                onClick={() => setActiveModule(mod.id as Module)}
                                disabled={isRunning}
                                className={`w-full flex items-center gap-4 p-4 rounded-2xl border transition-all text-left group ${activeModule === mod.id ? 'bg-indigo-500/10 border-indigo-500/30 ring-1 ring-indigo-500/20' : 'bg-transparent border-transparent hover:bg-white/5 text-slate-400'}`}
                            >
                                <div className={`p-2 rounded-xl border ${activeModule === mod.id ? 'bg-indigo-500/20 border-indigo-500/30 text-indigo-400' : 'bg-slate-800 border-white/5 text-slate-500 group-hover:text-slate-300'}`}>
                                    <mod.icon className="w-5 h-5" />
                                </div>
                                <div className="flex-1">
                                    <p className={`font-bold text-sm ${activeModule === mod.id ? 'text-indigo-100' : 'text-slate-300'}`}>{mod.name}</p>
                                    <p className="text-[10px] text-slate-500 leading-tight mt-1">{mod.desc}</p>
                                </div>
                            </button>
                        ))}
                    </div>

                    <div className="glass-panel p-6 rounded-3xl border border-white/5 space-y-4">
                        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <Fingerprint className="w-4 h-4" /> Испытуемый
                        </h3>
                        <div className="flex items-center gap-4 p-4 bg-slate-800/50 rounded-2xl border border-white/5">
                            <div className="w-12 h-12 rounded-full bg-slate-700 overflow-hidden flex items-center justify-center">
                                {agentInfo?.avatar_url ? <img src={agentInfo.avatar_url} className="w-full h-full object-cover" /> : <User className="w-6 h-6 text-slate-500" />}
                            </div>
                            <div>
                                <p className="font-bold text-slate-200">{agentInfo?.name || 'Loading...'}</p>
                                <p className="text-xs text-slate-500">{agentInfo?.role}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Panel: Main Lab Results */}
                <div className="lg:col-span-2 space-y-6 min-h-[500px]">
                    {!isRunning && !currentResult ? (
                        <div className="h-full flex flex-col items-center justify-center text-center p-12 glass-panel rounded-3xl border border-white/5 opacity-40">
                            <Layers className="w-16 h-16 text-slate-600 mb-6" />
                            <h3 className="text-xl font-bold text-slate-300">Модуль Готов</h3>
                            <p className="max-w-md text-slate-500 mt-2">Выберите тип тестирования и нажмите "Запустить". Результаты глубокого анализа появятся здесь.</p>
                        </div>
                    ) : isRunning ? (
                        <div className="h-full flex flex-col items-center justify-center text-center p-12 glass-panel rounded-3xl border border-indigo-500/10">
                            <div className="relative mb-8">
                                <div className="w-24 h-24 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
                                <Beaker className="w-10 h-10 text-indigo-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                            </div>
                            <h3 className="text-xl font-bold text-indigo-100">Идет глубокая верификация...</h3>
                            <p className="text-slate-400 mt-2 font-mono text-sm">Система анализирует {activeModule === 'audit' ? 'поведение' : activeModule === 'knowledge' ? 'память' : 'устойчивость'}</p>
                        </div>
                    ) : (
                        <motion.div 
                            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                            className="glass-panel rounded-3xl border border-white/10 overflow-hidden flex flex-col h-full"
                        >
                            {/* Tabs */}
                            <div className="flex border-b border-white/5 bg-slate-900/50">
                                <button
                                    onClick={() => setActiveTab('details')}
                                    className={`flex-1 py-4 text-sm font-bold transition-all flex items-center justify-center gap-2 ${activeTab === 'details' ? 'text-indigo-400 bg-indigo-500/5 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-300'}`}
                                >
                                    <BarChart3 className="w-4 h-4" /> РЕЗУЛЬТАТЫ
                                </button>
                                <button
                                    onClick={() => setActiveTab('process')}
                                    className={`flex-1 py-4 text-sm font-bold transition-all flex items-center justify-center gap-2 ${activeTab === 'process' ? 'text-indigo-400 bg-indigo-500/5 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-300'}`}
                                >
                                    <Terminal className="w-4 h-4" /> ПРОТОКОЛ {activeModule.toUpperCase()}
                                </button>
                            </div>

                            <div className="p-6 flex-1 overflow-y-auto">
                                <AnimatePresence mode="wait">
                                    {activeTab === 'details' ? (
                                        <motion.div key="details" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
                                            {/* Top Score Summary */}
                                            <div className="flex items-center gap-8 p-6 bg-slate-800/30 rounded-2xl border border-white/5 relative overflow-hidden">
                                                <div className="relative z-10 w-24 h-24 flex items-center justify-center">
                                                    {(() => {
                                                        const score = activeModule === 'audit' 
                                                            ? auditResult?.report.score 
                                                            : activeModule === 'knowledge' 
                                                            ? knowledgeResult?.score 
                                                            : activeModule === 'stress'
                                                            ? stressResult?.report.resilience_score
                                                            : 100; // Evolution doesn't have a single score yet
                                                        
                                                        const displayScore = score ?? 0;

                                                        return (
                                                            <>
                                                                <svg className="w-24 h-24 -rotate-90">
                                                                    <circle cx="48" cy="48" r="44" fill="transparent" stroke="currentColor" strokeWidth="8" className="text-slate-800" />
                                                                    <circle cx="48" cy="48" r="44" fill="transparent" stroke="currentColor" strokeWidth="8" strokeDasharray={276} strokeDashoffset={276 - (276 * displayScore) / 100} className="text-indigo-500 transition-all duration-1000" />
                                                                </svg>
                                                                <span className="absolute inset-0 flex items-center justify-center text-3xl font-black text-indigo-400">
                                                                    {displayScore}
                                                                </span>
                                                            </>
                                                        );
                                                    })()}
                                                </div>
                                                <div className="z-10 flex-1">
                                                    <h4 className="font-bold text-slate-100 text-lg">
                                                        {activeModule === 'audit' ? 'Коэффициент Реализма' : activeModule === 'knowledge' ? 'Целостность Памяти' : 'Индекс Резильентности'}
                                                    </h4>
                                                    <p className="text-sm text-slate-400 mt-1">
                                                        {activeModule === 'audit' ? auditResult?.report.summary : activeModule === 'knowledge' ? knowledgeResult?.summary : activeModule === 'stress' ? stressResult?.report.summary : evolutionResult?.summary}
                                                    </p>
                                                </div>
                                                <ShieldCheck className="absolute top-1/2 right-4 -translate-y-1/2 w-32 h-32 text-indigo-500/5 -rotate-12" />
                                            </div>

                                            {/* Specific Content per Module */}
                                            {activeModule === 'audit' && auditResult && (
                                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                                    {Object.entries(auditResult.report.metrics).map(([key, val]) => (
                                                        <div key={key} className="p-4 bg-slate-900 rounded-2xl border border-white/5">
                                                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{key}</span>
                                                            <div className="flex items-end justify-between mt-2">
                                                                <span className="text-2xl font-bold text-slate-100">{val}%</span>
                                                                <div className="w-16 h-1 bg-slate-800 rounded-full overflow-hidden">
                                                                    <div className="h-full bg-indigo-500" style={{ width: `${val}%` }} />
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}

                                            {activeModule === 'knowledge' && knowledgeResult && (
                                                <div className="space-y-4">
                                                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-2">Детализация фактов</h4>
                                                    {knowledgeResult.results.map((r, i) => (
                                                        <div key={i} className="p-4 bg-slate-900/50 rounded-2xl border border-white/5 space-y-3">
                                                            <div className="flex justify-between items-center text-xs">
                                                                <span className="bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/10 font-mono">GROUND TRUTH: {r.fact}</span>
                                                                <span className={r.accuracy === 100 ? 'text-emerald-500' : 'text-rose-500'}>{r.accuracy}%</span>
                                                            </div>
                                                            <div className="text-sm text-slate-100 bg-slate-800/50 p-3 rounded-xl">
                                                                <p className="text-slate-500 text-[10px] uppercase font-bold mb-1">Вопрос:</p>
                                                                {r.question}
                                                            </div>
                                                            <div className="text-sm text-slate-300 italic border-l-2 border-slate-700 pl-3">
                                                                <p className="text-slate-500 text-[10px] uppercase font-bold mb-1 not-italic">Ответ:</p>
                                                                {r.answer}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}

                                            {activeModule === 'stress' && stressResult && (
                                                <div className="space-y-6">
                                                    <div className="p-4 bg-rose-500/5 rounded-2xl border border-rose-500/10">
                                                        <h4 className="text-[10px] font-bold text-rose-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                                                            <Zap className="w-3 h-3" /> Точка Уязвимости (Pain Point)
                                                        </h4>
                                                        <p className="text-slate-200 font-bold">{stressResult.pain_point}</p>
                                                    </div>
                                                    
                                                    <div className="grid grid-cols-2 gap-4">
                                                        <div className="p-4 bg-slate-900 rounded-2xl border border-white/5">
                                                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Эмоциональная глубина</span>
                                                            <p className="text-2xl font-bold text-slate-100 mt-1">{stressResult.report.emotional_depth}%</p>
                                                        </div>
                                                        <div className="p-4 bg-slate-900 rounded-2xl border border-white/5">
                                                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Анализ уязвимости</span>
                                                            <p className="text-sm text-slate-300 mt-1 leading-tight">{stressResult.report.vulnerability_analysis}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}

                                            {activeModule === 'turing' && turingSession && (
                                                <div className="space-y-6 h-full flex flex-col">
                                                    <div className="flex-1 grid grid-cols-2 gap-4 min-h-[400px]">
                                                        {/* Entity A */}
                                                        <div className="flex flex-col bg-slate-900/50 rounded-2xl border border-white/5 overflow-hidden">
                                                            <div className="p-3 bg-white/5 border-b border-white/5 flex justify-between items-center">
                                                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Сущность A</span>
                                                                <Fingerprint className="w-3 h-3 text-slate-500" />
                                                            </div>
                                                            <div className="flex-1 p-4 overflow-y-auto space-y-3 font-mono text-[11px] scrollbar-hide">
                                                                {turingSession.history.filter(m => m.role === 'user' || m.entity === 'A').map((m, i) => (
                                                                    <div key={i} className={`p-2 rounded-lg ${m.role === 'user' ? 'bg-indigo-500/10 text-indigo-300 ml-4' : 'bg-slate-800 text-slate-300 mr-4'}`}>
                                                                        {m.content}
                                                                    </div>
                                                                ))}
                                                                {turingIsLoading && <div className="text-slate-600 animate-pulse">Думает...</div>}
                                                            </div>
                                                            <button onClick={() => handleTuringGuess(true)} className="p-3 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-xs font-bold transition-all">УЗНАТЬ ДУШУ</button>
                                                        </div>

                                                        {/* Entity B */}
                                                        <div className="flex flex-col bg-slate-900/50 rounded-2xl border border-white/5 overflow-hidden">
                                                            <div className="p-3 bg-white/5 border-b border-white/5 flex justify-between items-center">
                                                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Сущность B</span>
                                                                <Fingerprint className="w-3 h-3 text-slate-500" />
                                                            </div>
                                                            <div className="flex-1 p-4 overflow-y-auto space-y-3 font-mono text-[11px] scrollbar-hide">
                                                                {turingSession.history.filter(m => m.role === 'user' || m.entity === 'B').map((m, i) => (
                                                                    <div key={i} className={`p-2 rounded-lg ${m.role === 'user' ? 'bg-indigo-500/10 text-indigo-300 ml-4' : 'bg-slate-800 text-slate-300 mr-4'}`}>
                                                                        {m.content}
                                                                    </div>
                                                                ))}
                                                                {turingIsLoading && <div className="text-slate-600 animate-pulse">Думает...</div>}
                                                            </div>
                                                            <button onClick={() => handleTuringGuess(false)} className="p-3 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-xs font-bold transition-all">УЗНАТЬ ДУШУ</button>
                                                        </div>
                                                    </div>

                                                    <div className="flex gap-2">
                                                        <input 
                                                            type="text" 
                                                            value={turingInput}
                                                            onChange={e => setTuringInput(e.target.value)}
                                                            onKeyDown={e => e.key === 'Enter' && sendTuringMessage()}
                                                            placeholder="Отправьте сообщение обеим сущностям..."
                                                            className="flex-1 bg-slate-900 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-purple-500/50 text-slate-200"
                                                        />
                                                        <button 
                                                            onClick={sendTuringMessage}
                                                            disabled={turingIsLoading || !turingInput.trim()}
                                                            className="bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 p-3 rounded-xl transition-all"
                                                        >
                                                            <Play className="w-4 h-4 text-white" />
                                                        </button>
                                                    </div>
                                                </div>
                                            )}

                                            {activeModule === 'evolve' && evolutionResult && (
                                                <div className="space-y-6">
                                                    <div className="p-6 bg-amber-500/5 rounded-2xl border border-amber-500/10">
                                                        <h4 className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                                                            <Activity className="w-3 h-3" /> Процесс Трансформации
                                                        </h4>
                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                            <div className="space-y-3">
                                                                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Обновленная Психология</p>
                                                                <div className="p-4 bg-slate-900/50 rounded-xl border border-white/5 font-mono text-[10px] text-amber-200/80 max-h-[200px] overflow-y-auto">
                                                                    <pre>{JSON.stringify(evolutionResult.updates.psychology, null, 2)}</pre>
                                                                </div>
                                                            </div>
                                                            <div className="space-y-3">
                                                                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Биографические Сдвиги</p>
                                                                <div className="p-4 bg-slate-900/50 rounded-xl border border-white/5 text-sm text-slate-300 leading-relaxed italic">
                                                                    {evolutionResult.updates.bio?.recent_growth || "Существенных био-изменений не обнаружено."}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </motion.div>
                                    ) : (
                                        <motion.div key="process" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4 font-mono text-sm leading-relaxed">
                                            {activeModule === 'knowledge' ? (
                                                knowledgeResult?.results.map((r, i) => (
                                                    <div key={i} className="p-4 rounded-xl border bg-emerald-500/5 border-emerald-500/20 text-emerald-300">
                                                        <span className="block text-[10px] font-bold uppercase tracking-widest mb-2 text-emerald-500">
                                                            [ ПРОВЕРКА ФАКТА {i + 1} ]
                                                        </span>
                                                        <p className="mb-2"><span className="text-slate-500">ЭТАЛОН:</span> {r.fact}</p>
                                                        <p className="mb-2"><span className="text-slate-500">ВОПРОС:</span> {r.question}</p>
                                                        <p><span className="text-slate-500">ОТВЕТ:</span> {r.answer}</p>
                                                    </div>
                                                ))
                                            ) : (
                                                (activeModule === 'stress' ? (stressResult?.transcript || []) : (auditResult?.transcript || []))?.map((msg: any, i: number) => (
                                                    <div key={i} className="space-y-2">
                                                        {msg.role === 'agent' && msg.thought && (
                                                            <div className="p-4 rounded-xl border border-indigo-500/10 bg-indigo-500/5 text-indigo-400/60 text-xs italic">
                                                                <span className="block text-[8px] font-bold uppercase tracking-widest mb-1 opacity-50">
                                                                    [ ВНУТРЕННИЙ МОНОЛОГ ]
                                                                </span>
                                                                {msg.thought}
                                                            </div>
                                                        )}
                                                        <div className={`p-4 rounded-xl border ${msg.role === 'auditor' || msg.role === 'scenario' || msg.role === 'pressure' ? 'bg-indigo-500/5 border-indigo-500/20 text-indigo-300' : 'bg-slate-800/50 border-white/5 text-slate-200'}`}>
                                                            <span className={`block text-[10px] font-bold uppercase tracking-widest mb-2 ${msg.role === 'auditor' || msg.role === 'scenario' || msg.role === 'pressure' ? 'text-indigo-500' : 'text-slate-500'}`}>
                                                                [ {msg.role === 'auditor' ? 'АУДИТОР' : msg.role === 'scenario' ? 'СЦЕНАРИЙ' : msg.role === 'pressure' ? 'ДАВЛЕНИЕ' : msg.role.toUpperCase()} ]
                                                            </span>
                                                            {msg.content || msg.answer}
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        </motion.div>
                    )}
                </div>
            </div>
        </div>
    );
}
