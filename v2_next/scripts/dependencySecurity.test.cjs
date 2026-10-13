const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');

test('source-map-js rejects indexed offsets that could amplify a tiny map', () => {
  const { SourceMapConsumer } = require(path.join(root, 'frontend/node_modules/source-map-js'));
  const basic = { version: 3, sources: ['input.js'], sourcesContent: ['x'], names: [], mappings: 'AAAA' };
  const indexed = (line, map = basic) => ({
    version: 3,
    sections: [{ offset: { line, column: 0 }, map }],
  });
  const valid = new SourceMapConsumer(indexed(2));
  const mappings = [];
  valid.eachMapping((mapping) => mappings.push(mapping.generatedLine));
  assert.deepEqual(mappings, [3]);
  // Constructor-only checks: never serialize or expand a large offset, even on old versions.
  // GHSA-68fv-2mgg-jv7q also requires the accumulated nested offset to be bounded.
  assert.throws(() => new SourceMapConsumer(indexed(10000001)), /must not exceed/);
  assert.throws(() => new SourceMapConsumer(indexed(5000000, indexed(5000000, indexed(5000000)))),
    /including offsets of nested sections/);
});

for (const hook of ['beforeSanitizeElements', 'uponSanitizeElement', 'afterSanitizeElements', 'afterSanitizeAttributes']) {
  test(`DOMPurify neutralizes a detached descendant through ${hook}`, () => {
    const frontendRequire = Module.createRequire(path.join(root, 'frontend/package.json'));
    const { JSDOM } = frontendRequire('jsdom');
    const createDOMPurify = frontendRequire('dompurify');
    const dom = new JSDOM('<!doctype html><body></body>');
    try {
      const doc = dom.window.document;
      const container = doc.createElement('div');
      const wrapper = doc.createElement('section');
      const image = doc.createElement('img');
      image.setAttribute('src', 'synthetic-image');
      image.setAttribute('onerror', 'syntheticMarker()');
      wrapper.append(image);
      container.append(wrapper);
      doc.body.append(container);
      const sanitizer = createDOMPurify(dom.window);
      sanitizer.addHook(hook, (node) => { if (node === wrapper) node.remove(); });
      sanitizer.sanitize(container, { IN_PLACE: true });
      // Observe the original detached node; checking only sanitized output misses the bug.
      // jsdom does not load images or execute handlers in this fixture.
      assert.equal(wrapper.parentNode, null);
      assert.equal(image.hasAttribute('onerror'), false);
    } finally {
      dom.window.close();
    }
  });
}

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
