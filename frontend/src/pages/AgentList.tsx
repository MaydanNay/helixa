import { useEffect, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { 
  User, Activity, Layers, Trash2, BrainCircuit, 
  LayoutList, ShieldCheck, ShieldAlert, Zap, Globe, 
  Download, CheckCircle2, AlertCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface Agent {
  id: string;
  name: string;
  role: string | null;
  avatar_url: string | null;
  created_at: string;
  agent_data?: any;
  ci_score?: number | null;
  ci_passed?: boolean | null;
  ci_report?: any;
}

export default function AgentList() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const apiBase = '/api/v1';
    axios.get(`${apiBase}/agents`)
      .then(res => setAgents(res.data))
      .catch(err => console.error("Failed to fetch agents", err))
      .finally(() => setLoading(false));
  }, []);

  const handleDeleteAll = async () => {
    if (window.confirm("Вы уверены, что хотите удалить ВСЕХ агентов? Это действие необратимо.")) {
      setIsDeleting(true);
      try {
        const apiBase = '/api/v1';
        await axios.delete(`${apiBase}/agents`);
        setAgents([]);
      } catch (err) {
        console.error("Failed to delete agents", err);
        alert("Ошибка при удалении агентов.");
      } finally {
        setIsDeleting(false);
      }
    }
  };

  const getAgentStatus = (agent: Agent) => {
    if (agent.ci_score === null || agent.ci_score === undefined) return { label: 'Черновик', class: 'draft-badge', icon: AlertCircle };
    if (agent.ci_score >= 80) return { label: 'Идеальный', class: 'ideal-badge', icon: ShieldCheck };
    if (agent.ci_score >= 70) return { label: 'Стабильный', class: 'stable-badge', icon: CheckCircle2 };
    return { label: 'Доработка', class: 'bg-amber-500/80 shadow-lg shadow-amber-500/20', icon: Zap };
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Premium Header */}
      <div className="flex flex-col lg:flex-row lg:justify-between lg:items-end gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-primary-400 font-bold text-xs uppercase tracking-widest">
            <Globe className="w-4 h-4" />
            Реестр Цифровых Сущностей
          </div>
          <h2 className="text-4xl lg:text-5xl font-black text-glow tracking-tight">Галерея Сущностей</h2>
          <p className="text-slate-400 max-w-xl text-lg font-medium leading-relaxed">
            Реестр цифровых душ, прошедших через этапы синтеза и психологического аудита.
          </p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={`${'/api/v1'}/agents/export/all`}
            download
            className="flex items-center gap-2 glass-panel hover:bg-white/5 border-white/10 text-slate-200 px-5 py-2.5 rounded-2xl transition-all font-bold text-sm"
          >
            <Download className="w-4 h-4" />
            Экспорт
          </a>
          <button
            onClick={handleDeleteAll}
            disabled={isDeleting || agents.length === 0}
            className="flex items-center gap-2 glass-panel hover:bg-red-500/10 border-white/5 text-slate-400 hover:text-red-400 px-5 py-2.5 rounded-2xl transition-all font-bold text-sm disabled:opacity-30"
          >
            <Trash2 className="w-4 h-4" />
            Очистить
          </button>
          <div className="bg-slate-800/80 border border-white/5 px-4 py-2.5 flex items-center gap-3 rounded-2xl text-sm font-bold shadow-inner">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300">{agents.length} Активных</span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-32 space-y-4">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary-500"></div>
          <div className="text-slate-500 font-bold tracking-widest uppercase text-xs">Синхронизация данных...</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-8">
          {agents.map((agent, i) => {
            const status = getAgentStatus(agent);
            const StatusIcon = status.icon;
            const data = agent.agent_data || {};
            const resolvedName = data.demographics?.agent_name || data.editor?.name || agent.name;
            const resolvedRole = data.demographics?.agent_role || data.editor?.role || agent.role;
            const metrics = agent.ci_report?.metrics || {};

            return (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.03 }}
                className={`relative group ${agent.ci_score && agent.ci_score >= 80 ? 'premium-glow' : ''}`}
              >
                <div 
                  className="glass-panel rounded-3xl overflow-hidden hover:bg-slate-800/40 transition-all duration-500 cursor-pointer h-full border-white/5 flex flex-col"
                  onClick={() => window.location.assign(`/agent/${agent.id}`)}
                >
                  {/* Photo Section */}
                  <div className="h-64 bg-slate-800 relative overflow-hidden flex items-center justify-center shrink-0">
                    {agent.avatar_url ? (
                      <div className="absolute inset-0 bg-cover bg-center group-hover:scale-110 transition-transform duration-700" style={{ backgroundImage: `url(${agent.avatar_url})` }} />
                    ) : (
                      <User className="w-20 h-20 text-slate-700" />
                    )}

                    {/* Status Badge */}
                    <div className="absolute top-4 left-4 z-20">
                      <div className={`px-3 py-1.5 rounded-xl flex items-center gap-2 text-white text-[10px] font-black uppercase tracking-widest ${status.class}`}>
                        <StatusIcon className="w-3 h-3" />
                        {status.label}
                      </div>
                    </div>

                    {/* Stages Icon Button */}
                    <Link
                      to={`/agent/${agent.id}/stages`}
                      onClick={(e) => e.stopPropagation()}
                      className="absolute top-4 right-4 z-20 p-2 bg-black/40 hover:bg-black/60 border border-white/10 rounded-xl text-white transition-all hover:scale-110"
                      title="Этапы генерации"
                    >
                      <LayoutList className="w-4 h-4" />
                    </Link>

                    {/* Overlay Gradient */}
                    <div className="absolute inset-0 card-overlay-gradient pointer-events-none" />

                    {/* Name/Role Overlay */}
                    <div className="absolute bottom-0 left-0 right-0 p-6 z-10">
                      <h3 className="font-black text-2xl truncate text-white leading-tight mb-1">
                        {resolvedName !== "Unknown" ? resolvedName : 'Неизвестный'}
                      </h3>
                      <p className="text-sm font-bold text-primary-400 tracking-wide truncate uppercase">
                        {resolvedRole !== "AI Agent" ? resolvedRole : 'Цифровая сущность'}
                      </p>
                    </div>
                  </div>

                  {/* Body / Metrics */}
                  <div className="p-6 space-y-5 flex-1 flex flex-col justify-between">
                    <div className="grid grid-cols-1 gap-3">
                      <div className="space-y-1">
                        <div className="flex justify-between items-center">
                          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Консистентность</div>
                          <span className="text-[10px] font-black text-emerald-400">{metrics.consistency || 0}%</span>
                        </div>
                        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full" 
                            style={{ width: `${metrics.consistency || 0}%` }} 
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-1">
                        <div className="flex justify-between items-center">
                          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Глубина знаний</div>
                          <span className="text-[10px] font-black text-purple-400">{metrics.depth || 0}%</span>
                        </div>
                        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-purple-600 to-purple-400 rounded-full" 
                            style={{ width: `${metrics.depth || 0}%` }} 
                          />
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between items-center">
                          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Резильентность</div>
                          <span className="text-[10px] font-black text-blue-400">{metrics.stress_score || 0}%</span>
                        </div>
                        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full" 
                            style={{ width: `${metrics.stress_score || 0}%` }} 
                          />
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-3 pt-2" onClick={(e) => e.stopPropagation()}>
                      <Link
                        to={`/agent/${agent.id}/graph`}
                        className="w-full py-3 bg-primary-500/10 hover:bg-primary-500 text-primary-400 hover:text-white border border-primary-500/20 rounded-2xl text-xs font-black transition-all flex items-center justify-center gap-2 group/btn shadow-lg shadow-transparent hover:shadow-primary-500/20"
                      >
                        <BrainCircuit className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />
                        ПОГРУЖЕНИЕ В ПАМЯТЬ
                      </Link>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
          
          {agents.length === 0 && (
            <div className="col-span-full text-center py-24 bg-slate-800/20 rounded-3xl border-2 border-dashed border-white/5">
              <div className="max-w-xs mx-auto space-y-4">
                <Layers className="w-16 h-16 text-slate-700 mx-auto" />
                <h3 className="text-xl font-bold text-slate-400">Реестр пуст</h3>
                <p className="text-slate-500 text-sm">Начните синтез первого агента, чтобы наполнить галерею.</p>
                <Link to="/batch-create" className="inline-block text-primary-400 font-bold hover:text-primary-300 transition-colors">
                  Создать партию сущностей →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
