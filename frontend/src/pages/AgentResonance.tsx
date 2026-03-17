import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    ArrowLeft, Send, Sparkles, BrainCircuit, History, 
    User, Bot, Terminal, Info, Zap
} from 'lucide-react';

interface Message {
    id: string;
    role: 'user' | 'agent';
    text: string;
    nodes?: string;
    episodes?: string;
    timestamp: Date;
}

interface AgentInfo {
    name: string;
    role: string;
    avatar_url: string | null;
}

export default function AgentResonance() {
    const { id } = useParams();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
    const [showAuditPanel, setShowAuditPanel] = useState(false);
    const [activeAuditMsg, setActiveAuditMsg] = useState<Message | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    const apiBase = '/api/v1';

    useEffect(() => {
        // Load agent basic info
        axios.get(`${apiBase}/agents/${id}`)
            .then(res => {
                setAgentInfo({
                    name: res.data.name,
                    role: res.data.role,
                    avatar_url: res.data.avatar_url
                });
                
                // Greeting message
                setMessages([{
                    id: 'greeting',
                    role: 'agent',
                    text: `Соединение установлено. Я чувствую твое присутствие. Я ${res.data.name}, и моя сущность готова к резонансу. О чем ты хочешь спросить мою душу?`,
                    timestamp: new Date()
                }]);
            })
            .catch(err => console.error('Failed to load agent for resonance', err));
    }, [id]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            text: input,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await axios.post(`${apiBase}/agents/${id}/action`, {
                prompt: input
            });

            const agentMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'agent',
                text: response.data.action,
                nodes: response.data.retrieved_nodes,
                episodes: response.data.retrieved_episodes,
                timestamp: new Date()
            };

            setMessages(prev => [...prev, agentMsg]);
        } catch (err: any) {
            console.error('Resonance failed', err);
            setMessages(prev => [...prev, {
                id: 'error-' + Date.now(),
                role: 'agent',
                text: 'Связь прервана... Мои мысли запутались в эфире. Попробуй еще раз позже.',
                timestamp: new Date()
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const toggleAudit = (msg: Message) => {
        if (activeAuditMsg?.id === msg.id && showAuditPanel) {
            setShowAuditPanel(false);
        } else {
            setActiveAuditMsg(msg);
            setShowAuditPanel(true);
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-120px)] max-w-6xl mx-auto overflow-hidden relative">
            {/* Header */}
            <header className="flex items-center justify-between p-4 glass-panel rounded-t-3xl border-b border-white/10 relative z-20">
                <div className="flex items-center gap-4">
                    <Link to={`/agent/${id}`} className="p-2 hover:bg-white/5 rounded-xl transition-colors">
                        <ArrowLeft className="w-5 h-5 text-slate-400" />
                    </Link>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-slate-800 rounded-full overflow-hidden border border-amber-500/30 flex items-center justify-center">
                            {agentInfo?.avatar_url ? (
                                <img src={agentInfo.avatar_url} alt={agentInfo.name} className="w-full h-full object-cover" />
                            ) : (
                                <User className="w-6 h-6 text-slate-600" />
                            )}
                        </div>
                        <div>
                            <h2 className="font-bold text-slate-100 flex items-center gap-2">
                                {agentInfo?.name || 'Загрузка...'}
                                <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded-md border border-amber-500/30 uppercase tracking-tighter">
                                    Резонанс Души
                                </span>
                            </h2>
                            <p className="text-xs text-slate-400 italic">{agentInfo?.role}</p>
                        </div>
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    <button 
                        onClick={() => setShowAuditPanel(!showAuditPanel)}
                        className={`p-2 rounded-xl transition-all ${showAuditPanel ? 'bg-amber-500/20 text-amber-400' : 'hover:bg-white/5 text-slate-400'}`}
                        title="Панель аудита"
                    >
                        <Terminal className="w-5 h-5" />
                    </button>
                    <div className="hidden sm:flex items-center gap-2 text-[10px] text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full border border-emerald-400/20 shadow-[0_0_10px_rgba(52,211,153,0.1)]">
                        <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                        СВЯЗЬ АКТИВНА
                    </div>
                </div>
            </header>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden relative">
                {/* Chat Section */}
                <div className={`flex flex-col flex-1 transition-all duration-300 ${showAuditPanel ? 'mr-0 lg:mr-4' : ''}`}>
                    <div 
                        ref={scrollRef}
                        className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scroll-smooth"
                    >
                        <AnimatePresence initial={false}>
                            {messages.map((msg) => (
                                <motion.div
                                    key={msg.id}
                                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`max-w-[85%] sm:max-w-[70%] group relative ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                                        <div className={`inline-block px-4 py-3 rounded-2xl relative shadow-2xl ${
                                            msg.role === 'user' 
                                            ? 'bg-gradient-to-br from-primary-600 to-indigo-700 text-white rounded-tr-none' 
                                            : 'bg-slate-800/80 backdrop-blur-md border border-white/10 text-slate-200 rounded-tl-none'
                                        }`}>
                                            <p className="whitespace-pre-wrap text-sm sm:text-base leading-relaxed">
                                                {msg.text}
                                            </p>
                                            
                                            {msg.role === 'agent' && (msg.nodes || msg.episodes) && (
                                                <button 
                                                    onClick={() => toggleAudit(msg)}
                                                    className="absolute -right-10 top-2 opacity-0 group-hover:opacity-100 transition-opacity p-2 text-slate-500 hover:text-amber-400"
                                                >
                                                    <Info className="w-4 h-4" />
                                                </button>
                                            )}
                                        </div>
                                        <div className="text-[10px] text-slate-500 mt-1 px-1">
                                            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </AnimatePresence>
                        {isLoading && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                                <div className="bg-slate-800/50 backdrop-blur-sm border border-white/5 px-4 py-3 rounded-2xl rounded-tl-none flex gap-2 items-center">
                                    <div className="flex gap-1">
                                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" />
                                    </div>
                                    <span className="text-xs text-slate-400 font-medium font-mono uppercase tracking-widest">Резонанс...</span>
                                </div>
                            </motion.div>
                        )}
                    </div>

                    {/* Input Area */}
                    <div className="p-4 bg-slate-900/50 backdrop-blur-xl border-t border-white/10">
                        <div className="relative max-w-4xl mx-auto flex gap-2">
                            <div className="relative flex-1">
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                                    placeholder="Направьте свои мысли..."
                                    className="w-full bg-slate-800/80 border border-white/10 rounded-2xl py-4 pl-4 pr-12 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 transition-all"
                                />
                                <div className="absolute right-4 top-1/2 -translate-y-1/2 flex gap-3 text-slate-500">
                                    <Zap className="w-4 h-4" />
                                </div>
                            </div>
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || isLoading}
                                className="bg-primary-600 hover:bg-primary-500 disabled:bg-slate-800 disabled:text-slate-600 text-white p-4 rounded-2xl transition-all shadow-lg shadow-primary-900/20"
                            >
                                <Send className="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Audit Panel (Sidebar) */}
                <AnimatePresence>
                    {showAuditPanel && (
                        <motion.aside
                            initial={{ x: '100%' }}
                            animate={{ x: 0 }}
                            exit={{ x: '100%' }}
                            transition={{ type: 'spring', damping: 20 }}
                            className="absolute lg:relative top-0 right-0 h-full w-full lg:w-96 z-30 bg-slate-900/95 lg:bg-slate-800/40 backdrop-blur-2xl border-l border-white/10 flex flex-col"
                        >
                            <div className="p-4 border-b border-white/10 flex items-center justify-between">
                                <h3 className="font-bold text-slate-200 flex items-center gap-2">
                                    <Terminal className="w-4 h-4 text-amber-500" />
                                    Душевный Аудит
                                </h3>
                                <button onClick={() => setShowAuditPanel(false)} className="lg:hidden p-2 text-slate-400 hover:text-white">
                                    <ArrowLeft className="w-5 h-5 rotate-180" />
                                </button>
                            </div>
                            
                            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                                {!activeAuditMsg || activeAuditMsg.role === 'user' ? (
                                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-50">
                                        <BrainCircuit className="w-12 h-12 text-slate-600" />
                                        <p className="text-slate-400 text-sm">Выберите ответ агента, чтобы проанализировать его источники данных.</p>
                                    </div>
                                ) : (
                                    <>
                                        <div>
                                            <h4 className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                                                <BrainCircuit className="w-3 h-3" /> Семантические Факты (Neo4j)
                                            </h4>
                                            <div className="bg-black/30 rounded-xl p-3 border border-white/5 font-mono text-xs text-blue-300 leading-relaxed max-h-64 overflow-y-auto">
                                                {activeAuditMsg.nodes || 'Нет найденных связей.'}
                                            </div>
                                        </div>

                                        <div>
                                            <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                                                <History className="w-3 h-3" /> Эпизодические Воспоминания (Qdrant)
                                            </h4>
                                            <div className="bg-black/30 rounded-xl p-3 border border-white/5 font-mono text-xs text-indigo-300 leading-relaxed max-h-64 overflow-y-auto">
                                                {activeAuditMsg.episodes || 'Нет соответствующих эпизодов.'}
                                            </div>
                                        </div>

                                        <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10">
                                            <div className="flex gap-2 items-start">
                                                <Sparkles className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                                                <p className="text-[11px] text-slate-400 leading-tight">
                                                    Этот ответ был синтезирован на основе гибридного GraphRAG. 
                                                    Факты определяют логику, а эпизоды — эмоциональный фон.
                                                </p>
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>
                        </motion.aside>
                    )}
                </AnimatePresence>
            </div>

            {/* Background Glows */}
            <div className="absolute top-1/4 -left-32 w-96 h-96 bg-primary-600/15 blur-[120px] rounded-full pointer-events-none z-0" />
            <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-purple-600/15 blur-[120px] rounded-full pointer-events-none z-0" />
        </div>
    );
}
