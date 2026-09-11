import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserRouter, HashRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
vi.hoisted(() => {
  vi.stubGlobal('matchMedia', (media: string) => ({
    media, matches: false, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
    dispatchEvent: () => true,
  }));
  vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} });
});
import { Link as GrafanaLink } from '@grafana/ui';
import { EmbeddedScene, SceneApp, SceneAppPage, SceneReactObject } from '@grafana/scenes';
import { HistoryWrapper, LocationServiceProvider } from '@grafana/runtime';
afterAll(() => vi.unstubAllGlobals());

function Home() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/dashboard')}>Open dashboard</button>;
}
function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  return <>
    <output data-testid="location">{location.pathname + location.search}</output>
    <output data-testid="state">{JSON.stringify(location.state)}</output>
    <button onClick={() => navigate('/dashboard?tab=layout', { replace: true, state: { edit: true } })}>Replace location</button>
  </>;
}
function RouteFixture() {
  return <Routes><Route path="/" element={<Home />} /><Route path="/dashboard" element={<Dashboard />} /></Routes>;
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, '', '/');
});

describe('standalone public Router 7 API', () => {
  it('preserves BrowserRouter navigation and replacement state', async () => {
    window.history.replaceState(null, '', '/');
    render(<BrowserRouter><RouteFixture /></BrowserRouter>);
    fireEvent.click(screen.getByText('Open dashboard'));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/dashboard'));
    expect(window.location.pathname).toBe('/dashboard');
    fireEvent.click(screen.getByText('Replace location'));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/dashboard?tab=layout'));
    expect(screen.getByTestId('state')).toHaveTextContent('{"edit":true}');
  });

  it('preserves HashRouter navigation without changing the document path', async () => {
    window.history.replaceState(null, '', '/index.html#/');
    render(<HashRouter><RouteFixture /></HashRouter>);
    fireEvent.click(screen.getByText('Open dashboard'));
    await waitFor(() => expect(window.location.hash).toBe('#/dashboard'));
    expect(window.location.pathname).toBe('/index.html');
    fireEvent.click(screen.getByText('Replace location'));
    await waitFor(() => expect(window.location.hash).toBe('#/dashboard?tab=layout'));
    expect(screen.getByTestId('state')).toHaveTextContent('{"edit":true}');
  });
});

describe('real Grafana Link through the official Router 7 alias', () => {
  it.each([BrowserRouter, HashRouter])('shares the app context, forwards refs and performs internal navigation', async (Router) => {
    window.history.replaceState(null, '', Router === HashRouter ? '/index.html#/' : '/');
    const ref = createRef<HTMLAnchorElement>();
    render(<Router><GrafanaLink ref={ref} href="/dashboard?tab=layout">Grafana dashboard</GrafanaLink><RouteFixture /></Router>);
    expect(ref.current).toBe(screen.getByRole('link'));
    expect(ref.current).toHaveAttribute('href', Router === HashRouter ? '#/dashboard?tab=layout' : '/dashboard?tab=layout');
    fireEvent.click(screen.getByRole('link'));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/dashboard?tab=layout'));
    expect(window.location.pathname).toBe(Router === HashRouter ? '/index.html' : '/dashboard');
  });

  it('keeps safe external URLs and sanitizes script URLs', () => {
    render(<BrowserRouter>
      <GrafanaLink href="https://example.invalid/path?x=1" target="_blank" rel="noopener noreferrer">External</GrafanaLink>
      <GrafanaLink href="javascript:alert(1)">Unsafe</GrafanaLink>
    </BrowserRouter>);
    expect(screen.getByText('External')).toHaveAttribute('href', 'https://example.invalid/path?x=1');
    expect(screen.getByText('External')).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('Unsafe')).not.toHaveAttribute('href', expect.stringMatching(/^javascript:/i));
  });

  it('respects caller cancellation and does not hijack modified clicks', () => {
    render(<BrowserRouter>
      <GrafanaLink href="/dashboard" onClick={(event) => event.preventDefault()}>Cancelled</GrafanaLink>
      <GrafanaLink href="/dashboard">Modified</GrafanaLink><RouteFixture />
    </BrowserRouter>);
    fireEvent.click(screen.getByText('Cancelled'));
    expect(window.location.pathname).toBe('/');
    // Prevent jsdom's default document navigation AFTER React handles the event.
    // Router must leave these events untouched for the browser's new-tab action.
    for (const modifier of ['ctrlKey', 'metaKey', 'shiftKey', 'altKey']) {
      const link = screen.getByText('Modified');
      const event = new MouseEvent('click', { bubbles: true, cancelable: true, [modifier]: true });
      const preventDocumentNavigation = (e: Event) => { expect(e.defaultPrevented).toBe(false); e.preventDefault(); };
      document.addEventListener('click', preventDocumentNavigation, { once: true });
      fireEvent(link, event);
      expect(window.location.pathname).toBe('/');
    }
  });

  it('renders real Scenes nested routes in the same Router context', async () => {
    window.history.replaceState(null, '', '/dashboard');
    const page = new SceneAppPage({
      title: 'Scenes routing contract', url: '/dashboard', routePath: '/dashboard/*',
      getScene: () => new EmbeddedScene({ body: new SceneReactObject({ component: () => <div>Real Scenes route body</div> }) }),
    });
    const app = new SceneApp({ pages: [page] });
    const service = new HistoryWrapper();
    render(<BrowserRouter><LocationServiceProvider service={service}><app.Component model={app} /></LocationServiceProvider></BrowserRouter>);
    expect(await screen.findByText('Real Scenes route body')).toBeInTheDocument();
  });
});
