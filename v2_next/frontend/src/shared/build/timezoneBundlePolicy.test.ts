import { existsSync, readFileSync } from 'fs';
import { createRequire } from 'module';
import { resolve } from 'path';
import { describe, expect, it } from 'vitest';

const MOMENT_TIMEZONE_VERSION = '0.5.47';
const MOMENT_TIMEZONE_BROWSER_ENTRY = 'node_modules/moment-timezone/builds/moment-timezone-with-data-10-year-range.js';
const requireModule = createRequire(import.meta.url);

type UnknownRecord = Record<string, unknown>;

type MomentTimezoneBuild = {
  tz: {
    dataVersion: string;
    zone: (name: string) => { untils: number[] } | null;
  };
};

const isRecord = (value: unknown): value is UnknownRecord => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const readJsonFile = (path: string): UnknownRecord => {
  const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'));
  if (!isRecord(parsed)) {
    throw new Error(`Expected object JSON: ${path}`);
  }
  return parsed;
};

const readPackageDependencies = (path: string): UnknownRecord => {
  const packageJson = readJsonFile(path);
  const dependencies = packageJson.dependencies;
  if (!isRecord(dependencies)) {
    throw new Error(`Expected dependencies object: ${path}`);
  }
  return dependencies;
};

const readLockPackages = (path: string): UnknownRecord => {
  const packageLock = readJsonFile(path);
  const packages = packageLock.packages;
  if (!isRecord(packages)) {
    throw new Error(`Expected packages object: ${path}`);
  }
  return packages;
};

const getLockPackage = (packages: UnknownRecord, key: string): UnknownRecord => {
  const value = packages[key];
  if (!isRecord(value)) {
    throw new Error(`Expected lock package entry: ${key}`);
  }
  return value;
};

const getFiniteTransitionYears = (timezoneBuild: MomentTimezoneBuild, zoneName: string): number[] => {
  const zone = timezoneBuild.tz.zone(zoneName);
  if (!zone) {
    throw new Error(`Expected timezone zone: ${zoneName}`);
  }

  return zone.untils
    .filter((value) => Number.isFinite(value))
    .map((value) => new Date(value).getUTCFullYear());
};

describe('timezone bundle policy', () => {
  it('pins moment-timezone as a direct dependency for the Vite alias', () => {
    const packageDependencies = readPackageDependencies(resolve(process.cwd(), 'package.json'));
    const lockPackages = readLockPackages(resolve(process.cwd(), 'package-lock.json'));
    const rootLockPackage = getLockPackage(lockPackages, '');
    const rootLockDependencies = rootLockPackage.dependencies;
    const momentTimezoneLockPackage = getLockPackage(lockPackages, 'node_modules/moment-timezone');

    expect(packageDependencies['moment-timezone']).toBe(MOMENT_TIMEZONE_VERSION);
    expect(isRecord(rootLockDependencies) ? rootLockDependencies['moment-timezone'] : undefined).toBe(MOMENT_TIMEZONE_VERSION);
    expect(momentTimezoneLockPackage.version).toBe(MOMENT_TIMEZONE_VERSION);
  });

  it('keeps the browser alias on the ten-year timezone data bundle', () => {
    const viteConfigText = readFileSync(resolve(process.cwd(), 'vite.config.ts'), 'utf8');
    const browserEntry = resolve(process.cwd(), MOMENT_TIMEZONE_BROWSER_ENTRY);

    expect(viteConfigText).toContain('find: /^moment-timezone$/');
    expect(viteConfigText).toContain(MOMENT_TIMEZONE_BROWSER_ENTRY);
    expect(existsSync(browserEntry)).toBe(true);
  });

  it('covers near-term telemetry timezone transitions from 2020 through 2030', () => {
    const timezoneBuild = requireModule('moment-timezone/builds/moment-timezone-with-data-10-year-range.js') as MomentTimezoneBuild;
    const transitionYears = [
      ...getFiniteTransitionYears(timezoneBuild, 'America/New_York'),
      ...getFiniteTransitionYears(timezoneBuild, 'Europe/Berlin'),
    ];

    expect(timezoneBuild.tz.dataVersion).toBeTruthy();
    expect(Math.min(...transitionYears)).toBeLessThanOrEqual(2020);
    expect(Math.max(...transitionYears)).toBeGreaterThanOrEqual(2030);
  });
});
