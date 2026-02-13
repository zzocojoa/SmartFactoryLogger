import type { ConfigSnapshot } from '../types';

export const buildSettingsFingerprint = (snapshot: ConfigSnapshot): string => {
  return JSON.stringify({
    config_path: snapshot.config_path ?? '',
    encoding: snapshot.encoding ?? '',
    restart_required: Boolean(snapshot.restart_required),
    values: snapshot.values ?? {},
    meta: snapshot.meta ?? {},
  });
};
