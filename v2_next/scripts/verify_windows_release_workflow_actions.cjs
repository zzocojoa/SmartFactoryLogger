"use strict";

const fs = require("node:fs");
const path = require("node:path");
const yaml = require("js-yaml");

const APPROVED_ACTIONS = Object.freeze({
  "actions/checkout": "d23441a48e516b6c34aea4fa41551a30e30af803",
  "actions/setup-node": "249970729cb0ef3589644e2896645e5dc5ba9c38",
  "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",
  "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
});

function fail(message) {
  throw new Error(`Windows workflow action contract failed: ${message}`);
}

function collectUsesReferences(value, valuePath = "$", output = [], seen = new WeakSet()) {
  if (value === null || typeof value !== "object") {
    return output;
  }
  if (seen.has(value)) {
    return output;
  }
  seen.add(value);

  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      collectUsesReferences(item, `${valuePath}[${index}]`, output, seen);
    });
    return output;
  }

  for (const [key, child] of Object.entries(value)) {
    const childPath = `${valuePath}.${key}`;
    if (key === "uses") {
      if (typeof child !== "string" || child.trim() === "") {
        fail(`uses must be a non-empty string at ${childPath}`);
      }
      output.push({ path: childPath, reference: child.trim() });
    }
    collectUsesReferences(child, childPath, output, seen);
  }
  return output;
}

function parseWorkflow(text, sourceName) {
  let document;
  try {
    document = yaml.load(text, {
      filename: sourceName,
      schema: yaml.DEFAULT_SCHEMA,
    });
  } catch (error) {
    fail(`invalid YAML in ${sourceName}: ${error.message}`);
  }
  if (document === null || typeof document !== "object" || Array.isArray(document)) {
    fail(`workflow root must be a mapping in ${sourceName}`);
  }
  return document;
}

function verifyWorkflowText(text, sourceName) {
  const workflow = parseWorkflow(text, sourceName);
  const references = collectUsesReferences(workflow);
  const observed = new Set();

  for (const item of references) {
    const separator = item.reference.lastIndexOf("@");
    if (separator <= 0) {
      fail(`action reference must include an immutable commit at ${item.path}: ${item.reference}`);
    }
    const action = item.reference.slice(0, separator);
    const revision = item.reference.slice(separator + 1);
    if (!Object.prototype.hasOwnProperty.call(APPROVED_ACTIONS, action)) {
      fail(`action is not present in the approved allowlist at ${item.path}: ${action}`);
    }
    if (revision !== APPROVED_ACTIONS[action]) {
      fail(`action must use its approved immutable commit at ${item.path}: ${item.reference}`);
    }
    observed.add(action);
  }

  for (const action of Object.keys(APPROVED_ACTIONS)) {
    if (!observed.has(action)) {
      fail(`required approved action is missing from ${sourceName}: ${action}`);
    }
  }
  return references;
}

function approvedFixture(extraYaml = "") {
  const actionSteps = Object.entries(APPROVED_ACTIONS)
    .map(([action, revision]) => `      - uses: ${action}@${revision}`)
    .join("\n");
  return `name: fixture
on: pull_request
jobs:
  verify:
    runs-on: windows-latest
    steps:
${actionSteps}
${extraYaml}`;
}

function expectRejected(name, text) {
  let rejected = false;
  try {
    verifyWorkflowText(text, name);
  } catch (error) {
    rejected = error.message.startsWith("Windows workflow action contract failed:");
  }
  if (!rejected) {
    fail(`self-test accepted an unapproved action form: ${name}`);
  }
}

function runSelfTests() {
  verifyWorkflowText(approvedFixture(), "approved fixture");

  const injectedSteps = [
    "      - uses: attacker/example@main",
    '      - "uses": "attacker/example@main"',
    "      - 'uses': 'attacker/example@main'",
    "      - { uses: attacker/example@main }",
    '      - { "uses": "attacker/example@main" }',
    "      - { 'uses': 'attacker/example@main' }",
    "      - { name: injected, uses: attacker/example@main }",
  ];
  injectedSteps.forEach((step, index) => {
    expectRejected(`injected step ${index + 1}`, approvedFixture(step));
  });

  expectRejected(
    "flow reusable workflow",
    approvedFixture(
      "  injected-job: { uses: attacker/example/.github/workflows/reuse.yml@main }",
    ),
  );
  expectRejected(
    "escaped uses key",
    approvedFixture(
      String.raw`  injected-job: { "us\u0065s": "attacker/example/.github/workflows/reuse.yml@main" }`,
    ),
  );
  expectRejected(
    "mutable approved action",
    approvedFixture().replace(APPROVED_ACTIONS["actions/checkout"], "v6"),
  );
  expectRejected(
    "duplicate mapping key",
    `${approvedFixture()}\njobs:\n  duplicate: true\n`,
  );
}

function main(argv) {
  if (argv.length === 1 && argv[0] === "--self-test") {
    runSelfTests();
    console.log("[PASS] Windows workflow semantic action verifier self-tests passed.");
    return;
  }
  if (argv.length === 0) {
    fail("provide --self-test or one or more workflow paths");
  }
  for (const workflowPath of argv) {
    const resolved = path.resolve(workflowPath);
    verifyWorkflowText(fs.readFileSync(resolved, "utf8"), resolved);
  }
  console.log(`[PASS] Semantically verified action pins in ${argv.length} workflow(s).`);
}

try {
  main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}

module.exports = {
  collectUsesReferences,
  parseWorkflow,
  verifyWorkflowText,
};
