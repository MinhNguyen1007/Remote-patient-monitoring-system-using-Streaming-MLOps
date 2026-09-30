import { useCallback, useEffect, useState } from 'react';

import { readMuted, writeMuted } from '@/lib/soundPref';
import type { Tier } from '@/truanayangi-ui/core/rarity';
import { useCaseAudio } from '@/truanayangi-ui/react/use-case-audio';

export interface AlertSound {
  muted: boolean;
  /** false khi trình duyệt không cho lưu lựa chọn (chỉ còn trong phiên này). */
  saved: boolean;
  toggle: () => void;
  play: (tier: Tier) => void;
}

/**
 * Âm báo tổng hợp (Web Audio, không dùng tệp âm thanh có bản quyền). Trình duyệt chỉ cho phát âm sau một thao tác
 * của người dùng: mở khoá ngay trong lần chạm/bấm phím đầu tiên, đồng bộ trong chính sự kiện đó.
 * Engine tự dừng khi tab ẩn và tiếp tục khi tab hiện lại.
 */
export function useAlertSound(): AlertSound {
  const [initialMuted] = useState(readMuted);
  const [saved, setSaved] = useState(true);
  const audio = useCaseAudio({ mode: 'synth', initialMuted });
  const { unlock, playReveal, setMuted, muted } = audio;

  useEffect(() => {
    const onFirstGesture = () => {
      unlock();
      window.removeEventListener('pointerdown', onFirstGesture, true);
      window.removeEventListener('keydown', onFirstGesture, true);
    };
    window.addEventListener('pointerdown', onFirstGesture, true);
    window.addEventListener('keydown', onFirstGesture, true);
    return () => {
      window.removeEventListener('pointerdown', onFirstGesture, true);
      window.removeEventListener('keydown', onFirstGesture, true);
    };
  }, [unlock]);

  const toggle = useCallback(() => {
    const next = !muted;
    setMuted(next); // bật lại tiếng cũng mở khoá âm thanh ngay trong cú bấm này
    setSaved(writeMuted(next));
  }, [muted, setMuted]);

  return { muted, saved, toggle, play: playReveal };
}
