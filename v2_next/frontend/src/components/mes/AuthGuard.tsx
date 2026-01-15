import React, { useState, useEffect } from 'react';
import { LoginModal } from './LoginModal';

interface AuthGuardProps {
    children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [checking, setChecking] = useState(true);

    useEffect(() => {
        // Simple Session Check
        const auth = sessionStorage.getItem('mes_auth');
        if (auth === 'true') {
            setIsAuthenticated(true);
        }
        setChecking(false);
    }, []);

    const handleLoginSuccess = () => {
        sessionStorage.setItem('mes_auth', 'true');
        setIsAuthenticated(true);
    };

    if (checking) {
        return null; // Or a loading spinner
    }

    if (!isAuthenticated) {
        return <LoginModal onLogin={handleLoginSuccess} />;
    }

    return <>{children}</>;
};
