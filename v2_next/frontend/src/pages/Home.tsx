import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Home.css';

const Home: React.FC = () => {
  const navigate = useNavigate();

  const handleEnterDashboard = () => {
    navigate('/dashboard');
  };

  return (
    <div className="home-container">
      {/* Background Decor */}
      <div className="home-bg-glow" />
      <div className="home-bg-glow-2" />

      {/* Main Content */}
      <div className="home-content">
        <div>
          <h1 className="home-title">Smart Factory Logger</h1>
          <p className="home-subtitle">
            Advanced Real-time Monitoring & Data Analytics System
          </p>
        </div>

        <button className="cta-button" onClick={handleEnterDashboard}>
          Launch Dashboard
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M13.5 4.5L21 12M21 12L13.5 19.5M21 12H3"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <footer className="home-footer">
        © 2026 Smart Factory Logger System v2.0
      </footer>
    </div>
  );
};

export default Home;
