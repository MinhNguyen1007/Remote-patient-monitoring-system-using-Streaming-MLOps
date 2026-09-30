// Web Audio engine for the case-opening moment (generalized from truanayangi's CaseAudio).
// One gesture-unlocked AudioContext, decoded buffers reused for every tick, never
// one <audio> element per sound. Sources: the original files or synthesized buffers.

import { synthesizeSfx } from './sfx-synth';

export type SfxName = 'open' | 'tick' | 'reveal-rare' | 'reveal-mythical' | 'reveal-legendary' | 'reveal-unique' | 'reveal-ancient';
export const SFX_NAMES: readonly SfxName[] = ['open', 'tick', 'reveal-rare', 'reveal-mythical', 'reveal-legendary', 'reveal-unique', 'reveal-ancient'];

/** File names of the original Valve CS:GO sounds (assets/original/sounds). Personal/prototype use only. */
export const ORIGINAL_SFX_FILES: Record<SfxName, string> = {
  open: 'csgo_ui_crate_open.mp3',
  tick: 'csgo_ui_crate_item_scroll.mp3',
  'reveal-rare': 'item_reveal3_rare.mp3',
  'reveal-mythical': 'item_reveal4_mythical.mp3',
  'reveal-legendary': 'item_reveal5_legendary.mp3',
  // CS:GO has no fifth stinger: tiers 3 and 4 share the top one, exactly like the original.
  'reveal-unique': 'item_reveal6_ancient.mp3',
  'reveal-ancient': 'item_reveal6_ancient.mp3',
};

/**
 * truanayangi.com's supply set (public/sounds/supply): BOOM Library "Magic UI Designed", All Rights
 * Reserved and licensed to them, not us. Local dev server only; every build drops and refuses it
 * (licensed-audio.json). Five distinct stingers, Normal → Magic → Rare → Unique → Godmode.
 */
export const SUPPLY_SFX_FILES: Record<SfxName, string> = {
  open: 'opening.mp3',
  tick: 'tick.mp3',
  'reveal-rare': 'reveal.mp3',
  'reveal-mythical': 'reveal-mythical.mp3',
  'reveal-legendary': 'reveal-legendary.mp3',
  'reveal-unique': 'reveal-orange.mp3',
  'reveal-ancient': 'reveal-ancient.mp3',
};

export type AudioSource =
  | { type: 'files'; url: (name: SfxName) => string; silenceUrl?: string }
  | { type: 'synth' };

export interface CaseAudioOptions {
  source: AudioSource;
  /** Master gain; the original used 0.65. */
  volume?: number;
}

export class CaseAudio {
  private context?: AudioContext;
  private gain?: GainNode;
  private buffers = new Map<SfxName, AudioBuffer>();
  private requests = new Map<SfxName, Promise<ArrayBuffer>>();
  private decoding = new Map<SfxName, Promise<void>>();
  private sources = new Set<AudioBufferSourceNode>();
  private legacyRoute?: HTMLAudioElement;
  private muted = false;
  private disposed = false;
  private activated = false;
  private generation = 0;

  constructor(private options: CaseAudioOptions) {}

  get isMuted() { return this.muted; }

  /** Decode off the click path; playback still needs a user gesture (unlock). */
  preload() {
    try { this.prepareContext(); } catch { /* retried on the next gesture */ }
    for (const name of SFX_NAMES) {
      const pending = this.context ? this.decode(name) : this.options.source.type === 'files' ? this.fetchSound(name) : Promise.resolve();
      void pending.catch(() => {});
    }
  }

  /** Call synchronously inside the click/tap handler, before any await (Safari/iOS activation). */
  unlock() {
    if (this.disposed || this.muted) return;
    this.activated = true;
    try {
      const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
      if (session) session.type = 'playback';
      this.prepareContext();
      if (!this.context) return;
      // Older iOS routes Web Audio through the ringer switch. One looping silent
      // media element moves it to the media route; never one player per tick.
      if (!session && /iP(hone|ad|od)/.test(navigator.userAgent)) {
        this.legacyRoute ??= new Audio(this.options.source.type === 'files' && this.options.source.silenceUrl ? this.options.source.silenceUrl : silentWavDataUri());
        this.legacyRoute.loop = true;
        void this.legacyRoute.play().catch(() => {});
      }
      void this.context.resume().catch(() => {});
      const pulse = this.context.createBufferSource();
      pulse.buffer = this.context.createBuffer(1, 1, this.context.sampleRate);
      pulse.connect(this.gain!);
      pulse.onended = () => pulse.disconnect();
      pulse.start();
      for (const name of SFX_NAMES) void this.decode(name).catch(() => {});
    } catch { /* audio never blocks the reel; the next gesture retries */ }
  }

