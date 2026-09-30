import { Dialog as DialogPrimitive } from '@base-ui/react/dialog';
import type { CSSProperties, ReactNode } from 'react';
import { rarityStyle, type Tier } from '../core/rarity';

export interface WinnerOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tier: Tier;
  /** Small caps label, e.g. "NEW ITEM" / "VẬT PHẨM MỚI". */
  label: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  art: ReactNode;
  /** Use .tn-action--primary, .tn-action--app (touch-only deep link) and .tn-action--text children. */
  actions?: ReactNode;
  /** Needed only when the theme is set on a wrapper instead of <html> (the popup is portaled to <body>). */
  theme?: string;
  /** A theme's own colour for this tier; defaults to the CS:GO ladder. */
  color?: string;
}

/** Fullscreen "NEW ITEM" reveal: blurred page behind, rarity glow under the art, actions under a hairline. */
export function WinnerOverlay({ open, onOpenChange, tier, label, title, description, art, actions, theme, color }: WinnerOverlayProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={next => onOpenChange(next)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop className="tn-dialog-backdrop" />
        <DialogPrimitive.Popup className="tn-winner" data-tn-theme={theme} style={(color ? { '--tn-rarity': color } : rarityStyle(tier)) as CSSProperties}>
          <span className="tn-winner-label">{label}</span>
          <DialogPrimitive.Title className="tn-winner-title">{title}</DialogPrimitive.Title>
          {description && <DialogPrimitive.Description className="tn-winner-desc">{description}</DialogPrimitive.Description>}
          <div className="tn-winner-art">{art}</div>
          {actions && <div className="tn-winner-actions">{actions}</div>}
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
