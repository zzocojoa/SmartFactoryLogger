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

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_BASE_URL || 'http://localhost:8000';
  const grafanaScenesEntry: string = resolveGrafanaScenesEntry();

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
          find: /^react-router-dom$/,
          replacement: resolve(process.cwd(), 'src/shims/react-router-dom.ts'),
        },
      ],
    },
    define: {
      // Grafana libraries often check process.env
      'process.env': {},
    },
  };
});
