'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { createRequire } = require('node:module');

// This is a project-supported boundary, NOT a claim that Scenes supports Router 7.
// UI consumes only Link; Scenes consumes Route/Routes/useLocation/useParams/matchPath.
// Pin both published module formats; the Scenes CJS hash is AFTER our grid/table patch.
const SOURCE_HASHES = {
  '@grafana/ui/dist/esm/components/Link/Link.mjs': 'c4e2be7ec0f5c5bf55745dfcce35a5de4f1a9ed7535fab769e26ed355651eab4',
  '@grafana/ui/dist/cjs/components/Link/Link.cjs': '3ae1287b19e59a0ddcd22f4ada95bb027dceab3a69bb4e7760e713dc00bf885c',
  '@grafana/scenes/dist/index.js': 'd77a3ff1582abdfd3f60c8d214dc20693be33d07a2071c8b04acf1a3f72e879e',
  '@grafana/scenes/dist/esm/services/useUrlSync.js': '25a4d883c5c1cff16bffe4e8d26860e63d0804de089cb8a156826f8a14728c02',
  '@grafana/scenes/dist/esm/components/SceneApp/utils.js': '1a25517a4636ca3988d303cb326198c4518ff4a0c251b8724f57845f2f41bb1e',
  '@grafana/scenes/dist/esm/components/SceneApp/SceneAppPage.js': 'abb1de87d74a288f9fa645d290ed9f08f15e58bb5aee041c1d4294f1b0aaf6b4',
  '@grafana/scenes/dist/esm/components/SceneApp/SceneApp.js': '049fbf292ffb09a5aff32385553ffa00765833e390bb4cc8b12c01ff9e793164',
};
const GRAFANA_VERSIONS = { '@grafana/ui': '12.4.10', '@grafana/runtime': '12.4.10', '@grafana/scenes': '8.17.0' };
const ROUTER_VERSION = '7.18.3';
const json = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

function verifySourceContract(nodeModules) {
  const found = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (/\.(?:js|mjs|cjs)$/.test(entry.name)) {
        const bytes = fs.readFileSync(file);
        if (!bytes.includes('react-router')) continue;
        const relative = path.relative(nodeModules, file).split(path.sep).join('/');
        assert.ok(Object.hasOwn(SOURCE_HASHES, relative), `Unreviewed Router consumer: ${relative}`);
        assert.equal(createHash('sha256').update(bytes).digest('hex'), SOURCE_HASHES[relative], `Router consumer changed: ${relative}`);
        found.push(relative);
      }
    }
  }
  for (const [name, version] of Object.entries(GRAFANA_VERSIONS)) {
    assert.equal(json(path.join(nodeModules, name, 'package.json')).version, version, `Unsupported Grafana version: ${name}`);
    visit(path.join(nodeModules, name, 'dist'));
  }
  assert.deepEqual(found.sort(), Object.keys(SOURCE_HASHES).sort(), 'Missing reviewed Router consumer');
  return found;
}

function verifyModuleIdentities({ rootDom, scenesDom, aliasDom, rootReact, consumersReact, domRouter, aliasRouter }) {
  assert.equal(scenesDom, rootDom, 'Scenes and app resolve different Router facades');
  assert.equal(aliasRouter, domRouter, 'Grafana Link and app resolve different Router contexts');
  for (const react of consumersReact) assert.equal(react, rootReact, 'Duplicate React context');
  for (const file of [rootDom, aliasDom, domRouter]) {
    const pkg = json(file);
    assert.equal(pkg.version, ROUTER_VERSION, 'Unsupported Router version');
    assert.equal(pkg.name, file === domRouter ? 'react-router' : 'react-router-dom', 'Expected official Router package, not a stub');
  }
}

function verifyRouterContract(frontendRoot = path.resolve(__dirname, '..')) {
  const nodeModules = path.join(frontendRoot, 'node_modules');
  const sources = verifySourceContract(nodeModules);
  const from = (file) => createRequire(file);
  const resolvePackage = (request, name) => fs.realpathSync(request.resolve(name + '/package.json'));
  const root = from(path.join(frontendRoot, 'package.json'));
  const ui = from(path.join(nodeModules, '@grafana/ui/package.json'));
  const scenes = from(path.join(nodeModules, '@grafana/scenes/package.json'));
  const runtime = from(path.join(nodeModules, '@grafana/runtime/package.json'));
  const rootDom = resolvePackage(root, 'react-router-dom');
  const aliasDom = resolvePackage(ui, 'react-router-dom-v5-compat');
  const domRouter = resolvePackage(from(rootDom), 'react-router');
  verifyModuleIdentities({
    rootDom, aliasDom, domRouter, scenesDom: resolvePackage(scenes, 'react-router-dom'),
    aliasRouter: resolvePackage(from(aliasDom), 'react-router'), rootReact: resolvePackage(root, 'react'),
    consumersReact: [ui, scenes, runtime, from(aliasDom), from(domRouter)].map((r) => resolvePackage(r, 'react')),
  });
  const lock = json(path.join(frontendRoot, 'package-lock.json'));
  const domEntry = lock.packages[path.relative(frontendRoot, path.dirname(rootDom)).split(path.sep).join('/')];
  const aliasEntry = lock.packages[path.relative(frontendRoot, path.dirname(aliasDom)).split(path.sep).join('/')];
  assert.equal(aliasEntry.name, 'react-router-dom', 'Alias must disclose its real package name to npm audit');
  assert.equal(aliasEntry.version, ROUTER_VERSION);
  assert.equal(aliasEntry.resolved, `https://registry.npmjs.org/react-router-dom/-/react-router-dom-${ROUTER_VERSION}.tgz`);
  assert.equal(aliasEntry.resolved, domEntry.resolved);
  assert.match(aliasEntry.integrity, /^sha512-/);
  assert.equal(aliasEntry.integrity, domEntry.integrity, 'Alias and app must use the same official tarball');
  for (const [name, pkg] of Object.entries(lock.packages)) {
    if (/\/react-router(?:-dom|-dom-v5-compat)?$/.test(name)) {
      assert.ok(!pkg.version.startsWith('6.'), `Vulnerable Router 6 remains: ${name}`);
    }
    assert.ok(!pkg.link, `Unexpected linked dependency: ${name}`);
  }
  return { routerVersion: ROUTER_VERSION, sources: sources.length, routerRoot: path.dirname(domRouter) };
}

function assertRouterCoreGraph(ids, routerRoot) {
  const expected = routerRoot.replace(/\\/g, '/');
  const branches = new Set();
  for (const id of ids) {
    const normalized = id.replace(/\\/g, '/');
    if (!normalized.includes('/node_modules/react-router/')) continue;
    // CJS/ESM cores define different contexts even inside the SAME package root.
    // Do not strip virtual prefixes/queries: they can also create another instance.
    assert.ok(normalized.startsWith(expected + '/dist/') && normalized.endsWith('.mjs') && !normalized.includes('?'), `Non-shared Router core: ${id}`);
    const branch = normalized.slice(expected.length).match(/^\/dist\/(development|production)\//);
    assert.ok(branch, `Unexpected Router core layout: ${id}`);
    branches.add(branch[1]);
  }
  assert.equal(branches.size, 1, 'Expected one ESM Router core branch');
}

module.exports = { verifySourceContract, verifyModuleIdentities, verifyRouterContract, assertRouterCoreGraph, SOURCE_HASHES, GRAFANA_VERSIONS };
if (require.main === module) {
  const result = verifyRouterContract();
  console.log(`[router-contract] PASS: Router ${result.routerVersion}; ${result.sources} pinned consumers; shared React/Router contexts`);
}
