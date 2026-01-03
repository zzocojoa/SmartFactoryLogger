import * as RouterDom from 'react-router-dom/dist/index.js';
import { useLocation, useNavigate } from 'react-router-dom/dist/index.js';

export * from 'react-router-dom/dist/index.js';
export default RouterDom;

type HistoryLike = {
  location: ReturnType<typeof useLocation>;
  push: (to: any, state?: any) => void;
  replace: (to: any, state?: any) => void;
  go: (delta: number) => void;
  back: () => void;
  forward: () => void;
  goBack: () => void;
  goForward: () => void;
  listen: () => () => void;
  block: () => () => void;
  createHref: (to: any) => string;
};

export function useHistory(): HistoryLike {
  const navigate = useNavigate();
  const location = useLocation();

  const createHref = (to: any) => {
    if (typeof to === 'string') {
      return to;
    }
    const pathname = to?.pathname ?? '';
    const search = to?.search ?? '';
    const hash = to?.hash ?? '';
    return `${pathname}${search}${hash}`;
  };

  return {
    location,
    push: (to, state) => navigate(to, { state }),
    replace: (to, state) => navigate(to, { replace: true, state }),
    go: (delta) => navigate(delta),
    back: () => navigate(-1),
    forward: () => navigate(1),
    goBack: () => navigate(-1),
    goForward: () => navigate(1),
    listen: () => () => {},
    block: () => () => {},
    createHref,
  };
}
