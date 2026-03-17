import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import AgentList from './pages/AgentList';
import AgentCreate from './pages/AgentCreate';
import BatchCreate from './pages/BatchCreate';
import StagedCreate from './pages/StagedCreate';
import AgentProfile from './pages/AgentProfile';
import AgentGraphPage from './pages/AgentGraphPage';
import AgentStages from './pages/AgentStages';
import AgentResonance from './pages/AgentResonance';
import SoulLabs from './pages/SoulLabs';
import AuthPage from './pages/AuthPage';
import { Sparkles, Users, Database, Layers, BrainCircuit, Plus, ChevronDown, LogOut } from 'lucide-react';

function App() {
  const token = localStorage.getItem('helixa_auth_token');

  return (
    <Router>
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        
        {/* Full-screen graph page — no navbar, no padding wrapper */}
        <Route path="/agent/:id/graph" element={token ? <AgentGraphPage /> : <AuthPage />} />

        {/* All other pages get the standard navbar + main layout */}
        <Route path="/*" element={token ? <MainLayout /> : <AuthPage />} />
      </Routes>
    </Router>
  );
}

function MainLayout() {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="min-h-screen text-slate-100 flex flex-col">
      {/* Navbar */}
      <nav className="glass-panel sticky top-0 z-50 px-6 py-4 flex justify-between items-center bg-slate-900/80 backdrop-blur-xl border-b border-white/5">
        <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="bg-primary-500/20 p-2 rounded-xl">
            <Database className="w-6 h-6 text-primary-400" />
          </div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
            Helixa
          </h1>
        </Link>

        <div className="flex gap-4 items-center">
          <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors font-medium px-2 py-1">
            <Users className="w-4 h-4" />
            <span>Галерея</span>
          </Link>

          <div className="relative" ref={dropdownRef}>
            <button 
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-5 py-2.5 rounded-2xl transition-all shadow-lg shadow-primary-500/20 font-bold text-sm active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>Создать</span>
              <ChevronDown className={`w-3 h-3 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isDropdownOpen && (
              <div className="absolute right-0 mt-3 w-64 glass-panel border border-white/10 rounded-2xl shadow-2xl p-2 z-[100] animate-in fade-in zoom-in duration-200">
                <Link 
                  to="/staged-create" 
                  onClick={() => setIsDropdownOpen(false)}
                  className="flex items-center gap-3 p-3 hover:bg-white/5 rounded-xl transition-all group"
                >
                  <div className="bg-emerald-500/20 p-2 rounded-lg group-hover:bg-emerald-500/30 transition-colors">
                    <BrainCircuit className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <div className="text-sm font-bold">Одиночный синтез</div>
                    <div className="text-[10px] text-slate-500">Глубокое создание личности</div>
                  </div>
                </Link>

                <Link 
                  to="/batch-create" 
                  onClick={() => setIsDropdownOpen(false)}
                  className="flex items-center gap-3 p-3 hover:bg-white/5 rounded-xl transition-all group"
                >
                  <div className="bg-purple-500/20 p-2 rounded-lg group-hover:bg-purple-500/30 transition-colors">
                    <Layers className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <div className="text-sm font-bold">Групповая партия</div>
                    <div className="text-[10px] text-slate-500">Создание сразу нескольких душ</div>
                  </div>
                </Link>
              </div>
            )}
          </div>

          <button 
            onClick={() => {
              localStorage.removeItem('helixa_auth_token');
              localStorage.removeItem('helixa_user_role');
              window.location.href = '/auth';
            }}
            className="flex items-center gap-2 text-slate-400 hover:text-red-400 transition-colors font-medium px-2 py-1 ml-4"
            title="Выйти"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 mt-4">
        <Routes>
          <Route path="/" element={<AgentList />} />
          <Route path="/create" element={<AgentCreate />} />
          <Route path="/batch-create" element={<BatchCreate />} />
          <Route path="/staged-create" element={<StagedCreate />} />
          <Route path="/agent/:id" element={<AgentProfile />} />
          <Route path="/agent/:id/stages" element={<AgentStages />} />
          <Route path="/agent/:id/resonance" element={<AgentResonance />} />
          <Route path="/agent/:id/labs" element={<SoulLabs />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
