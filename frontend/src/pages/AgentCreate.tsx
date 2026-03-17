import { useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { BrainCircuit, Sparkles, AlertCircle } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';

export default function AgentCreate() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        name_hint: '',
        role_hint: '',
        personality_hint: '',
        country_hint: '',
        city_hint: '',
        visual_dna: ''
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            const payload = {
                name_hint: formData.name_hint || undefined,
                role_hint: formData.role_hint || undefined,
                personality_hint: formData.personality_hint || undefined,
                country_hint: formData.country_hint || undefined,
                city_hint: formData.city_hint || undefined,
                criteria: { visual_dna: formData.visual_dna }
            };

            const apiBase = '/api/v1';
            const res = await axios.post(`${apiBase}/generate/soul`, payload);

            if (res.data.job_id) {
                navigate('/');
            }
        } catch (err: any) {
            setError(err?.response?.data?.detail || err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-w-2xl mx-auto mt-10"
        >
            <div className="glass-panel rounded-2xl p-8 border border-primary-500/20 shadow-2xl shadow-primary-500/10">
                <div className="flex items-center gap-4 mb-8">
                    <div className="bg-primary-500/20 p-3 rounded-2xl">
                        <BrainCircuit className="w-8 h-8 text-primary-400" />
                    </div>
                    <div>
                        <h2 className="text-3xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">Создать Агента</h2>
                        <p className="text-slate-400 font-medium mt-1">Инициализировать новую когнитивную архитектуру</p>
                    </div>
                </div>

                <div className="mb-4 p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-xl text-sm text-emerald-400 flex items-center gap-2">
                    <span>✨</span>
                    <span>Хотите полную 13-этапную генерацию?</span>
                    <Link to="/staged-create" className="ml-auto underline hover:text-emerald-300 transition-colors font-semibold">
                        Глубокий Синтез →
                    </Link>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-xl flex items-center gap-3 text-red-200">
                        <AlertCircle className="w-5 h-5" />
                        <p>{error}</p>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">

                    <div className="grid grid-cols-2 gap-5">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">Имя агента</label>
                            <input
                                type="text"
                                value={formData.name_hint}
                                onChange={e => setFormData({ ...formData, name_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Айко"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">Профессия / Роль</label>
                            <input
                                type="text"
                                value={formData.role_hint}
                                onChange={e => setFormData({ ...formData, role_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Кибер-хакер"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-5">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">🌍 Страна</label>
                            <input
                                type="text"
                                value={formData.country_hint}
                                onChange={e => setFormData({ ...formData, country_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Япония"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-slate-300 ml-1">🏙️ Город</label>
                            <input
                                type="text"
                                value={formData.city_hint}
                                onChange={e => setFormData({ ...formData, city_hint: e.target.value })}
                                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600"
                                placeholder="например: Токио"
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-300 ml-1">Черты личности</label>
                        <textarea
                            value={formData.personality_hint}
                            onChange={e => setFormData({ ...formData, personality_hint: e.target.value })}
                            className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 h-24 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600 resize-none"
                            placeholder="например: Интроверт, саркастичный, гениальный но ленивый…"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-300 ml-1">Визуальная ДНК (внешность)</label>
                        <textarea
                            value={formData.visual_dna}
                            onChange={e => setFormData({ ...formData, visual_dna: e.target.value })}
                            className="w-full bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-3 h-24 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all font-medium placeholder-slate-600 resize-none"
                            placeholder="например: Неоново-зелёные волосы, кибернетический глаз…"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full mt-2 bg-gradient-to-r from-primary-600 to-purple-600 hover:from-primary-500 hover:to-purple-500 text-white font-bold text-lg py-4 rounded-xl flex items-center justify-center gap-3 transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-xl shadow-primary-500/25 disabled:opacity-50 disabled:pointer-events-none"
                    >
                        {loading ? (
                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                        ) : (
                            <>
                                <Sparkles className="w-6 h-6" />
                                <span>Начать Генерацию</span>
                            </>
                        )}
                    </button>
                </form>
            </div>
        </motion.div>
    );
}
