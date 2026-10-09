import type { HealthReceiptTiming, HealthSnapshot } from '../../../shared/types';

export interface HealthState {
  health: HealthSnapshot | null;
  healthReceipt: HealthReceiptTiming | null;
  spotAgeFloor?: SpotAgeFloor | null;
}

interface SpotAgeFloor {
  receivedAtMonotonicMs: number;
  spot_snapshot_age_ms: number | null;
  spot_value_age_ms: number | null;
}

export const SUPERSEDED_HEALTH_REQUEST = Symbol('supersededHealthRequest');

export interface SpotObservation {
  serviceId: string;
  pollSequence: number;
  completed: boolean;
  sourceStale: boolean;
  freshnessThresholdSec?: number;
}

interface SpotObservationDecision {
  observation: SpotObservation | null;
  accepted: boolean;
  sameObservation: boolean;
}

export const assessSpotObservation = (
  snapshot: HealthSnapshot,
  previousObservation: SpotObservation | null,
  retiredServices: ReadonlySet<string>,
  authoritative = false,
): SpotObservationDecision => {
  const serviceId = snapshot.spot_temperature?.spot_service_instance_id;
  const pollSequence = snapshot.spot_temperature?.spot_poll_seq;
  if (typeof serviceId !== 'string' || serviceId.length === 0
    || typeof pollSequence !== 'number' || !Number.isSafeInteger(pollSequence) || pollSequence < 0) {
    return { observation: null, accepted: true, sameObservation: false };
  }

  const sameService = previousObservation?.serviceId === serviceId;
  const sameObservation = sameService && previousObservation.pollSequence === pollSequence;
  const pollStatus = snapshot.spot_temperature?.spot_poll_status;
  const completed = ['success', 'timeout', 'connection_error', 'http_error', 'config_missing'].includes(pollStatus ?? '');
  const threshold = snapshot.spot_temperature?.spot_poll_freshness_threshold_sec;
  const validPolicy = threshold === undefined || (typeof threshold === 'number' && Number.isFinite(threshold) && threshold > 0);
  const samePolicy = sameObservation && (!validPolicy || threshold === previousObservation.freshnessThresholdSec);
  return {
    observation: { serviceId, pollSequence,
      completed: completed || Boolean(sameObservation && previousObservation.completed),
      sourceStale: Boolean(samePolicy && previousObservation.sourceStale)
        || (validPolicy && snapshot.spot_temperature?.spot_source_freshness === 'stale'),
      freshnessThresholdSec: validPolicy ? threshold : sameObservation ? previousObservation.freshnessThresholdSec : undefined,
    },
    accepted: (authoritative || !retiredServices.has(serviceId))
      && (!sameService || pollSequence >= previousObservation.pollSequence)
      && !(sameObservation && previousObservation.completed && pollStatus === 'not_attempted'),
    sameObservation,
  };
};

export const includeHealthDeliveryAge = (snapshot: HealthSnapshot, durationMs: number): HealthSnapshot => {
  if (!snapshot.spot_temperature) return snapshot;
  const spot = { ...snapshot.spot_temperature };
  for (const key of ['spot_snapshot_age_ms', 'spot_value_age_ms'] as const) {
    const age = spot[key];
    if (!Number.isFinite(durationMs) || durationMs < 0) spot[key] = null;
    else if (typeof age === 'number' && Number.isFinite(age) && age >= 0) spot[key] = age + durationMs;
  }
  return { ...snapshot, spot_temperature: spot };
};

export const buildHealthReceipt = (
  sentAtMs: number | undefined,
  receivedAtWallClockMs: number,
  receivedAtMonotonicMs: number,
): HealthReceiptTiming => {
  const delayMs = sentAtMs === undefined ? 0
    : typeof sentAtMs === 'number' && Number.isFinite(sentAtMs) ? receivedAtWallClockMs - sentAtMs : NaN;
  return {
    receivedAtMonotonicMs,
    ageAtReceiptMs: Number.isFinite(delayMs) && delayMs >= 0 ? delayMs : null,
  };
};

export const mergeHealthSnapshot = (
  previous: HealthState,
  snapshot: HealthSnapshot,
  receipt: HealthReceiptTiming,
  { accepted, sameObservation, observation }: SpotObservationDecision,
): HealthState => {
  if (!accepted) return {
    ...previous,
    health: {
      ...snapshot,
      spot_temperature: previous.health?.spot_temperature,
      comm: { ...snapshot.comm, spot: previous.health?.comm?.spot },
    },
    healthReceipt: previous.healthReceipt,
  };

  // Re-reading one poll may update other health fields, but must not
  // rejuvenate its observation or cached value when another sender lags.
  let displaySpot = snapshot.spot_temperature;
  let spotAgeFloor = sameObservation || !observation ? previous.spotAgeFloor ?? null : null;
  if (observation?.sourceStale && displaySpot?.spot_source_freshness === 'fresh') {
    displaySpot = { ...displaySpot, spot_source_freshness: 'stale' };
  }
  if (observation && receipt.ageAtReceiptMs !== null) {
    const elapsed = spotAgeFloor ? Math.max(0, receipt.receivedAtMonotonicMs - spotAgeFloor.receivedAtMonotonicMs) : 0;
    const nextFloor: SpotAgeFloor = { receivedAtMonotonicMs: receipt.receivedAtMonotonicMs,
      spot_snapshot_age_ms: null, spot_value_age_ms: null };
    for (const key of ['spot_snapshot_age_ms', 'spot_value_age_ms'] as const) {
      const oldAge = spotAgeFloor?.[key];
      const newAge = snapshot.spot_temperature?.[key];
      const oldFloor = oldAge == null ? null : oldAge + elapsed;
      nextFloor[key] = oldFloor;
      if (typeof newAge === 'number' && Number.isFinite(newAge) && newAge >= 0) {
        const effectiveAge = Math.max(newAge + receipt.ageAtReceiptMs, oldFloor ?? 0);
        nextFloor[key] = effectiveAge;
        if (effectiveAge - receipt.ageAtReceiptMs > newAge) {
          displaySpot = { ...displaySpot, [key]: effectiveAge - receipt.ageAtReceiptMs };
        }
      }
    }
    spotAgeFloor = nextFloor;
  }
  return { health: { ...snapshot, spot_temperature: displaySpot }, healthReceipt: receipt, spotAgeFloor };
};
