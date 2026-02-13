export interface OverridePayload {
  enabled: boolean;
  password?: string;
  actor: string;
}

export interface PasswordVerificationResponse {
  ok: boolean;
}

export type ConfigPayload = Record<string, unknown>;
export type GenericApiResponse = Record<string, unknown>;
