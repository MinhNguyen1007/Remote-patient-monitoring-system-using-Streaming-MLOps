import { describe, expect, it } from 'vitest';

import { appendTimeline, applyNewAlert, applyPrediction, latestFromEvent, timelinePointFromEvent } from '@/lib/realtime';
import { timeAgo, vn } from '@/lib/format';

import { latest, patient, prediction } from './fixtures';

describe('applyPrediction — dashboard cập nhật realtime', () => {
  it('cập nhật đúng bệnh nhân, nối dải 12 giờ và sắp lại theo rủi ro', () => {
    const list = [patient('a', { latest: latest({ risk_level: 'WARNING', risk_score: 0.2 }) }), patient('b')];
    const next = applyPrediction(list, prediction('b'));
    expect(next.map((p) => p.id)).toEqual(['b', 'a']); // b vừa thành CRITICAL → lên đầu
    expect(next[0].latest?.risk_level).toBe('CRITICAL');
    expect(next[0].recent_risk_levels).toEqual(['NORMAL', 'CRITICAL']);
    expect(list[1].latest?.risk_level).toBe('NORMAL'); // không sửa mảng cũ
  });

  it('bỏ qua bệnh nhân không có trong danh sách và giờ cũ hơn/đã có', () => {
    const list = [patient('a')];
    expect(applyPrediction(list, prediction('x'))).toBe(list);
    expect(applyPrediction(list, prediction('a', { hour_index: 10 }))).toBe(list);
  });

  it('dải rủi ro giữ tối đa 12 giờ', () => {
    const list = [patient('a', { recent_risk_levels: Array(12).fill('NORMAL') })];
    const next = applyPrediction(list, prediction('a'));
    expect(next[0].recent_risk_levels).toHaveLength(12);
    expect(next[0].recent_risk_levels.at(-1)).toBe('CRITICAL');
  });

  it('cảnh báo mới tăng số cảnh báo mở của đúng bệnh nhân', () => {
    const next = applyNewAlert([patient('a'), patient('b')], 'b');
    expect(next.map((p) => p.open_alerts)).toEqual([0, 1]);
  });
});

describe('dữ liệu từ sự kiện prediction', () => {
  it('latest dùng vitals đã forward-fill, biểu đồ dùng vitals đo gốc', () => {
    const event = prediction('a');
    expect(latestFromEvent(event).temperature).toBe(38.1);
    expect(timelinePointFromEvent(event).temperature).toBeNull();
  });

  it('appendTimeline thêm giờ mới, giữ cửa sổ đang xem, bỏ giờ trùng', () => {
    const points = [latestFromEvent(prediction('a', { hour_index: 9 })), latestFromEvent(prediction('a', { hour_index: 10 }))];
    expect(appendTimeline(points, prediction('a', { hour_index: 11 }), 2).map((p) => p.hour_index)).toEqual([10, 11]);
    expect(appendTimeline(points, prediction('a', { hour_index: 10 }), 48)).toBe(points);
  });
});

describe('định dạng', () => {
  it('số thập phân dấu phẩy và thời gian tương đối', () => {
    expect(vn(0.7234)).toBe('0,72');
    expect(vn(null)).toBe('—');
    expect(timeAgo('2026-09-11T05:30:00Z', Date.parse('2026-09-11T05:32:00Z'))).toBe('2 phút trước');
  });
});