  /** Re-unlock after the tab becomes visible again. */
  recover() { if (this.activated && this.context && !this.muted) this.unlock(); }

  play(name: SfxName) {
    if (this.disposed || this.muted || document.hidden || !this.context) return;
    const buffer = this.buffers.get(name);
    if (!buffer) {
      // Drop stale ticks; open/reveal may wait briefly for their first decode.
      if (name !== 'tick') {
        const generation = this.generation, deadline = performance.now() + 1200;
        void this.decode(name).then(() => { if (generation === this.generation && performance.now() < deadline) this.play(name); }).catch(() => {});
      }
      return;
    }
    if (this.context.state !== 'running') return;
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gain!);
    this.sources.add(source);
    source.onended = () => { source.disconnect(); this.sources.delete(source); };
    source.start();
  }

  setMuted(muted: boolean) {
    this.muted = muted;
    if (this.gain) this.gain.gain.value = muted ? 0 : this.options.volume ?? 0.65;
    if (muted) this.pause(); else this.unlock();
  }

  /** Swap between original files and synthesized sounds at runtime. */
  setSource(source: AudioSource) {
    this.pause();
    this.options = { ...this.options, source };
    this.buffers.clear(); this.requests.clear(); this.decoding.clear();
    this.legacyRoute?.pause(); this.legacyRoute = undefined;
    if (this.context) for (const name of SFX_NAMES) void this.decode(name).catch(() => {});
  }

  pause() {
    this.generation++;
    for (const source of this.sources) { try { source.stop(); } catch { /* already stopped */ } source.disconnect(); }
    this.sources.clear();
    this.legacyRoute?.pause();
  }

  dispose() {
    this.disposed = true;
    this.pause();
    void this.context?.close().catch(() => {});
  }

  private prepareContext() {
    if (this.context) return;
    const Constructor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Constructor) return;
    this.context = new Constructor();
    this.gain = this.context.createGain();
    this.gain.gain.value = this.muted ? 0 : this.options.volume ?? 0.65;
    this.gain.connect(this.context.destination);
  }

  private fetchSound(name: SfxName) {
    const source = this.options.source;
    if (source.type !== 'files') return Promise.reject(new Error('Synth source has no files'));
    let request = this.requests.get(name);
    if (!request) {
      request = fetch(source.url(name)).then(r => { if (!r.ok) throw new Error(`SFX ${r.status}`); return r.arrayBuffer(); });
      this.requests.set(name, request);
      void request.catch(() => this.requests.delete(name));
    }
    return request;
  }

  private decode(name: SfxName) {
    const context = this.context;
    if (!context || this.buffers.has(name)) return Promise.resolve();
    let pending = this.decoding.get(name);
    if (!pending) {
      const source = this.options.source;
      const make = source.type === 'files'
        ? this.fetchSound(name).then(data => context.decodeAudioData(data.slice(0)))
        : synthesizeSfx(name, context.sampleRate);
      pending = make.then(buffer => { if (!this.disposed && this.options.source === source) this.buffers.set(name, buffer); });
      this.decoding.set(name, pending);
      void pending.finally(() => this.decoding.delete(name)).catch(() => {});
    }
    return pending;
  }
}

/** 1 s of 8 kHz mono silence as a WAV data URI (iOS media-route keeper when no silence file is shipped). */
export function silentWavDataUri(seconds = 1): string {
  const rate = 8000, samples = rate * seconds, bytes = new Uint8Array(44 + samples * 2), view = new DataView(bytes.buffer);
  const text = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) bytes[offset + i] = value.charCodeAt(i); };
  text(0, 'RIFF'); view.setUint32(4, 36 + samples * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, samples * 2, true);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:audio/wav;base64,${btoa(binary)}`;
}
