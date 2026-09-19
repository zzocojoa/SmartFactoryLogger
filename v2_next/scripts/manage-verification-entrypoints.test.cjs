'use strict';
// Exercise actual command entrypoints with an in-memory registry. Never opens
// the operator's registry or invokes Git, PowerShell, a product, or a cleanup.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, 'manage-verification-files.cjs'), 'utf8');

function manager(audits) {
  const index = {host: os.hostname(), workspace: path.resolve(__dirname, '..'), plans: [], migrations: [], history: [], audits};
  const io = {writes: 0};
  const fakeFs = {
    readFileSync: () => JSON.stringify(index),
    existsSync: () => true,
    openSync: () => { io.writes++; throw new Error('Unexpected filesystem write'); }
  };
  const localRequire = name => {
    if (name === 'node:fs') return fakeFs;
    if (name === 'node:child_process') return {execFileSync: () => { throw new Error('Unexpected subprocess'); }};
    return require(name);
  };
  const context = {require: localRequire, module: {exports: {}}, __dirname, console: {log() {}}};
  vm.createContext(context);
  vm.runInContext(source + `
    plain = value => value;
    walk = () => ({files:[{path:'fixture-only',bytes:3,mtime_ms:0}],dirs:[],links:[],errors:[]});
    trackedFiles = () => new Set();
    hash = async () => 'A'.repeat(64);
    globalThis.commands = {planExact,planDuplicateDirs,prepareDesktopMigration,
      prepareTransferMigration,prepareReleaseMigration,prepareTransferBatchMigrations,scan,verify};
    globalThis.saveIndex = save;
  `, context);
  return {context, io, index};
}

for (const command of ['planExact', 'planDuplicateDirs', 'prepareDesktopMigration',
  'prepareTransferMigration', 'prepareReleaseMigration', 'prepareTransferBatchMigrations', 'scan', 'verify']) {
  test(`${command} refuses a partial ACL repair before any registry write`, async () => {
    const {context, io} = manager([{kind: 'DESKTOP_DEPENDENCY_ACL_REPAIR', state: 'PARTIAL_STOPPED'}]);
    await assert.rejects(context.commands[command](['.tmp_electron_cache']), /ACL repair incomplete/);
    assert.equal(io.writes, 0);
  });
}

for (const [kind, message] of [
  ['DESKTOP_DEPENDENCY_ACL_REPAIR', /ACL repair incomplete/],
  ['DESKTOP_DIST_PROTECTED_CI_MIGRATION', /Dist migration/],
  ['DESKTOP_CHROME_TEST_CACHE_CLEANUP', /Chrome cache/]
]) {
  test(`save independently blocks ${kind} interruption`, () => {
    const {context, io, index} = manager([{kind, state: 'PARTIAL_STOPPED'}]);
    assert.throws(() => context.saveIndex(index), message);
    assert.equal(io.writes, 0);
  });
}
