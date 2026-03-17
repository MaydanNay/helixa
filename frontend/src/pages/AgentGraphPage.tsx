import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Activity, Info, Zap, Maximize2, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react';

interface GraphData {
    nodes: any[];
    links: any[];
}

interface AgentInfo {
    name: string;
    role: string;
}

export default function AgentGraphPage() {
    const { id } = useParams();
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const fgRef = useRef<any>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [graphRes, agentRes] = await Promise.all([
                    axios.get(`/api/v1/agents/${id}/graph`),
                    axios.get(`/api/v1/agents/${id}`)
                ]);
                setData(graphRes.data);
                
                const agentData = agentRes.data;
                const name = agentData.agent_data?.demographics?.agent_name || agentData.name || 'Безымянный';
                const role = agentData.agent_data?.demographics?.agent_role || agentData.role || 'ИИ Агент';
                setAgentInfo({ name, role });
            } catch (err) {
                console.error('Failed to fetch graph data:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [id]);

    const getColor = (label: string) => {
        switch (label.toUpperCase()) {
            case 'AGENT': return '#60a5fa'; // Blue
            case 'LOCATION': return '#34d399'; // Green
            case 'ORGANIZATION': return '#a78bfa'; // Purple
            case 'ITEM': return '#fbbf24'; // Amber
            case 'GOAL': return '#f87171'; // Red
            default: return '#94a3b8'; // Slate
        }
    };

    if (loading) {
        return (
            <div className="h-screen flex items-center justify-center bg-slate-950 text-primary-400">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-16 h-16 border-4 border-primary-500/20 border-t-primary-500 rounded-full animate-spin" />
                    <span className="text-sm font-mono tracking-widest uppercase animate-pulse">Инициализация нейронных связей...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen w-screen bg-slate-950 overflow-hidden flex flex-col relative" ref={containerRef}>
            {/* Header Overlay */}
            <div className="absolute top-0 left-0 right-0 z-50 p-6 flex justify-between items-start pointer-events-none">
                <div className="flex flex-col gap-4 pointer-events-auto">
                    <Link to={`/agent/${id}`} className="glass-panel p-2 rounded-xl border border-white/5 hover:bg-white/5 transition-colors group inline-flex items-center gap-2 text-slate-400">
                        <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform" />
                        <span className="text-sm">Вернуться к профилю</span>
                    </Link>
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <div className="w-3 h-3 rounded-full bg-primary-500 animate-pulse shadow-[0_0_15px_rgba(59,130,246,0.5)]" />
                            <h1 className="text-2xl font-bold text-white tracking-tight leading-none">
                                {agentInfo?.name} <span className="text-slate-500 font-light text-xl">/ Neural Memory</span>
                            </h1>
                        </div>
                        <p className="text-primary-400 text-sm font-medium uppercase tracking-widest pl-6 opacity-80">
                            {agentInfo?.role}
                        </p>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-3 pointer-events-auto">
                    <div className="glass-panel px-4 py-2 rounded-xl flex items-center gap-3 border border-white/5 bg-slate-900/40">
                        <Activity className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs font-mono text-slate-300">Active Sync: Neo4j Graph Database</span>
                    </div>
                    <div className="flex gap-2">
                        <button onClick={() => fgRef.current?.zoomToFit(400)} className="glass-panel p-2 rounded-lg border border-white/5 hover:bg-white/5 transition-colors text-slate-400" title="Zoom to fit">
                            <Maximize2 className="w-4 h-4" />
                        </button>
                        <button onClick={() => fgRef.current?.zoom(fgRef.current?.zoom() * 1.2)} className="glass-panel p-2 rounded-lg border border-white/5 hover:bg-white/5 transition-colors text-slate-400">
                            <ZoomIn className="w-4 h-4" />
                        </button>
                        <button onClick={() => fgRef.current?.zoom(fgRef.current?.zoom() * 0.8)} className="glass-panel p-2 rounded-lg border border-white/5 hover:bg-white/5 transition-colors text-slate-400">
                            <ZoomOut className="w-4 h-4" />
                        </button>
                        <button onClick={() => window.location.reload()} className="glass-panel p-2 rounded-lg border border-white/5 hover:bg-white/5 transition-colors text-slate-400">
                            <RefreshCw className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Canvas Area */}
            <div className="flex-1 bg-[radial-gradient(circle_at_center,_#0f172a_0%,_#020617_100%)]">
                <ForceGraph2D
                    ref={fgRef}
                    graphData={data}
                    nodeLabel="name"
                    nodeColor={(node: any) => selectedNode?.id === node.id ? '#fff' : getColor(node.label)}
                    nodeRelSize={7}
                    linkColor={() => 'rgba(255,255,255,0.08)'}
                    linkDirectionalParticles={2}
                    linkDirectionalParticleSpeed={() => 0.005}
                    linkDirectionalParticleWidth={2}
                    linkDirectionalArrowLength={4}
                    linkDirectionalArrowRelPos={1}
                    linkCurvature={0.2}
                    nodeCanvasObject={(node: any, ctx, globalScale) => {
                        const label = node.name;
                        const fontSize = 12 / globalScale;
                        ctx.font = `${fontSize}px Inter, sans-serif`;

                        // Node Circle
                        ctx.beginPath();
                        ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
                        ctx.fillStyle = selectedNode?.id === node.id ? '#fff' : getColor(node.label);
                        ctx.fill();
                        
                        // Glow for selected
                        if (selectedNode?.id === node.id) {
                            ctx.shadowBlur = 15;
                            ctx.shadowColor = '#fff';
                        } else {
                            ctx.shadowBlur = 0;
                        }

                        // Label
                        if (globalScale > 1.2) {
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                            ctx.fillText(label, node.x, node.y + 10);
                        }
                    }}
                    onNodeClick={(node) => {
                        setSelectedNode(node);
                        fgRef.current?.centerAt(node.x, node.y, 400);
                    }}
                    onBackgroundClick={() => setSelectedNode(null)}
                    width={window.innerWidth}
                    height={window.innerHeight}
                />
            </div>

            {/* Sidebar / Node Details */}
            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        initial={{ x: 400, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 400, opacity: 0 }}
                        className="absolute right-0 top-0 bottom-0 w-96 glass-panel border-l border-white/5 bg-slate-900/80 backdrop-blur-xl z-[60] p-8 overflow-y-auto"
                    >
                        <div className="flex justify-between items-start mb-8">
                            <div className={`px-3 py-1 rounded-full text-[10px] uppercase font-bold tracking-widest bg-opacity-20`} style={{ backgroundColor: getColor(selectedNode.label), color: getColor(selectedNode.label) }}>
                                {selectedNode.label}
                            </div>
                            <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white transition-colors">
                                <ArrowLeft className="w-5 h-5 rotate-180" />
                            </button>
                        </div>

                        <h2 className="text-3xl font-bold text-white mb-2">{selectedNode.name}</h2>
                        
                        <div className="space-y-6 mt-8">
                            <div>
                                <h4 className="text-xs uppercase font-bold text-slate-500 tracking-widest mb-3 flex items-center gap-2">
                                    <Info className="w-3 h-3" /> Свойства узла
                                </h4>
                                <div className="space-y-2">
                                    {Object.entries(selectedNode.properties || {}).map(([key, value]: [string, any]) => (
                                        <div key={key} className="glass-panel p-3 rounded-xl border border-white/5 bg-slate-800/20">
                                            <span className="text-[10px] text-slate-500 block uppercase mb-1">{key}</span>
                                            <span className="text-sm text-slate-200 break-words">{String(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="p-4 rounded-2xl bg-primary-500/10 border border-primary-500/20">
                                <div className="flex items-center gap-2 mb-2">
                                    <Zap className="w-4 h-4 text-primary-400" />
                                    <span className="text-sm font-bold text-primary-300">Синапс завершен</span>
                                </div>
                                <p className="text-xs text-slate-400 leading-relaxed">
                                    Этот узел является частью долгосрочной памяти агента. Все связи графа Neo4j участвуют в RAG-поиске при принятии решений.
                                </p>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Legend Footer */}
            <div className="absolute bottom-6 left-6 z-50 flex gap-4 pointer-events-none">
                <div className="glass-panel px-4 py-3 rounded-2xl border border-white/5 flex gap-6 pointer-events-auto bg-slate-900/40">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-[#60a5fa]" /> Agent
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-[#34d399]" /> Location
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-[#a78bfa]" /> Organization
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-[#fbbf24]" /> Item
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-2 h-2 rounded-full bg-[#f87171]" /> Goal
                    </div>
                </div>
            </div>
        </div>
    );
}
