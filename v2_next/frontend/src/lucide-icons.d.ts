// Allows TypeScript to recognize dynamic imports from the lucide-react esm dist folder without losing type hints.
declare module 'lucide-react/dist/esm/icons/*' {
  import { LucideIcon } from 'lucide-react';
  const Icon: LucideIcon;
  export default Icon;
}
