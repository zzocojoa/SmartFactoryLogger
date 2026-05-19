const fs = require('node:fs');
const path = require('node:path');

const readArg = (name, fallback) => {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback;
  }
  return process.argv[index + 1];
};

const sourceRoot = path.resolve(__dirname, '..');
const rootArg = readArg('--root', null);

if (!rootArg) {
  throw new Error('Missing required --root. Pass the temporary worktree root to avoid modifying the current checkout.');
}

const targetRoot = path.resolve(rootArg);
const sourceProfilerPath = path.join(sourceRoot, 'frontend', 'src', 'shared', 'profiling', 'reactRenderProfiler.tsx');
const targetProfilerPath = path.join(targetRoot, 'frontend', 'src', 'shared', 'profiling', 'reactRenderProfiler.tsx');
const targetAppPath = path.join(targetRoot, 'frontend', 'src', 'App.tsx');
const targetNativeSurfacePath = path.join(targetRoot, 'frontend', 'src', 'scenes', 'NativeDashboardSurface.tsx');

if (targetRoot === sourceRoot) {
  throw new Error(`Refusing to instrument the current checkout: ${targetRoot}`);
}

if (!fs.existsSync(targetAppPath)) {
  throw new Error(`Target worktree is missing frontend/src/App.tsx: ${targetRoot}`);
}

const ensureProfilerFile = () => {
  fs.mkdirSync(path.dirname(targetProfilerPath), { recursive: true });
  fs.copyFileSync(sourceProfilerPath, targetProfilerPath);
};

const readText = (filePath) => fs.readFileSync(filePath, 'utf8');
const writeText = (filePath, value) => fs.writeFileSync(filePath, value, 'utf8');

const replaceStringOnce = (source, filePath, before, after, label) => {
  const firstIndex = source.indexOf(before);
  if (firstIndex === -1) {
    throw new Error(`Instrumentation anchor not found: ${label} in ${filePath}`);
  }

  if (source.indexOf(before, firstIndex + before.length) !== -1) {
    throw new Error(`Instrumentation anchor matched multiple times: ${label} in ${filePath}`);
  }

  return source.replace(before, after);
};

const replaceRegexOnce = (source, filePath, pattern, after, label) => {
  if (!pattern.test(source)) {
    throw new Error(`Instrumentation pattern not found: ${label} in ${filePath}`);
  }

  pattern.lastIndex = 0;
  const nextSource = source.replace(pattern, after);
  pattern.lastIndex = 0;

  if (pattern.test(nextSource)) {
    throw new Error(`Instrumentation pattern still matches after replacement: ${label} in ${filePath}`);
  }

  return nextSource;
};

const addProfilerImport = (source, importPath) => {
  if (source.includes('reactRenderProfiler')) {
    return source;
  }

  const anchor = "import { useLayoutHandlers } from './shared/hooks/useLayoutHandlers';";
  if (source.includes(anchor)) {
    return replaceStringOnce(
      source,
      targetAppPath,
      anchor,
      `${anchor}\nimport { ProfilerProbe } from '${importPath}';`,
      'App ProfilerProbe import',
    );
  }

  return replaceStringOnce(
    source,
    targetAppPath,
    "import { SnapshotContext } from './domains/FacilityData/context/SnapshotContext';",
    "import { SnapshotContext } from './domains/FacilityData/context/SnapshotContext';\nimport { ProfilerProbe } from './shared/profiling/reactRenderProfiler';",
    'App fallback ProfilerProbe import',
  );
};

const wrapRootApp = (source) => {
  if (source.includes('<ProfilerProbe id="App">')) {
    return source;
  }

  const rootPattern = /(return \(\r?\n)(\s+<div className=\{`App \$\{layoutEditing \? 'layout-editing' : ''\}`)/;
  const closingPattern = /(\r?\n\s+<\/div>\r?\n\s+\);\r?\n}\r?\n\r?\nexport default App;)\s*$/;

  const withOpening = replaceRegexOnce(
    source,
    targetAppPath,
    rootPattern,
    '$1    <ProfilerProbe id="App">\n$2',
    'App root profiler opening',
  );

  return replaceRegexOnce(
    withOpening,
    targetAppPath,
    closingPattern,
    '\n    </div>\n    </ProfilerProbe>\n  );\n}\n\nexport default App;',
    'App root profiler closing',
  );
};

