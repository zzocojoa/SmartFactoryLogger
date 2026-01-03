const fs = require('fs');
const path = require('path');

const GRID_COLS = 60;
const GRID_ROW_HEIGHT = 20;
const GRID_MARGIN = 4;

const replacements = [
  { pattern: /const GRID_CELL_HEIGHT = \d+;/g, value: `const GRID_CELL_HEIGHT = ${GRID_ROW_HEIGHT};` },
  { pattern: /const GRID_CELL_VMARGIN = \d+;/g, value: `const GRID_CELL_VMARGIN = ${GRID_MARGIN};` },
  { pattern: /const GRID_COLUMN_COUNT = \d+;/g, value: `const GRID_COLUMN_COUNT = ${GRID_COLS};` },
];

const targets = [
  path.join(
    __dirname,
    '..',
    'node_modules',
    '@grafana',
    'scenes',
    'dist',
    'esm',
    'packages',
    'scenes',
    'src',
    'components',
    'layout',
    'grid',
    'constants.js'
  ),
  path.join(__dirname, '..', 'node_modules', '@grafana', 'scenes', 'dist', 'index.js'),
];

const patchFile = (filePath) => {
  if (!fs.existsSync(filePath)) {
    console.warn(`[patch] skip missing: ${filePath}`);
    return { updated: false, skipped: true };
  }
  const original = fs.readFileSync(filePath, 'utf8');
  let next = original;
  for (const { pattern, value } of replacements) {
    next = next.replace(pattern, value);
  }
  if (next === original) {
    console.log(`[patch] already patched: ${filePath}`);
    return { updated: false, skipped: false, unchanged: true };
  }
  fs.writeFileSync(filePath, next, 'utf8');
  console.log(`[patch] updated: ${filePath}`);
  return { updated: true, skipped: false };
};

let updatedCount = 0;
let skippedCount = 0;
let unchangedCount = 0;

for (const filePath of targets) {
  const result = patchFile(filePath);
  if (result.updated) {
    updatedCount += 1;
  }
  if (result.skipped) {
    skippedCount += 1;
  }
  if (result.unchanged) {
    unchangedCount += 1;
  }
}

if (updatedCount === 0 && skippedCount === 0 && unchangedCount === 0) {
  console.error('[patch] failed to update any files');
  process.exit(1);
}
