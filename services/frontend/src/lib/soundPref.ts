// Lựa chọn tắt/bật âm báo, nhớ trên trình duyệt này. Đọc lại thì kiểm tra chặt, lỗi thì dùng mặc định (bật âm).
export const SOUND_PREF_KEY = 'rpm-alert-sound-muted';

type Store = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStore(): Store | null {
  try {
    return window.localStorage;
  } catch {
    return null; // trình duyệt chặn lưu trữ
  }
}

export function readMuted(store: Store | null = defaultStore()): boolean {
  try {
    return store?.getItem(SOUND_PREF_KEY) === '1';
  } catch {
    return false;
  }
}

/** Trả về false khi không lưu được, để giao diện nói rõ lựa chọn chỉ còn trong phiên này. */
export function writeMuted(muted: boolean, store: Store | null = defaultStore()): boolean {
  try {
    if (!store) return false;
    store.setItem(SOUND_PREF_KEY, muted ? '1' : '0');
    return true;
  } catch {
    return false;
  }
}
