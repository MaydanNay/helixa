import { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

interface GraphData {
    nodes: any[];
    links: any[];
}

const POLL_INTERVAL_MS = 8000; // Poll every 8 seconds if graph is empty
const MAX_POLLS = 15; // Give up after ~2 minutes

export default function AgentGraphView({ agentId }: { agentId: string }) {
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);
    const [polling, setPolling] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const pollCountRef = useRef(0);

    useEffect(() => {
        let timer: ReturnType<typeof setTimeout>;

        const fetchGraph = async () => {
            try {
                const res = await axios.get(`/api/v1/agents/${agentId}/graph`);
                const graphData: GraphData = res.data;

                if (graphData.nodes && graphData.nodes.length > 0) {
                    setData(graphData);
                    setPolling(false);
                    setLoading(false);
                    return; // Done — graph is populated
                }

                // Graph is empty — start polling if not at limit
                if (pollCountRef.current < MAX_POLLS) {
                    pollCountRef.current += 1;
                    setLoading(false);
                    setPolling(true);
                    timer = setTimeout(fetchGraph, POLL_INTERVAL_MS);
                } else {
                    setLoading(false);
                    setPolling(false);
                }
            } catch (err) {
                console.error('Failed to fetch graph:', err);
                setLoading(false);
                setPolling(false);
            }
        };

        fetchGraph();

        return () => clearTimeout(timer);
    }, [agentId]);

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

    if (loading) return (
        <div className="h-64 flex items-center justify-center text-slate-500">
            Загрузка графа...
        </div>
    );

    if (data.nodes.length === 0) return (
        <div className="h-64 flex flex-col items-center justify-center gap-3 text-slate-500 italic">
            <span>
                {polling
                    ? '⏳ Граф знаний генерируется... обновление через 8 сек.'
                    : 'Граф пуст или не инициализирован'}
            </span>
            {polling && (
                <div className="w-48 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-primary-500 animate-pulse rounded-full" style={{ width: `${(pollCountRef.current / MAX_POLLS) * 100}%` }} />
                </div>
            )}
        </div>
    );

    return (
        <div className="glass-panel rounded-2xl border border-white/5 bg-slate-900/40 overflow-hidden" ref={containerRef}>
            <div className="p-4 border-b border-white/5 flex justify-between items-center">
                <h3 className="font-bold text-slate-200 flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
                    Knowledge Graph (Neo4j)
                </h3>
                <div className="flex gap-4 text-[10px] uppercase tracking-widest font-bold text-slate-500">
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-[#60a5fa]" /> Agent</div>
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-[#34d399]" /> Location</div>
                    <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-[#a78bfa]" /> Org</div>
                </div>
            </div>
            <div className="h-[400px] w-full">
                <ForceGraph2D
                    graphData={data}
                    nodeLabel="name"
                    nodeColor={(node: any) => getColor(node.label)}
                    nodeRelSize={6}
                    linkColor={() => 'rgba(255,255,255,0.1)'}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    linkCurvature={0.25}
                    linkLabel="type"
                    onNodeClick={(node: any) => {
                        console.log('Node clicked:', node);
                    }}
                    cooldownTicks={100}
                    width={containerRef.current?.clientWidth || 800}
                    height={400}
                />
            </div>
            <div className="p-2 bg-black/20 text-[10px] text-slate-500 text-center italic">
                Интерактивный граф: можно тянуть узлы, зумить и наводить для подсказок.
            </div>
        </div>
    );
}
