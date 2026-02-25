import type { LayoutPreset, LayoutPresetId } from './layoutPresets.types';

export function pickPresetById(
  presets: LayoutPreset[],
  id: LayoutPresetId
): LayoutPreset | undefined {
  return presets.find((preset) => preset.id === id);
}

export function pickRecommendedPreset(
  presets: LayoutPreset[],
  aspectRatio: string
): LayoutPreset {
  switch (aspectRatio) {
    case '21:9':
      return pickPresetById(presets, '21:9') ?? presets[0];
    case '4:3':
      return pickPresetById(presets, '4:3') ?? presets[0];
    case 'portrait':
      return pickPresetById(presets, 'compact') ?? presets[0];
    default:
      return pickPresetById(presets, '16:9') ?? presets[0];
  }
}
