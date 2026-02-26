import { useState, useCallback } from 'react';

export interface UseSnapshotManagerOptions {
  pushNotification: (title: string, message: string, level: 'info' | 'warn' | 'error') => void;
  saveSnapshot: (params: { image_base64: string; name: string; format: string }) => Promise<void>;
}

export function useSnapshotManager({ pushNotification, saveSnapshot }: UseSnapshotManagerOptions) {
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  const handleSnapshot = useCallback(async () => {
    if (snapshotLoading) return;
    try {
      setSnapshotLoading(true);
      pushNotification('스냅샷', '스냅샷 생성 및 서버 저장 중...', 'info');
      
      const element = document.getElementById('root') || document.body;
      const scrollHeight = document.documentElement.scrollHeight;

      const sanitizeCss = (cssText: string) => {
        if (!cssText) return '';
        let newText = cssText.replace(/color-mix\(in\s+[a-z]+,\s*([^, ]+)[^)]*\)/gi, '$1');
        newText = newText.replace(/color\([^)]+\)/gi, '#1e1e1e');
        return newText;
      };

      const originalSheets: { link: HTMLLinkElement; disabled: boolean }[] = [];
      const originalStyleTags: { sheet: CSSStyleSheet; disabled: boolean }[] = [];
      const tempStyles: HTMLStyleElement[] = [];

      try {
        const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]')) as HTMLLinkElement[];
        const styleTags = Array.from(document.querySelectorAll('style')) as HTMLStyleElement[];
        
        await Promise.all([
          ...links.map(async (link) => {
            try {
              const href = link.href;
              if (href.startsWith('chrome-extension:') || href.startsWith('moz-extension:') || href.startsWith('edge-extension:')) {
                return;
              }
              const response = await fetch(href);
              const text = await response.text();
              const sanitizedText = sanitizeCss(text);
              const style = document.createElement('style');
              style.textContent = sanitizedText;
              style.setAttribute('data-snapshot-temp', 'true');
              tempStyles.push(style);
              originalSheets.push({ link, disabled: link.disabled });
            } catch (err) {
              console.warn('Failed to fetch/sanitize stylesheet:', link.href, err);
            }
          }),
          ...styleTags.map(async (tag) => {
            try {
              if (tag.hasAttribute('data-snapshot-temp')) return;
              const sheet = tag.sheet;
              if (!sheet) return;
              const text = tag.textContent || '';
              const sanitizedText = sanitizeCss(text);
              const style = document.createElement('style');
              style.textContent = sanitizedText;
              style.setAttribute('data-snapshot-temp', 'true');
              tempStyles.push(style);
              originalStyleTags.push({ sheet, disabled: sheet.disabled });
            } catch (e) {
              console.warn('Failed to sanitize style tag:', e);
            }
          })
        ]);

        originalSheets.forEach(item => item.link.disabled = true);
        originalStyleTags.forEach(item => item.sheet.disabled = true);
        tempStyles.forEach(style => document.head.appendChild(style));
      } catch (e) {
        console.warn('Pre-capture sanitization error:', e);
      }

      try {
        let canvas;
        const html2canvas = (await import('html2canvas')).default;
        try {
          canvas = await html2canvas(element, {
            useCORS: true,
            logging: false,
            backgroundColor: '#1E1E1E',
            imageTimeout: 10000,
            height: scrollHeight,
            windowHeight: scrollHeight,
            width: element.offsetWidth,
            windowWidth: element.offsetWidth,
            scrollY: -window.scrollY,
            onclone: (clonedDoc: Document) => {
              clonedDoc.documentElement.style.overflow = 'hidden';
              clonedDoc.body.style.overflow = 'hidden';
              const replaceColorFunctions = (text: string) => {
                if (!text) return text;
                let newText = text.replace(/color-mix\(in\s+[a-z]+,\s*([^, ]+)[^)]*\)/gi, '$1');
                newText = newText.replace(/color\([^)]+\)/gi, '#1e1e1e');
                return newText;
              };
              const allElements = Array.from(clonedDoc.querySelectorAll('*'));
              allElements.forEach(el => {
                const styleAttr = el.getAttribute('style');
                if (styleAttr && (styleAttr.includes('color(') || styleAttr.includes('color-mix('))) {
                  el.setAttribute('style', replaceColorFunctions(styleAttr));
                }
              });
            },
            ignoreElements: (el: Element) => {
              const className = el.className?.toString() || '';
              if (className.includes('scene-tooltip')) return true;
              return false;
            }
          } as any);
        } catch (initialError) {
          console.warn('Sanitized snapshot failed, retrying in Nuclear Safe Mode:', initialError);
          canvas = await html2canvas(element, {
            useCORS: true,
            logging: false,
            backgroundColor: '#121212',
            imageTimeout: 5000,
            height: scrollHeight,
            windowHeight: scrollHeight,
            width: element.offsetWidth,
            windowWidth: element.offsetWidth,
            scrollY: -window.scrollY,
            onclone: (clonedDoc: Document) => {
              clonedDoc.documentElement.style.overflow = 'hidden';
              clonedDoc.body.style.overflow = 'hidden';
              clonedDoc.querySelectorAll('link[rel="stylesheet"]').forEach(el => el.remove());
              clonedDoc.querySelectorAll('style').forEach(el => el.remove());
              clonedDoc.querySelectorAll('*').forEach(el => el.removeAttribute('style'));
              const fallbackStyle = clonedDoc.createElement('style');
              fallbackStyle.textContent = `
                body, #root, .app-container { background-color: #121212 !important; color: #ffffff !important; font-family: sans-serif !important; }
                .card-base, .MuiPaper-root, .panel-container { 
                  background-color: #1e1e1e !important; 
                  border: 1px solid #333 !important; 
                  margin: 4px !important; padding: 8px !important; 
                }
                * { border-color: #444 !important; }
                p, h1, h2, h3, span, div { color: #e0e0e0 !important; }
                .text-primary { color: #90caf9 !important; }
              `;
              clonedDoc.head.appendChild(fallbackStyle);
            }
          } as any);
        }

        const base64Data = canvas.toDataURL('image/png');
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

        canvas.toBlob((blob) => {
          if (!blob) throw new Error('Canvas to Blob conversion failed');
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          const now = new Date();
          const timestamp = now.getFullYear().toString() +
            (now.getMonth() + 1).toString().padStart(2, '0') +
            now.getDate().toString().padStart(2, '0') + '_' +
            now.getHours().toString().padStart(2, '0') +
            now.getMinutes().toString().padStart(2, '0') +
            now.getSeconds().toString().padStart(2, '0');
          link.download = `snapshot_${timestamp}.png`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          setTimeout(() => URL.revokeObjectURL(url), 100);
          if (!isLocal) {
            pushNotification('스냅샷 다운로드', '스냅샷이 내 컴퓨터에 저장되었습니다.', 'info');
          }
        }, 'image/png');

        if (isLocal) {
          try {
            const base64Content = base64Data.split(',')[1];
            await saveSnapshot({
              image_base64: base64Content,
              name: 'snapshot',
              format: 'png'
            });
            pushNotification('스냅샷 성공', '서버 설정 폴더에 저장되었습니다.', 'info');
          } catch (apiError) {
            console.error('Snapshot API failed', apiError);
            pushNotification('스냅샷 실패', '서버 저장 중 오류가 발생했습니다.', 'error');
          }
        }
      } finally {
        tempStyles.forEach(el => el.remove());
        originalSheets.forEach(item => {
          try { item.link.disabled = item.disabled; } catch(e) {}
        });
        originalStyleTags.forEach(item => {
          try { item.sheet.disabled = item.disabled; } catch(e) {}
        });
      }
    } catch (error) {
      console.error('Snapshot capture failed', error);
      pushNotification('스냅샷 실패', '화면 캡처 중 오류가 발생했습니다.', 'error');
    } finally {
      setSnapshotLoading(false);
    }
  }, [pushNotification, snapshotLoading, saveSnapshot]);

  return {
    snapshotLoading,
    handleSnapshot,
  };
}
