// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { CSSTransition, TransitionGroup } from 'react-transition-group';
import HomePage from './pages/home';
import ChatBotPage from './pages/ChatBotPage';
import ClaimFormPage from './pages/ClaimFormPage';
import FAQPage from './pages/FAQPage';
import './App.css';
import './transitions.css';

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <TransitionGroup component={null}>
      <CSSTransition
        key={location.pathname}
        classNames="fade"
        timeout={300}
        nodeRef={{ current: null }} // 👈 Fix the warning by disabling findDOMNode
      >
        <div>
          <Routes location={location}>
            <Route path="/" element={<HomePage />} />
            <Route path="/chat" element={<ChatBotPage />} />
            <Route path="/claim" element={<ClaimFormPage />} />
            <Route path="/faq" element={<FAQPage />} />
          </Routes>
        </div>
      </CSSTransition>
    </TransitionGroup>
  );
}

function App() {
  return (
    <Router>
      <AnimatedRoutes />
    </Router>
  );
}

export default App;