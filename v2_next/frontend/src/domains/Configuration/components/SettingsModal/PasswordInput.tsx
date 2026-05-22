import type { CSSProperties, ChangeEvent } from 'react';

const PASSWORD_INPUT_WRAP_STYLE: CSSProperties = { position: 'relative' };
const PASSWORD_INPUT_BASE_STYLE: CSSProperties = { paddingRight: '40px' };
const PASSWORD_TOGGLE_STYLE: CSSProperties = {
  position: 'absolute',
  right: '8px',
  top: '50%',
  transform: 'translateY(-50%)',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '4px',
  opacity: 0.7,
  fontSize: '1rem',
};

const PASSWORD_STRENGTH_COLORS = ['#ef4444', '#f59e0b', '#22c55e'] as const;
const PASSWORD_STRENGTH_LEVELS = [1, 2, 3] as const;

type PasswordStrength = 1 | 2 | 3;

export const getPasswordStrength = (password: string): PasswordStrength => {
  const trimmed = password.trim();
  if (trimmed.length < 4) {
    return 1;
  }
  if (trimmed.length < 8) {
    return 2;
  }
  return 3;
};

export const getPasswordStrengthLabel = (strength: PasswordStrength): string => {
  if (strength === 1) {
    return '강도: 약함 (4자 이상 권장)';
  }
  if (strength === 2) {
    return '강도: 보통 (8자 이상 권장)';
  }
  return '강도: 강함';
};

interface PasswordInputProps {
  value: string;
  visible: boolean;
  placeholder: string;
  onChange: (value: string) => void;
  onToggleVisible: () => void;
  disabled?: boolean;
  style?: CSSProperties;
}

export const PasswordInput = ({
  value,
  visible,
  placeholder,
  onChange,
  onToggleVisible,
  disabled = false,
  style,
}: PasswordInputProps): JSX.Element => (
  <div style={PASSWORD_INPUT_WRAP_STYLE}>
    <input
      type={visible ? 'text' : 'password'}
      placeholder={placeholder}
      value={value}
      onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
      disabled={disabled}
      style={{ ...PASSWORD_INPUT_BASE_STYLE, ...style }}
    />
    <button
      type="button"
      onClick={onToggleVisible}
      style={PASSWORD_TOGGLE_STYLE}
      title={visible ? '숨기기' : '표시'}
      aria-label={visible ? '비밀번호 숨기기' : '비밀번호 표시'}
      aria-pressed={visible}
    >
      {visible ? '🙈' : '👁️'}
    </button>
  </div>
);

interface PasswordStrengthIndicatorProps {
  password: string;
}

export const PasswordStrengthIndicator = ({
  password,
}: PasswordStrengthIndicatorProps): JSX.Element | null => {
  if (password.trim().length === 0) {
    return null;
  }

  const strength = getPasswordStrength(password);
  const activeColor = PASSWORD_STRENGTH_COLORS[strength - 1];

  return (
    <div style={{ marginTop: '6px' }}>
      <div style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
        {PASSWORD_STRENGTH_LEVELS.map((level) => {
          const active = level <= strength;
          return (
            <div
              key={level}
              style={{
                flex: 1,
                height: '4px',
                borderRadius: '2px',
                backgroundColor: active ? activeColor : 'var(--border-muted)',
                transition: 'background-color 0.2s',
              }}
            />
          );
        })}
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        {getPasswordStrengthLabel(strength)}
      </span>
    </div>
  );
};
