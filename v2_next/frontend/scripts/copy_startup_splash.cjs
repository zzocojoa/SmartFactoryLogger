'use strict';

const fs = require('node:fs');
const path = require('node:path');

const frontendRoot = path.resolve(__dirname, '..');
const source = path.resolve(frontendRoot, '..', 'backend', 'assets', 'splash.png');
const destinationDirectory = path.resolve(frontendRoot, 'dist', 'assets');
const destination = path.join(destinationDirectory, 'splash.png');

if (!fs.existsSync(source)) {
  throw new Error(`Startup splash asset is missing: ${source}`);
}

fs.mkdirSync(destinationDirectory, { recursive: true });
fs.copyFileSync(source, destination);

if (!fs.existsSync(destination) || fs.statSync(destination).size === 0) {
  throw new Error(`Startup splash copy failed: ${destination}`);
}

console.log(`Startup splash copied: ${destination}`);
