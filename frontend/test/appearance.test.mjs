import assert from 'node:assert/strict';
import test from 'node:test';
import { accessibleAccent, accentPresets, contrast, defaultAppearance, parseAppearance } from '../.test-build/src/appearance/appearance.mjs';

test('appearance rejects malformed, unsupported and future preferences', () => {
  for (const raw of [null, '', 'bad json', 'null', '[]', '{"version":2,"mode":"dark"}']) assert.deepEqual(parseAppearance(raw), defaultAppearance);
  assert.deepEqual(parseAppearance('{"version":1,"mode":"invalid","accent":"url(test)"}'), defaultAppearance);
  assert.deepEqual(parseAppearance('{"version":1,"mode":"system","accent":"#AAbb00","secret":"ignored"}'), { version: 1, mode: 'system', accent: '#aabb00' });
});

test('all presets and extreme custom colors produce readable text and buttons in both modes', () => {
  for (const dark of [false, true]) {
    for (const color of [...accentPresets.map(preset => preset.color), '#ffffff', '#000000', '#ffff00', '#00ff00', '#ff00ff', '#123456']) {
      const result = accessibleAccent(color, dark);
      assert.ok(contrast(result.accent, dark ? '#1b2528' : '#f4f6f8') >= 5.3, `${color} text in ${dark ? 'dark' : 'light'}`);
      assert.ok(contrast(result.accent, result.foreground) >= 4.5, `${color} button in ${dark ? 'dark' : 'light'}`);
    }
  }
});
