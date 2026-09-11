const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const SUPPORTED_VERSION = '8.17.0';
const SCHEMA_VERSION = '12.4.10';
const GRID = [
  { name: 'GRID_CELL_HEIGHT', original: 30, value: 20 },
  { name: 'GRID_CELL_VMARGIN', original: 8, value: 4 },
  { name: 'GRID_COLUMN_COUNT', original: 24, value: 60 },
];
const TARGETS = ['dist/esm/components/layout/grid/constants.js', 'dist/index.js'];
const TABLE_TARGETS = ['index.js', 'PanelOptionsBuilders.js', 'VizConfigBuilders.js']
  .map((name) => `dist/esm/core/PanelBuilders/${name}`);
const OLD_TABLE_IMPORT = "import { defaultOptions as defaultOptions$2 } from '@grafana/schema/dist/esm/raw/composable/table/panelcfg/x/TablePanelCfg_types.gen';";
const NEW_TABLE_IMPORT = "import { defaultTableOptions as defaultOptions$2 } from '@grafana/schema';";
const OLD_TABLE_REFERENCE = 'TablePanelCfg_types_gen.defaultOptions';
const NEW_TABLE_REFERENCE = 'schema.defaultTableOptions';

function replaceExactly(source, original, replacement, count, label) {
  const oldCount = source.split(original).length - 1;
  const newCount = source.split(replacement).length - 1;
  if (oldCount === count && newCount === 0) return source.split(original).join(replacement);
  if (oldCount === 0 && newCount === count) return source;
  throw new Error(`[patch] Unsupported table defaults reference: ${label}`);
}

function transformTable(source, label, commonjs = false) {
  if (commonjs) {
    if (source.split("var schema = require('@grafana/schema');").length !== 2) {
      throw new Error(`[patch] Unsupported schema namespace: ${label}`);
    }
    return replaceExactly(source, OLD_TABLE_REFERENCE, NEW_TABLE_REFERENCE, 3, label);
  }
  return replaceExactly(source, OLD_TABLE_IMPORT, NEW_TABLE_IMPORT, 1, label);
}

function transformGrid(source, label) {
  let result = source;
  for (const { name, original, value } of GRID) {
    const pattern = new RegExp(`const ${name} = (\\d+);`, 'g');
    const matches = [...source.matchAll(pattern)];
    if (matches.length !== 1 || ![original, value].includes(Number(matches[0][1]))) {
      throw new Error(`[patch] Unsupported ${name} declaration: ${label}`);
    }
    result = result.replace(pattern, `const ${name} = ${value};`);
  }
  return result;
}

function patchScenes(packageRoot, schemaRoot = path.join(packageRoot, '../schema')) {
  const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'));
  if (manifest.version !== SUPPORTED_VERSION) {
    throw new Error(`[patch] Revalidate Scenes before upgrading: expected ${SUPPORTED_VERSION}, got ${manifest.version}`);
  }
  const schemaManifest = JSON.parse(fs.readFileSync(path.join(schemaRoot, 'package.json'), 'utf8'));
  if (schemaManifest.version !== SCHEMA_VERSION) {
    throw new Error(`[patch] Revalidate schema before upgrading: expected ${SCHEMA_VERSION}, got ${schemaManifest.version}`);
  }
  // Schema 12.4 moved table defaults to this public export. Preserve the upstream values,
  // not an invented empty fallback. Scenes 8.17 still references the removed private export.
  assert.deepEqual(require(schemaRoot).defaultTableOptions, {
    cellHeight: 'sm', frameIndex: 0, showHeader: true, showTypeIcons: false, sortBy: [],
  }, '[patch] Revalidate upstream table defaults');
  // Validate every target before writing any file; drift is never a successful install.
  const changes = TARGETS.map((relative) => {
    const file = path.join(packageRoot, relative);
    const original = fs.readFileSync(file, 'utf8');
    const grid = transformGrid(original, relative);
    return { file, original, next: relative === 'dist/index.js' ? transformTable(grid, relative, true) : grid };
  });
  for (const relative of TABLE_TARGETS) {
    const file = path.join(packageRoot, relative);
    const original = fs.readFileSync(file, 'utf8');
    changes.push({ file, original, next: transformTable(original, relative) });
  }
  for (const { file, original, next } of changes) {
    if (next !== original) fs.writeFileSync(file, next, 'utf8');
    if (fs.readFileSync(file, 'utf8') !== next) throw new Error(`[patch] Verification failed: ${file}`);
    console.log(`[patch] verified Scenes grid/table compatibility: ${file}`);
  }
}

if (require.main === module) {
  patchScenes(path.resolve(__dirname, '../node_modules/@grafana/scenes'));
}
module.exports = { transformGrid, transformTable, patchScenes, TARGETS, TABLE_TARGETS,
  SUPPORTED_VERSION, SCHEMA_VERSION, OLD_TABLE_IMPORT, NEW_TABLE_IMPORT };
