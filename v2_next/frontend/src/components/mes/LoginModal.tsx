import React, { useState, useEffect, useRef } from 'react';

interface LoginModalProps {
    onLogin: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ onLogin }) => {
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        // Auto-focus input on mount
        setTimeout(() => inputRef.current?.focus(), 100);
    }, []);

    const handleSubmit = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!password) return;

        setLoading(true);
        setError(null);

        try {
            const response = await fetch('http://localhost:8000/api/mes/auth/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password }),
            });

            const data = await response.json();

            if (data.success) {
                onLogin();
            } else {
                setError(data.message || 'Invalid Password');
            }
        } catch (err) {
            setError('Connection failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="custom-modal-overlay" style={{ backdropFilter: 'blur(8px)', backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="custom-modal-content info" style={{ maxWidth: '400px', width: '90%' }}>
                <div className="custom-modal-header" style={{ justifyContent: 'center', paddingBottom: '1rem' }}>
                    <h2 className="custom-modal-title" style={{ fontSize: '1.5rem', color: 'var(--accent-main)' }}>
                        MES Dashboard
                    </h2>
                </div>
                
                <div className="custom-modal-body" style={{ textAlign: 'center' }}>
                    <p style={{ marginBottom: '1.5rem', color: '#aaa' }}>
                        Enter access password defined in config.ini
                    </p>
                    
                    <form onSubmit={handleSubmit}>
                        <div style={{ position: 'relative', marginBottom: '1rem' }}>
                            <input
                                ref={inputRef}
                                type="password"
                                className="custom-modal-input"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Password"
                                style={{ 
                                    width: '100%', 
                                    padding: '12px', 
                                    textAlign: 'center',
                                    fontSize: '1.1rem',
                                    letterSpacing: '0.2rem'
                                }}
                            />
                        </div>

                        {error && (
                            <div style={{ color: 'var(--state-danger)', marginBottom: '1rem', fontSize: '0.9rem' }}>
                                {error}
                            </div>
                        )}

                        <div className="custom-modal-actions" style={{ justifyContent: 'center', marginTop: '1rem' }}>
                            <button 
                                type="submit" 
                                className="custom-modal-btn confirm info"
                                disabled={loading}
                                style={{ width: '100%', padding: '12px', fontSize: '1rem' }}
                            >
                                {loading ? 'Verifying...' : 'Access Dashboard'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
};
