import React, { useState } from 'react';
import { motion } from 'framer-motion';
import '../App.css';

const FAQs = [
  { q: 'How long does a claim take?', a: 'Usually 3–5 business days after verification.', m: 'Fast and efficient, like me 🏃‍♀️💨' },
  { q: 'What documents are needed?', a: 'ID proof, policy, and any medical/legal supporting documents.', m: 'Better safe than sorry 📑🧐' },
  { q: 'Can I edit my claim?', a: 'Yes! You can contact support within 24 hours of submission.', m: 'Just don’t ghost us 👻' }
];

const FAQPage = () => {
  const [open, setOpen] = useState(null);

  return (
    <motion.div
      className="faq-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="faq-glass"
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <h2 className="glow-title">❓ Ask Mari - Your FAQ Assistant</h2>
        {FAQs.map((faq, i) => (
          <motion.div
            className="faq-item"
            key={i}
            layout
            transition={{ layout: { duration: 0.4, type: 'spring' } }}
          >
            <button onClick={() => setOpen(open === i ? null : i)}>{faq.q}</button>
            {open === i && (
              <motion.div
                className="faq-answer"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <p>{faq.a}</p>
                <div className="mari-comment">🤖 Mari says: <i>{faq.m}</i></div>
              </motion.div>
            )}
          </motion.div>
        ))}
      </motion.div>
    </motion.div>
  );
};

export default FAQPage;
