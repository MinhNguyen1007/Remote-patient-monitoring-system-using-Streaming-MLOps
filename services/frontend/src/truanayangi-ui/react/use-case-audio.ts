import { useCallback, useEffect, useRef, useState } from 'react';
import { CaseAudio, ORIGINAL_SFX_FILES, SUPPLY_SFX_FILES, type AudioSource, type SfxName } from '../core/case-audio';
import { REVEAL_SOUND_BY_TIER, type Tier } from '../core/rarity';

/**
 * 'original' = Valve CS:GO files (personal/prototype only), 'supply' = truanayangi.com's BOOM Library set
 * (local dev server only, never in a build), 'synth' = royalty-free synthesized set.
 */
export type SoundMode = 'original' | 'supply' | 'synth';

export type SoundUrls = Partial<Record<SfxName | 'silence', string>>;

function sourceFor(mode: SoundMode, baseUrl: string, urls?: SoundUrls): AudioSource {
  if (mode === 'synth') return { type: 'synth' };
  const files = mode === 'supply' ? SUPPLY_SFX_FILES : ORIGINAL_SFX_FILES;
  return { type: 'files', url: name => urls?.[name] ?? `${baseUrl}/${files[name]}`, silenceUrl: urls?.silence ?? `${baseUrl}/silence.mp3` };
}

export interface UseCaseAudioOptions {
  mode?: SoundMode;
  /** Folder that holds the files when mode = 'original' or 'supply'. */
  baseUrl?: string;
  /** Explicit URLs (e.g. Vite asset imports, which become data URIs in a single-file build). */
  urls?: SoundUrls;
  initialMuted?: boolean;
  volume?: number;
}

/**
 * Engine lifecycle: preload on mount (off the click path), pause when the tab hides,
 * recover when it shows, dispose on unmount. Call `unlock()` synchronously in the click
 * that starts the spin, before any await.
 */
export function useCaseAudio({ mode = 'synth', baseUrl = '/sounds', urls, initialMuted = false, volume }: UseCaseAudioOptions = {}) {
  const engine = useRef<CaseAudio | null>(null);
  const firstSource = useRef(true);
  const [muted, setMutedState] = useState(initialMuted);

  useEffect(() => {
    const audio = new CaseAudio({ source: sourceFor(mode, baseUrl, urls), volume });
    engine.current = audio;
    if (initialMuted) audio.setMuted(true);
    audio.preload();
    const onVisibility = () => { if (document.hidden) audio.pause(); else audio.recover(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      audio.dispose();
      engine.current = null;
    };
    // The engine lives for the component's lifetime; source changes are applied below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (firstSource.current) { firstSource.current = false; return; }
    engine.current?.setSource(sourceFor(mode, baseUrl, urls));
  }, [mode, baseUrl, urls]);

  const unlock = useCallback(() => engine.current?.unlock(), []);
  const play = useCallback((name: SfxName) => engine.current?.play(name), []);
  const playReveal = useCallback((tier: Tier) => engine.current?.play(REVEAL_SOUND_BY_TIER[tier]), []);
  /** Call from the mute button's click so unmuting also unlocks audio. */
  const setMuted = useCallback((next: boolean) => { engine.current?.setMuted(next); setMutedState(next); }, []);

  return { unlock, play, playReveal, muted, setMuted };
}