const wrapSelfClosingComponent = (source, componentName, profilerId) => {
  if (source.includes(`<ProfilerProbe id="${profilerId}">`)) {
    return source;
  }

  const pattern = new RegExp(`(\\n\\s+<${componentName}[\\s\\S]*?\\n\\s+/>)`, 'm');
  return replaceRegexOnce(
    source,
    targetAppPath,
    pattern,
    `\n      <ProfilerProbe id="${profilerId}">$1\n      </ProfilerProbe>`,
    `${componentName} profiler wrapper`,
  );
};

const instrumentApp = () => {
  let source = readText(targetAppPath);
  source = addProfilerImport(source, './shared/profiling/reactRenderProfiler');
  source = wrapRootApp(source);
  source = wrapSelfClosingComponent(source, 'DashboardHeader', 'DashboardHeader');
  source = wrapSelfClosingComponent(source, 'DashboardSceneSurface', 'DashboardSceneSurface');
  source = wrapSelfClosingComponent(source, 'NativeDashboardSurface', 'NativeDashboardSurface');
  writeText(targetAppPath, source);
};

const instrumentNativeSurface = () => {
  if (!fs.existsSync(targetNativeSurfacePath)) {
    return;
  }

  let source = readText(targetNativeSurfacePath);
  if (!source.includes('reactRenderProfiler')) {
    source = replaceStringOnce(
      source,
      targetNativeSurfacePath,
      "} from './DashboardSceneModel';",
      "} from './DashboardSceneModel';\nimport { ProfilerProbe } from '../shared/profiling/reactRenderProfiler';",
      'NativeDashboardSurface ProfilerProbe import',
    );
  }

  const replacements = [
    ['return <KpiComponent />;', 'return <ProfilerProbe id="Widget:kpi"><KpiComponent /></ProfilerProbe>;'],
    ['return <SpotComponent />;', 'return <ProfilerProbe id="Widget:spot"><SpotComponent /></ProfilerProbe>;'],
    ['return <TempsComponent />;', 'return <ProfilerProbe id="Widget:temps"><TempsComponent /></ProfilerProbe>;'],
    ['return <MoldsComponent />;', 'return <ProfilerProbe id="Widget:molds"><MoldsComponent /></ProfilerProbe>;'],
    ['return <EnvComponent />;', 'return <ProfilerProbe id="Widget:env"><EnvComponent /></ProfilerProbe>;'],
    ['return <TimeSeriesWidget />;', 'return <ProfilerProbe id="Widget:timeseries"><TimeSeriesWidget /></ProfilerProbe>;'],
    ['return <NativeMarkdown item={item} />;', 'return <ProfilerProbe id="Widget:markdown"><NativeMarkdown item={item} /></ProfilerProbe>;'],
  ];

  replacements.forEach(([before, after]) => {
    if (!source.includes(after)) {
      source = replaceStringOnce(source, targetNativeSurfacePath, before, after, after);
    }
  });

  if (!source.includes('<ProfilerProbe id="Widget:camera">')) {
    source = replaceRegexOnce(
      source,
      targetNativeSurfacePath,
      /return \(\n\s+<CameraComponent\n([\s\S]*?)\n\s+\/>\n\s+\);/,
      'return (\n      <ProfilerProbe id="Widget:camera">\n        <CameraComponent\n$1\n        />\n      </ProfilerProbe>\n    );',
      'Camera widget profiler wrapper',
    );
  }

  writeText(targetNativeSurfacePath, source);
};

ensureProfilerFile();
instrumentApp();
instrumentNativeSurface();
process.stdout.write(`Instrumented React Profiler in ${targetRoot}\n`);
