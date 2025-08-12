import React, { useState, useEffect, useRef } from "react";
import '../App.css';

const API_BASE = "http://localhost:8000"; // Or your backend URL

const FAQs = [
  { q: "How long does a claim take?", a: "It typically takes 3–5 working days after verification." },
  { q: "What documents are needed?", a: "You’ll need ID proof, policy copy, and supporting documents like bills or reports." },
  { q: "Can I modify a submitted claim?", a: "Yes, contact support within 24 hours with your Claim ID." }
];

function App() {
  const [form, setForm] = useState({ name: '', email: '', policy: '', description: '' });
  const [file, setFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [success, setSuccess] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);
  const [chat, setChat] = useState('');
  const [messages, setMessages] = useState([]);
  const [recognitionActive, setRecognitionActive] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if ("webkitSpeechRecognition" in window) {
      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setChat(transcript);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  const handleVoiceInput = () => {
    if (recognitionRef.current) {
      recognitionRef.current.start();
      setRecognitionActive(true);
      recognitionRef.current.onend = () => setRecognitionActive(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSuccess(true);
    setTimeout(() => setSuccess(false), 5000);
    setForm({ name: '', email: '', policy: '', description: '' });
    setFile(null);
    setImagePreview(null);
  };

  const handleFileChange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

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

};


  const handleSend = () => {
    if (chat.trim()) {
      setMessages([...messages, { sender: "user", text: chat }]);
      setChat('');
      setTimeout(() => {
        setMessages(prev => [...prev, { sender: "bot", text: "🤖 I am processing your request..." }]);
      }, 1000);
    }
  };

  return (
    <div className="app-wrapper">
      <header className="header">
        <h1>🤖 EasyClaim - Smart Insurance Assistance</h1>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <h3>🔍 Navigation</h3>
          <ul>
            <li>📄 Claim Form</li>
            <li>📁 Previous Claims</li>
            <li>❓ FAQs</li>
            <li>🖼️ Upload Image</li>
            <li>🔊 Voice Assist</li>
          </ul>
        </aside>

        <main className="main-content">
          <section className="chat-section">
            <h2>🤖 Ask EasyClaim Bot</h2>
            <div className="chat-box">
              {messages.map((msg, idx) => (
                <div key={idx} className={`msg ${msg.sender}`}>{msg.text}</div>
              ))}
            </div>
            <div className="chat-input">
              <input
                type="text"
                value={chat}
                onChange={(e) => setChat(e.target.value)}
                placeholder="Type your question..."
              />
              <button onClick={handleSend}>Send</button>
              <button onClick={handleVoiceInput} disabled={recognitionActive}>
                🎤 {recognitionActive ? 'Listening...' : 'Speak'}
              </button>
            </div>
          </section>

          <section className="claim-form">
            <h2>📄 Submit a Claim</h2>
            <form onSubmit={handleSubmit}>
              <input type="text" placeholder="Full Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
              <input type="email" placeholder="Email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
              <input type="text" placeholder="Policy Number" value={form.policy} onChange={e => setForm({ ...form, policy: e.target.value })} required />
              <textarea placeholder="Describe your issue..." value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required />
              <input type="file" onChange={handleFileChange} />
              {imagePreview && <img src={imagePreview} alt="Preview" className="image-preview" />}
              <p className="ocr-placeholder">🧠 OCR will parse this image after upload...</p>
              <button type="submit">Submit</button>
              {success && <p className="success">✅ Claim submitted!</p>}
            </form>
          </section>

          <section className="faq-section">
            <h2>❓ Frequently Asked Questions</h2>
            {FAQs.map((faq, i) => (
              <div key={i} className="faq-item">
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)}>{faq.q}</button>
                {openFaq === i && <p className="faq-answer">{faq.a}</p>}
              </div>
            ))}
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
