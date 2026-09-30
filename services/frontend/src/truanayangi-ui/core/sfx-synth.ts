// Royalty-free sounds synthesized with OfflineAudioContext, shaped after the
// measured character of the original CS:GO files (they are inspired by, not
// copies of, the originals):
//   tick   0.58 s file, transient < 50 ms, bright ring ≈ 4.56 kHz, centroid ≈ 6.8 kHz
//   open   1.52 s, loud first 200 ms, mechanical latch + rumble, centroid ≈ 3.9 kHz
//   reveal 4.4–5.4 s stingers, peak at 100–350 ms then shimmer and long decay,
//          brighter and denser for higher tiers
// Rendering is deterministic (seeded noise), so every page load sounds the same.

import type { SfxName } from './case-audio';

type Out = AudioNode;

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function noise(ctx: BaseAudioContext, seconds: number, random: () => number) {
  const buffer = ctx.createBuffer(1, Math.max(1, Math.ceil(seconds * ctx.sampleRate)), ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = random() * 2 - 1;
  return buffer;
}

function envelope(ctx: BaseAudioContext, at: number, peak: number, attack: number, decay: number) {
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0, at);
  gain.gain.linearRampToValueAtTime(peak, at + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
  return gain;
}

function burst(ctx: BaseAudioContext, outs: Out[], random: () => number, o: { at: number; duration: number; filter: BiquadFilterType; freq: number; freqTo?: number; q?: number; gain: number; attack?: number }) {
  const src = ctx.createBufferSource();
  src.buffer = noise(ctx, o.duration + 0.05, random);
  const filter = ctx.createBiquadFilter();
  filter.type = o.filter;
  filter.frequency.setValueAtTime(o.freq, o.at);
  if (o.freqTo) filter.frequency.exponentialRampToValueAtTime(o.freqTo, o.at + o.duration);
  filter.Q.value = o.q ?? 0.8;
  const env = envelope(ctx, o.at, o.gain, o.attack ?? 0.002, o.duration);
  src.connect(filter).connect(env);
  outs.forEach(out => env.connect(out));
  src.start(o.at);
  src.stop(o.at + o.duration + 0.05);
}

function tone(ctx: BaseAudioContext, outs: Out[], o: { at: number; freq: number; type?: OscillatorType; gain: number; attack?: number; decay: number; glideTo?: number; glideTime?: number; detune?: number }) {
  const osc = ctx.createOscillator();
  osc.type = o.type ?? 'sine';
  osc.frequency.setValueAtTime(o.freq, o.at);
  if (o.glideTo) osc.frequency.exponentialRampToValueAtTime(o.glideTo, o.at + (o.glideTime ?? o.decay));
  if (o.detune) osc.detune.value = o.detune;
  const env = envelope(ctx, o.at, o.gain, o.attack ?? 0.003, o.decay);
  osc.connect(env);
  outs.forEach(out => env.connect(out));
  osc.start(o.at);
  osc.stop(o.at + (o.attack ?? 0.003) + o.decay + 0.05);
}

function room(ctx: BaseAudioContext, out: Out, random: () => number, seconds: number, power: number, mix: number) {
  const length = Math.ceil(seconds * ctx.sampleRate);
  const impulse = ctx.createBuffer(2, length, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const data = impulse.getChannelData(ch);
    for (let i = 0; i < length; i++) data[i] = (random() * 2 - 1) * Math.pow(1 - i / length, power);
  }
  const convolver = ctx.createConvolver();
  convolver.buffer = impulse;
  const wet = ctx.createGain();
  wet.gain.value = mix;
  convolver.connect(wet).connect(out);
  return convolver;
}

const REVEALS = {
  'reveal-rare': { seconds: 3.2, root: 440, chord: [1, 5 / 4, 3 / 2, 2], shimmer: 5, boom: 0.5, bright: 2600, seed: 31 },
  'reveal-mythical': { seconds: 4.0, root: 493.88, chord: [1, 5 / 4, 3 / 2, 15 / 8, 2], shimmer: 7, boom: 0.6, bright: 3200, seed: 41 },
  'reveal-legendary': { seconds: 3.6, root: 554.37, chord: [1, 9 / 8, 5 / 4, 3 / 2, 2], shimmer: 9, boom: 0.7, bright: 3800, seed: 59 },
  'reveal-unique': { seconds: 4.2, root: 587.33, chord: [1, 5 / 4, 3 / 2, 2, 5 / 2], shimmer: 10, boom: 0.78, bright: 4000, seed: 67 },
  'reveal-ancient': { seconds: 4.6, root: 587.33, chord: [1, 5 / 4, 3 / 2, 15 / 8, 2, 5 / 2], shimmer: 12, boom: 0.85, bright: 4400, seed: 73 },
} as const;

const SECONDS: Record<SfxName, number> = { tick: 0.25, open: 1.3, ...Object.fromEntries(Object.entries(REVEALS).map(([k, v]) => [k, v.seconds])) } as Record<SfxName, number>;

function build(name: SfxName, ctx: BaseAudioContext, out: Out) {
  if (name === 'tick') {
    const random = mulberry32(7);
    burst(ctx, [out], random, { at: 0, duration: 0.012, filter: 'highpass', freq: 2500, q: 0.7, gain: 0.9, attack: 0.001 });
    tone(ctx, [out], { at: 0, freq: 4560, gain: 0.35, attack: 0.001, decay: 0.06 });
    tone(ctx, [out], { at: 0, freq: 6840, gain: 0.18, attack: 0.001, decay: 0.03 });
    tone(ctx, [out], { at: 0, freq: 1150, type: 'triangle', gain: 0.25, attack: 0.001, decay: 0.018 });
    return;
  }
  if (name === 'open') {
    const random = mulberry32(19);
    const wet = room(ctx, out, random, 0.6, 3, 0.18);
    burst(ctx, [out, wet], random, { at: 0, duration: 0.03, filter: 'bandpass', freq: 3200, q: 1.2, gain: 1 });
    tone(ctx, [out], { at: 0, freq: 95, glideTo: 48, glideTime: 0.14, gain: 0.9, decay: 0.25 });
    burst(ctx, [out, wet], random, { at: 0.085, duration: 0.05, filter: 'bandpass', freq: 1800, q: 1.5, gain: 0.8 });
    burst(ctx, [out, wet], random, { at: 0.16, duration: 0.025, filter: 'bandpass', freq: 4200, q: 3, gain: 0.45 });
    burst(ctx, [out, wet], random, { at: 0.215, duration: 0.02, filter: 'bandpass', freq: 3600, q: 3, gain: 0.35 });
    burst(ctx, [out, wet], random, { at: 0.05, duration: 0.9, filter: 'bandpass', freq: 900, freqTo: 3200, q: 0.8, gain: 0.35, attack: 0.18 });
    tone(ctx, [out, wet], { at: 0.09, freq: 620, type: 'triangle', gain: 0.12, decay: 0.35 });
    tone(ctx, [wet], { at: 0.09, freq: 1240, gain: 0.06, decay: 0.5 });
    return;
  }
  const spec = REVEALS[name];
  const random = mulberry32(spec.seed);
  const wet = room(ctx, out, random, 2.8, 2.2, 0.35);
  burst(ctx, [out, wet], random, { at: 0, duration: 0.08, filter: 'highpass', freq: 1500, gain: 0.7 });
  tone(ctx, [out], { at: 0, freq: 70, glideTo: 45, glideTime: 0.3, gain: spec.boom, decay: 0.6 });
  spec.chord.forEach((ratio, i) => {
    tone(ctx, [out, wet], { at: 0.02 + i * 0.015, freq: spec.root * ratio, type: 'triangle', gain: 0.16, attack: 0.01, decay: spec.seconds * 0.55 });
    tone(ctx, [wet], { at: 0.02 + i * 0.015, freq: spec.root * ratio * 2, gain: 0.05, attack: 0.01, decay: spec.seconds * 0.45, detune: 6 });
  });
  for (let k = 0; k < spec.shimmer; k++) {
    tone(ctx, [out, wet], { at: 0.12 + k * 0.07, freq: spec.bright * (1 + ((k * 5) % 7) / 10), gain: 0.06, attack: 0.003, decay: 0.35 });
  }
  burst(ctx, [wet], random, { at: 0.1, duration: 1.2, filter: 'bandpass', freq: spec.bright * 1.5, q: 0.7, gain: 0.08, attack: 0.05 });
}

export async function synthesizeSfx(name: SfxName, sampleRate = 44100): Promise<AudioBuffer> {
  const ctx = new OfflineAudioContext(2, Math.ceil(SECONDS[name] * sampleRate), sampleRate);
  const master = ctx.createGain();
  master.connect(ctx.destination);
  build(name, ctx, master);
  const buffer = await ctx.startRendering();
  let peak = 0;
  for (let ch = 0; ch < buffer.numberOfChannels; ch++) for (const v of buffer.getChannelData(ch)) peak = Math.max(peak, Math.abs(v));
  const scale = peak > 0 ? 0.9 / peak : 1;
  for (let ch = 0; ch < buffer.numberOfChannels; ch++) { const data = buffer.getChannelData(ch); for (let i = 0; i < data.length; i++) data[i] *= scale; }
  return buffer;
}
