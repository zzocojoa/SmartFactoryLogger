import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import postcss from 'postcss';
import { describe, expect, it } from 'vitest';

const css = postcss.parse(readFileSync(resolve(process.cwd(), 'src/App.css'), 'utf8'));

describe('operator metadata animation cost contract', () => {
  it('keeps continuous motion limited to transform and opacity', () => {
    const names: string[] = [];
    css.walkAtRules('keyframes', (rule) => {
      if (!rule.params.startsWith('operator-alert-')) return;
      names.push(rule.params);
      rule.walkDecls((decl) => {
        expect(['transform', 'opacity']).toContain(decl.prop);
      });
    });
    expect(names).toEqual(['operator-alert-border-wave']);
    const animationValues: string[] = [];
    css.walkRules('.operator-card-alert-ring', (rule) => {
      if (rule.parent?.type !== 'root') return;
      rule.walkDecls('animation', (decl) => { animationValues.push(decl.value); });
    });
    expect(animationValues).toEqual(['operator-alert-border-wave 3.6s linear infinite']);
  });

  it('does not reintroduce blur, masks, blending or animated card shadows', () => {
    css.walkRules((rule) => {
      if (!rule.selector.includes('operator-card-alert')) return;
      rule.walkDecls((decl) => {
        expect(decl.prop).not.toMatch(/^(?:filter|backdrop-filter|(?:-webkit-)?mask.*|mix-blend-mode)$/);
        if (rule.selector.includes('.operator-card.operator-card-alert-active')) {
          if (decl.prop === 'animation') expect(decl.value).toBe('none');
        }
      });
    });
  });

  it('clips noninteractive decoration and keeps an always-visible warning outline', () => {
    const values: Record<string, string> = {};
    css.walkRules('.operator-card-alert-glow', (rule) => {
      rule.walkDecls((decl) => { values[decl.prop] = decl.value; });
    });
    expect(values).toMatchObject({ inset: '0', overflow: 'hidden', contain: 'paint', 'pointer-events': 'none' });
    const outlines: string[] = [];
    css.walkRules('.operator-card.operator-card-alert-active', (rule) => {
      rule.walkDecls('outline', (decl) => { outlines.push(decl.value); });
    });
    expect(outlines.some(value => value.startsWith('2px solid'))).toBe(true);
  });

  it('retains the reduced-motion exception without hiding the missing-input warning', () => {
    let stopsWaves = false;
    let preservesOutline = false;
    css.walkAtRules('media', (media) => {
      if (media.params !== '(prefers-reduced-motion: reduce)') return;
      media.walkRules((rule) => {
        rule.walkDecls((decl) => {
          if (rule.selector === '.operator-card-alert-ring' && decl.prop === 'animation' && decl.value === 'none') stopsWaves = true;
          if (rule.selector.includes('.operator-card.operator-card-alert-active') && decl.prop === 'outline') preservesOutline = true;
        });
      });
    });
    expect(stopsWaves).toBe(true);
    expect(preservesOutline).toBe(true);
  });
});
