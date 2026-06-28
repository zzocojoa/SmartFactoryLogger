/// <reference types="vitest/config" />

import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

type GrafanaScenesPackageJson = {
  module?: string;
  version: string;
};

type UnknownObject = {
  [key: string]: unknown;
};

const SUPPORTED_GRAFANA_SCENES_VERSION = '6.52.0';
const MOMENT_TIMEZONE_BROWSER_ENTRY = 'node_modules/moment-timezone/builds/moment-timezone-with-data-10-year-range.js';

const isUnknownObject = (value: unknown): value is UnknownObject => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isGrafanaScenesPackageJson = (value: unknown): value is GrafanaScenesPackageJson => {
  return (
    isUnknownObject(value) &&
    typeof value.version === 'string' &&
    (value.module === undefined || typeof value.module === 'string')
  );
};

const readGrafanaScenesPackageJson = (packageJsonPath: string): GrafanaScenesPackageJson => {
  const packageJsonText: string = readFileSync(packageJsonPath, 'utf8');
  const parsedPackageJson: unknown = JSON.parse(packageJsonText);

  if (!isGrafanaScenesPackageJson(parsedPackageJson)) {
    throw new Error(`Invalid @grafana/scenes package.json shape: ${packageJsonPath}`);
  }

  return parsedPackageJson;
};

const normalizeModuleId = (id: string): string => {
  return id.replace(/\\/g, '/');
};

const resolveManualChunk = (id: string): string | undefined => {
  const normalizedId: string = normalizeModuleId(id);

  if (normalizedId.includes('vite/preload-helper')) {
    return 'vendor-vite';
  }

  if (normalizedId.includes('commonjsHelpers')) {
    return 'vendor-common';
  }

  if (
    normalizedId.includes('/node_modules/@babel/runtime/') ||
    normalizedId.includes('/node_modules/tslib/')
  ) {
    return 'vendor-common';
  }

  if (normalizedId.includes('/node_modules/moment-timezone/')) {
    return 'vendor-moment-timezone';
  }

  if (normalizedId.includes('/node_modules/moment/')) {
    return 'vendor-moment';
  }

  if (normalizedId.includes('/node_modules/@grafana/scenes/')) {
    return 'vendor-grafana-scenes';
  }

  if (normalizedId.includes('/node_modules/@grafana/ui/')) {
    return 'vendor-grafana-ui';
  }

  if (normalizedId.includes('/node_modules/@grafana/data/')) {
    return 'vendor-grafana-data';
  }

  if (normalizedId.includes('/node_modules/@grafana/runtime/')) {
    return 'vendor-grafana-runtime';
  }

  if (
    normalizedId.includes('/node_modules/@grafana/schema/') ||
    normalizedId.includes('/node_modules/@grafana/i18n/') ||
    normalizedId.includes('/node_modules/@grafana/faro-core/') ||
    normalizedId.includes('/node_modules/@grafana/faro-web-sdk/') ||
    normalizedId.includes('/node_modules/@grafana/e2e-selectors/')
  ) {
    return 'vendor-grafana-support';
  }

  if (normalizedId.includes('/node_modules/@grafana/')) {
    return 'vendor-grafana';
  }

  if (
    normalizedId.includes('/node_modules/react/') ||
    normalizedId.includes('/node_modules/react-dom/') ||
    normalizedId.includes('/node_modules/react-router/') ||
    normalizedId.includes('/node_modules/react-router-dom/') ||
    normalizedId.includes('/node_modules/scheduler/')
  ) {
    return 'vendor-react';
  }

  if (normalizedId.includes('/node_modules/uplot/')) {
    return 'vendor-uplot';
  }

  if (
    normalizedId.includes('/node_modules/react-grid-layout/') ||
    normalizedId.includes('/node_modules/react-resizable/') ||
    normalizedId.includes('/node_modules/react-draggable/') ||
    normalizedId.includes('/node_modules/prop-types/') ||
    normalizedId.includes('/node_modules/clsx/') ||
    normalizedId.includes('/node_modules/fast-equals/') ||
    normalizedId.includes('/node_modules/resize-observer-polyfill/')
  ) {
    return 'vendor-grid-layout';
  }

  return undefined;
};

const resolveGrafanaScenesEntry = (): string => {
  const packageRoot: string = resolve(__dirname, 'node_modules/@grafana/scenes');
  const packageJsonPath: string = resolve(packageRoot, 'package.json');
  const packageJson: GrafanaScenesPackageJson = readGrafanaScenesPackageJson(packageJsonPath);

  if (packageJson.version !== SUPPORTED_GRAFANA_SCENES_VERSION) {
    throw new Error(
      [
        '@grafana/scenes ESM alias must be revalidated after package upgrades.',
        `Expected version: ${SUPPORTED_GRAFANA_SCENES_VERSION}`,
        `Installed version: ${packageJson.version}`,
        `Package: ${packageJsonPath}`,
      ].join('\n')
    );
  }

  const internalEsmEntry: string = resolve(packageRoot, 'dist/esm/packages/scenes/src/index.js');

  if (existsSync(internalEsmEntry)) {
    return internalEsmEntry;
  }

  const declaredModuleEntry: string | null = packageJson.module ? resolve(packageRoot, packageJson.module) : null;

  throw new Error(
    [
      '@grafana/scenes ESM entry could not be resolved.',
      `Internal ESM entry: ${internalEsmEntry}`,
      `Declared module entry: ${declaredModuleEntry ?? 'missing'}`,
      `Package: ${packageJsonPath}`,
    ].join('\n')
  );
};

const resolveMomentTimezoneBrowserEntry = (): string => {
  const browserEntry = resolve(__dirname, MOMENT_TIMEZONE_BROWSER_ENTRY);

  if (existsSync(browserEntry)) {
    return browserEntry;
  }

  throw new Error(
    [
      'moment-timezone browser bundle could not be resolved.',
      'Keep moment-timezone as a direct frontend dependency because Vite aliases this package explicitly.',
      `Expected entry: ${browserEntry}`,
    ].join('\n')
  );
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_BASE_URL || 'http://localhost:8000';
  const grafanaScenesEntry: string = resolveGrafanaScenesEntry();
  const momentTimezoneBrowserEntry: string = resolveMomentTimezoneBrowserEntry();

  return {
    base: './',
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/stats': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: [
        { find: '@', replacement: resolve(__dirname, 'src') },
        {
          find: '@grafana/scenes',
          replacement: grafanaScenesEntry,
        },
        {
          find: /^moment-timezone$/,
          // Dashboard telemetry uses near-term ranges; keep the smaller direct dependency bundle.
          replacement: momentTimezoneBrowserEntry,
        },
        {
          find: /^react-router-dom$/,
          replacement: resolve(process.cwd(), 'src/shims/react-router-dom.ts'),
        },
      ],
    },
    define: {
      // Grafana 라이브러리는 process.env를 확인하는 경우가 있음
      'process.env': {},
    },
    test: {
      environment: 'jsdom',
      globals: false,
      include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    },
    build: {
      modulePreload: false,
      rollupOptions: {
        output: {
          hoistTransitiveImports: false,
          manualChunks: resolveManualChunk,
        },
      },
    },
  };
});
