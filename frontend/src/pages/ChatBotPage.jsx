import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import '../App.css';

const API_BASE = "http://localhost:8000"; // Or your backend URL

const ChatBotPage = () => {
  const [chat, setChat] = useState('');
  const [messages, setMessages] = useState([]);
  const [recognitionActive, setRecognitionActive] = useState(false);
  const recognitionRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if ('webkitSpeechRecognition' in window) {
      const recognition = new window.webkitSpeechRecognition();
      recognition.lang = 'en-US';
      recognition.onresult = (e) => setChat(e.results[0][0].transcript);
      recognition.onend = () => setRecognitionActive(false);
      recognitionRef.current = recognition;
    }
  }, []);

  const handleSend = async () => {
  if (!chat.trim()) return;

  setMessages((prev) => [...prev, { sender: "user", text: chat }]);

  const res = await fetch(`${API_BASE}/chat_query`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    user_id: "demo-user",
    question: chat
  }),
});
const data = await res.json();
setMessages(prev => [...prev, { sender: "bot", text: data.reply }]);

  setChat('');
};

  const handleVoice = () => {
    if (recognitionRef.current){
      recognitionRef.current.start();
      setRecognitionActive(true);
      recognitionRef.current.onend = () => setRecognitionActive(false);
    }
  };

  return (
    <motion.div
      className="chatbot-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <button className="close-btn" onClick={() => navigate('/')}>❌</button>
      
      <motion.div
        className="chat-container"
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <h2 className="glow-title">Zynk Claims Assistant</h2>
        
        <div className="chat-box">
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              className={`msg ${msg.sender}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
            >
              {msg.text}
            </motion.div>
          ))}
        </div>

        <div className="chat-input">
          <input
            value={chat}
            onChange={e => setChat(e.target.value)}
            placeholder="Ask me anything..."
          />
          <button onClick={handleSend}>Send</button>
          <button onClick={handleVoice} disabled={recognitionActive}>
            🎤 {recognitionActive ? 'Listening...' : 'Speak'}
          </button>
        </div>
      </motion.div>

      <motion.div
        className="bottom-options"
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <button onClick={() => navigate('/faq')}>FAQs</button>
        <button onClick={() => navigate('/claim')}>Submit Claim</button>
        <button onClick={() => alert('Customer Bot coming soon!')}>Customer Bot</button>
      </motion.div>
    </motion.div>
  );
};

export default ChatBotPage;
