// CS:GO rarity ladder as used by truanayangi. Colors are the official CS:GO
// item-grade colors; the gold tier is the "★ Rare Special Item" (knife) slot.

export type Tier = 0 | 1 | 2 | 3 | 4;
export const TIERS: readonly Tier[] = [0, 1, 2, 3, 4];

export const RARITY_COLORS = ['#4b69ff', '#8847ff', '#d32ce6', '#eb4b4b', '#e4ae39'] as const;

export const TIER_NAMES = {
  en: ['MIL-SPEC', 'RESTRICTED', 'CLASSIFIED', 'COVERT', '★ SPECIAL ITEM'],
  vi: ['QUỐC DÂN', 'HIẾM', 'CỰC PHẨM', 'TỐI MẬT', '★ ĐẶC BIỆT'],
} as const;

/** The gold tier is kept secret inside the reel and only revealed in the result. */
export const MYSTERY_TIER: Tier = 4;

export type RevealSound = 'reveal-rare' | 'reveal-mythical' | 'reveal-legendary' | 'reveal-unique' | 'reveal-ancient';
/** Tier → reveal stinger. The CS:GO file set maps 'reveal-unique' to the ancient file, so there the
 *  top two tiers still share one sound, exactly like the original; five-stinger sets keep them apart. */
export const REVEAL_SOUND_BY_TIER: readonly RevealSound[] = ['reveal-rare', 'reveal-mythical', 'reveal-legendary', 'reveal-unique', 'reveal-ancient'];

/**
 * Map any numeric value onto the ladder. The original used lunch price in
 * thousand VND with thresholds ≤40, ≤65, ≤100, ≤130, else gold.
 */
export function tierFor(value: number, thresholds: readonly [number, number, number, number] = [40, 65, 100, 130]): Tier {
  return value <= thresholds[0] ? 0 : value <= thresholds[1] ? 1 : value <= thresholds[2] ? 2 : value <= thresholds[3] ? 3 : 4;
}

/** Inline style that feeds every rarity-aware rule (`--tn-rarity`). */
export function rarityStyle(tier: Tier): Record<'--tn-rarity', string> {
  return { '--tn-rarity': RARITY_COLORS[tier] };
}
