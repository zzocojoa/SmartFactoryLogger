export const resolveEmbedHeight = (height: string | number): string =>
  typeof height === 'number' ? `${height}px` : height;
