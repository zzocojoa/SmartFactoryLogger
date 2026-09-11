const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { transformGrid, transformTable, patchScenes, TARGETS, TABLE_TARGETS, SUPPORTED_VERSION,
  SCHEMA_VERSION, OLD_TABLE_IMPORT, NEW_TABLE_IMPORT } = require('./patch_grafana_scenes_grid');
const source = 'const GRID_CELL_HEIGHT = 30;\nconst GRID_CELL_VMARGIN = 8;\nconst GRID_COLUMN_COUNT = 24;\n';
const cjsTable = "var schema = require('@grafana/schema');\n" + 'TablePanelCfg_types_gen.defaultOptions\n'.repeat(3);

test('patches the supported grid and is idempotent', () => {
  const patched = transformGrid(source, 'fixture');
  assert.equal(patched, 'const GRID_CELL_HEIGHT = 20;\nconst GRID_CELL_VMARGIN = 4;\nconst GRID_COLUMN_COUNT = 60;\n');
  assert.equal(transformGrid(patched, 'fixture'), patched);
});
test('rejects missing, duplicate, or unexpected constants', () => {
  for (const bad of [source.replace('const GRID_CELL_HEIGHT = 30;', ''), source + source,
    source.replace('30;', '31;'), source.replace('30;', '30.5;')]) {
    assert.throws(() => transformGrid(bad, 'bad fixture'), /Unsupported/);
  }
});
test('table bridge uses the public default, is idempotent, and rejects drift', () => {
  assert.equal(transformTable(OLD_TABLE_IMPORT, 'esm'), NEW_TABLE_IMPORT);
  assert.equal(transformTable(NEW_TABLE_IMPORT, 'esm'), NEW_TABLE_IMPORT);
  const next = transformTable(cjsTable, 'cjs', true);
  assert.equal(next.split('schema.defaultTableOptions').length - 1, 3);
  assert.equal(transformTable(next, 'cjs', true), next);
  for (const bad of ['', OLD_TABLE_IMPORT + OLD_TABLE_IMPORT, OLD_TABLE_IMPORT + NEW_TABLE_IMPORT]) {
    assert.throws(() => transformTable(bad, 'esm'), /Unsupported/);
  }
  assert.throws(() => transformTable(cjsTable.replace('var schema', 'var renamed'), 'cjs', true), /Unsupported/);
  assert.throws(() => transformTable(cjsTable.replace('TablePanelCfg_types_gen.defaultOptions', ''), 'cjs', true), /Unsupported/);
});
test('verifies both package versions and every target before any write', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-grid-patch-'));
  t.after(() => {
    const resolved = fs.realpathSync(root);
    assert.ok(resolved.startsWith(fs.realpathSync(os.tmpdir()) + path.sep + 'sfl-grid-patch-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  });
  const manifest = path.join(root, 'package.json');
  fs.writeFileSync(manifest, JSON.stringify({ version: SUPPORTED_VERSION }));
  const schemaRoot = path.join(root, 'schema');
  fs.mkdirSync(schemaRoot);
  const schemaManifest = path.join(schemaRoot, 'package.json');
  fs.writeFileSync(schemaManifest, JSON.stringify({ version: SCHEMA_VERSION, main: 'index.js' }));
  fs.writeFileSync(path.join(schemaRoot, 'index.js'), "exports.defaultTableOptions = {cellHeight:'sm',frameIndex:0,showHeader:true,showTypeIcons:false,sortBy:[]};");
  const first = path.join(root, TARGETS[0]);
  fs.mkdirSync(path.dirname(first), { recursive: true });
  fs.writeFileSync(first, source);
  assert.throws(() => patchScenes(root, schemaRoot), /ENOENT/);
  assert.equal(fs.readFileSync(first, 'utf8'), source);
  fs.writeFileSync(path.join(root, TARGETS[1]), source + cjsTable);
  for (const relative of TABLE_TARGETS) {
    const file = path.join(root, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, OLD_TABLE_IMPORT);
  }
  fs.writeFileSync(path.join(root, TABLE_TARGETS[2]), 'drifted import');
  assert.throws(() => patchScenes(root, schemaRoot), /Unsupported/);
  assert.equal(fs.readFileSync(first, 'utf8'), source);
  fs.writeFileSync(path.join(root, TABLE_TARGETS[2]), OLD_TABLE_IMPORT);
  fs.writeFileSync(manifest, JSON.stringify({ version: '0.0.0' }));
  assert.throws(() => patchScenes(root, schemaRoot), /Revalidate Scenes/);
  assert.equal(fs.readFileSync(first, 'utf8'), source);
  fs.writeFileSync(manifest, JSON.stringify({ version: SUPPORTED_VERSION }));
  fs.writeFileSync(schemaManifest, JSON.stringify({ version: '0.0.0', main: 'index.js' }));
  assert.throws(() => patchScenes(root, schemaRoot), /Revalidate schema/);
  assert.equal(fs.readFileSync(first, 'utf8'), source);
  fs.writeFileSync(schemaManifest, JSON.stringify({ version: SCHEMA_VERSION, main: 'index.js' }));
  patchScenes(root, schemaRoot);
  patchScenes(root, schemaRoot);
  assert.equal(fs.readFileSync(first, 'utf8'), transformGrid(source, 'fixture'));
  assert.equal(fs.readFileSync(path.join(root, TARGETS[1]), 'utf8'), transformGrid(source, 'fixture') + transformTable(cjsTable, 'fixture', true));
  for (const relative of TABLE_TARGETS) assert.equal(fs.readFileSync(path.join(root, relative), 'utf8'), NEW_TABLE_IMPORT);
});
