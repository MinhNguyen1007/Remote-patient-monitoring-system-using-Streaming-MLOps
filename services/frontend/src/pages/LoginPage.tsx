import { Eye, EyeOff, Lock, Mail, OctagonAlert } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { homeFor } from '@/app/routes';
import { RiskBadge } from '@/components/clinical';
import { Logo } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';

/** UC01 — lỗi hiển thị ngay dưới nút Đăng nhập (02_8 mục 2.8.4a), cùng một thông báo cho mọi trường hợp sai. */
export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const signedIn = await login(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== '/login' ? from : homeFor(signedIn.role), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đăng nhập được');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="tn-shell grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <section className="hidden flex-col justify-between border-r border-[#ffffff20] bg-[#101a2350] px-14 py-12 lg:flex">
        <Logo />
        <div className="flex max-w-[520px] flex-col gap-[18px]">
          <div className="eyebrow">Hệ thống giám sát bệnh nhân từ xa</div>
          <h1 className="page-title text-[44px] leading-[1.1]">Cảnh báo sớm nguy kịch trong 4 giờ tới.</h1>
          <p className="m-0 text-[15px] text-pretty text-[#aebbc5]">
            Vitals ICU được phát theo thời gian thực, dự báo rủi ro bằng mô hình học máy và phát hiện diễn biến bất thường so với baseline của chính bệnh nhân.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <RiskBadge level="NORMAL" />
          <RiskBadge level="WARNING" />
          <RiskBadge level="CRITICAL" />
        </div>
      </section>
      <section className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="card flex w-full max-w-[420px] flex-col gap-[22px] p-8" noValidate>
          <div className="flex flex-col gap-1.5">
            <div className="mb-3 lg:hidden">
              <Logo />
            </div>
            <h2 className="m-0 text-[28px] font-normal text-[#e4e8eb]">Đăng nhập</h2>
            <span className="text-[#abb8c2]">Dành cho Bác sĩ, Điều dưỡng và Quản trị viên</span>
          </div>
          <label className="flex flex-col gap-2">
            <span className="text-[12px] text-[#c2c8cd]">Email</span>
            <span className="field">
              <Mail aria-hidden size={16} color="#abb8c2" />
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ten@benhvien.vn"
              />
            </span>
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-[12px] text-[#c2c8cd]">Mật khẩu</span>
            <span className="field">
              <Lock aria-hidden size={16} color="#abb8c2" />
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="flex min-h-8 min-w-8 items-center justify-center text-[#abb8c2] hover:text-white"
                aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </span>
          </label>
          <Button type="submit" disabled={submitting || !email || !password} className="h-[46px] text-[15px]">
            {submitting ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </Button>
          {error && (
            <div role="alert" className="flex items-center gap-2.5 border px-3 py-2.5 text-[13px]" style={{ background: 'color-mix(in srgb, var(--risk-critical) 12%, transparent)', borderColor: 'color-mix(in srgb, var(--risk-critical) 40%, transparent)' }}>
              <OctagonAlert aria-hidden size={16} color="var(--risk-critical)" strokeWidth={2} />
              <span>{error}</span>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}
