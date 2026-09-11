'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { verifySourceContract, verifyModuleIdentities, verifyRouterContract, assertRouterCoreGraph, SOURCE_HASHES, GRAFANA_VERSIONS } = require('./verify_grafana_router_contract.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-router-contract-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const [name, version] of Object.entries(GRAFANA_VERSIONS)) {
    fs.mkdirSync(path.join(root, name, 'dist'), { recursive: true });
    fs.writeFileSync(path.join(root, name, 'package.json'), JSON.stringify({ version }));
  }
  for (const name of Object.keys(SOURCE_HASHES)) {
    const target = path.join(root, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(__dirname, '../node_modules', name), target);
  }
  return root;
}

test('installed official alias and all reviewed consumers share one context', () => {
  const result = verifyRouterContract();
  assert.equal(result.routerVersion, '7.18.3');
  assert.equal(result.sources, 7);
});

test('production graph rejects CJS/ESM, branch and virtual duplicate cores', () => {
  const root = '/app/node_modules/react-router';
  const esm = root + '/dist/production/core.mjs';
  assertRouterCoreGraph([esm, root + '/dist/production/index.mjs'], root);
  for (const other of [root + '/dist/production/core.js', root + '/dist/development/core.mjs', '\0' + esm, esm + '?other', '/other/node_modules/react-router/dist/production/core.mjs']) {
    assert.throws(() => assertRouterCoreGraph([esm, other], root), /Router core/);
  }
  assert.throws(() => assertRouterCoreGraph([], root), /Router core/);
});

test('rejects missing, changed and additional Router consumers', (t) => {
  const root = fixture(t);
  assert.equal(verifySourceContract(root).length, 7);
  const target = path.join(root, '@grafana/ui/dist/esm/components/Link/Link.mjs');
  const original = fs.readFileSync(target);
  fs.appendFileSync(target, '\n// changed consumer');
  assert.throws(() => verifySourceContract(root), /Router consumer changed/);
  fs.writeFileSync(target, original);
  const extra = path.join(root, '@grafana/ui/dist/extra.js');
  fs.writeFileSync(extra, "import { CompatRouter } from 'react-router-dom-v5-compat';");
  assert.throws(() => verifySourceContract(root), /Unreviewed Router consumer/);
  fs.unlinkSync(extra);
  fs.unlinkSync(target);
  assert.throws(() => verifySourceContract(root), /Missing reviewed Router consumer/);
});

test('rejects unreviewed Grafana versions', (t) => {
  const root = fixture(t);
  fs.writeFileSync(path.join(root, '@grafana/ui/package.json'), JSON.stringify({ version: '12.4.11' }));
  assert.throws(() => verifySourceContract(root), /Unsupported Grafana version/);
});

test('rejects split contexts and a stub posing as the official package', (t) => {
  const root = fixture(t);
  const rootDom = path.join(root, 'dom.json');
  const aliasDom = path.join(root, 'alias.json');
  const domRouter = path.join(root, 'router.json');
  for (const file of [rootDom, aliasDom, domRouter]) {
    fs.writeFileSync(file, JSON.stringify({ name: file === domRouter ? 'react-router' : 'react-router-dom', version: '7.18.3' }));
  }
  const identities = { rootDom, aliasDom, domRouter, scenesDom: rootDom, aliasRouter: domRouter, rootReact: 'same-react', consumersReact: ['same-react'] };
  verifyModuleIdentities(identities);
  assert.throws(() => verifyModuleIdentities({ ...identities, scenesDom: 'other-dom' }), /different Router facades/);
  assert.throws(() => verifyModuleIdentities({ ...identities, aliasRouter: 'other-router' }), /different Router contexts/);
  assert.throws(() => verifyModuleIdentities({ ...identities, consumersReact: ['other-react'] }), /Duplicate React/);
  fs.writeFileSync(aliasDom, JSON.stringify({ name: 'local-stub', version: '7.18.3' }));
  assert.throws(() => verifyModuleIdentities(identities), /Expected official Router/);
  fs.writeFileSync(aliasDom, JSON.stringify({ name: 'react-router-dom', version: '6.30.6' }));
  assert.throws(() => verifyModuleIdentities(identities), /Unsupported Router version/);
});
