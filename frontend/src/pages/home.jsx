import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import '../App.css';

const HomePage = () => {
  return (
    <motion.div
      className="home-bg-image"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="home-glass-card"
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="glow-title">Welcome to Zynk</h1>
        <p className="home-subtitle">Your All-in-one AI-powered Claims Assistant.</p>

        <div className="home-nav-buttons">
          <Link to="/chat">
            <motion.button whileHover={{ scale: 1.05 }}>Chat with Zynk</motion.button>
          </Link>
          <Link to="/claim">
            <motion.button whileHover={{ scale: 1.05 }}>Submit a Claim</motion.button>
          </Link>
          <Link to="/faq">
            <motion.button whileHover={{ scale: 1.05 }}>Frequently Asked Questions</motion.button>
          </Link>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default HomePage;
