const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');

// Exercise every locked copy, including build tooling and nested lint dependencies.
for (const project of [root, path.join(root, 'frontend')]) {
  const lock = JSON.parse(readFileSync(path.join(project, 'package-lock.json'), 'utf8'));
  const copies = Object.keys(lock.packages).filter((name) => name.endsWith('/brace-expansion'));
  assert.ok(copies.length > 0, `Missing brace-expansion coverage: ${project}`);
  for (const relative of copies) {
    test(`${path.basename(project)}/${relative}: normal globs and deep groups`, () => {
      const loaded = require(path.join(project, relative));
      const expand = typeof loaded === 'function' ? loaded : loaded.expand;
      assert.equal(typeof expand, 'function');
      assert.deepEqual(expand('src/{main,preload}.{js,cjs}'), [
        'src/main.js', 'src/main.cjs', 'src/preload.js', 'src/preload.cjs',
      ]);
      // GHSA-q2hr-2g5m-vwhr: excessive rewrites must fall back to a literal.
      // Assert the bounded behavior instead of a machine-dependent time limit.
      const rewrites = '{a}' + '}'.repeat(2000) + ',z}';
      assert.deepEqual(expand(rewrites), [rewrites]);
      // Bounded synthetic inputs; no filesystem traversal or external I/O.
      // GHSA-qhr7-859c-m2p7 and GHSA-6j4f-fj2g-mc7p parsing paths.
      for (const input of [
        '{'.repeat(4000) + 'a,b' + '}'.repeat(4000),
        '{a,'.repeat(4500) + 'z' + '}'.repeat(4500),
        '{' + '{a},'.repeat(8000) + 'b}',
        '{{x},' + 'a,'.repeat(130000) + 'b}',
      ]) {
        assert.doesNotThrow(() => {
          const result = expand(input);
          assert.ok(Array.isArray(result) && result.length > 0);
        });
      }
    });
  }
}

test('fast-uri normalizes encoded and literal hostname case consistently', () => {
  const uri = require(path.join(root, 'node_modules/fast-uri'));
  for (const input of ['//%41.example', '//A.example', '//a.example']) {
    assert.equal(uri.parse(input).host, 'a.example');
    assert.equal(uri.equal(input, '//a.example'), true);
  }
});

test('Moment does not lazy-load a non-string locale as a filesystem path', () => {
  const moment = require(path.join(root, 'frontend/node_modules/moment'));
  const previousLocale = moment.locale();
  const originalLoad = Module._load;
  const requests = [];
  const input = {
    toString: () => '../sfl-security-probe',
    match: () => true,
    toLowerCase() { return this; },
    replace() { return this; },
    split: () => ['en'],
  };
  // Observe the external module-loading boundary without loading any probe file.
  Module._load = function (request, parent, isMain) {
    if (request.includes('sfl-security-probe')) {
      requests.push(request);
      return {};
    }
    return originalLoad.call(this, request, parent, isMain);
  };
  try {
    moment.locale(input);
    assert.deepEqual(requests, []);
    assert.equal(moment.locale(), previousLocale);
  } finally {
    Module._load = originalLoad;
    moment.locale(previousLocale);
  }
});
