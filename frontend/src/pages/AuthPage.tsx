import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { BrainCircuit, Lock, Phone, Eye, EyeOff } from 'lucide-react';

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const API = import.meta.env.VITE_API_URL || '/api/v1';

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Only allow digits and '+' at the start
    const val = e.target.value;
    const digitsOnly = val.replace(/[^\d+]/g, '');
    setPhone(digitsOnly);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const res = await axios.post(`${API}${endpoint}`, { phone, password });
      
      if (res.data.access_token) {
        localStorage.setItem('helixa_auth_token', res.data.access_token);
        localStorage.setItem('helixa_user_role', res.data.role);
        // Force refresh to ensure interceptors and states catch the new token
        window.location.href = '/';
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка авторизации. Проверьте данные.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full glass-panel p-8 rounded-3xl border border-white/10 shadow-2xl relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-0 inset-x-0 h-32 bg-gradient-to-b from-primary-500/20 to-transparent pointer-events-none" />
        
        <div className="flex flex-col items-center mb-8 relative z-10">
          <div className="bg-primary-500/20 p-4 rounded-2xl mb-4 shadow-[0_0_30px_rgba(56,189,248,0.2)] text-primary-400">
            <BrainCircuit className="w-10 h-10" />
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Helixa
          </h1>
          <p className="text-slate-400 text-sm mt-2 text-center">
            Единая микросервисная среда для генерации ДНК ИИ Агентов
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 relative z-10">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl text-sm text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Номер телефона</label>
            <div className="relative">
              <Phone className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input 
                type="tel" 
                value={phone}
                onChange={handlePhoneChange}
                placeholder="+77024383624"
                className="w-full bg-slate-900/50 border border-white/10 rounded-xl py-3 pl-11 pr-4 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/50 transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Пароль</label>
            <div className="relative">
              <Lock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input 
                type={showPassword ? "text" : "password"} 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-900/50 border border-white/10 rounded-xl py-3 pl-11 pr-12 text-white placeholder:text-slate-600 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/50 transition-all"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-gradient-to-r from-primary-600 to-purple-600 hover:from-primary-500 hover:to-purple-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-primary-500/25 active:scale-[0.98] disabled:opacity-50"
          >
            {loading ? 'Загрузка...' : (isLogin ? 'Войти в Систему' : 'Зарегистрировать Душу')}
          </button>
        </form>

        <div className="mt-6 text-center relative z-10">
          <button 
            onClick={() => { setIsLogin(!isLogin); setError(''); }}
            className="text-primary-400 hover:text-primary-300 text-sm font-medium transition-colors"
          >
            {isLogin ? 'Нет аккаунта? Зарегистрироваться' : 'Уже есть аккаунт? Войти'}
          </button>
        </div>
      </div>
    </div>
  );
}
