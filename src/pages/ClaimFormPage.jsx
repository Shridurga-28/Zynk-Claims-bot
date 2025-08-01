import React, { useState } from 'react';
import { motion } from 'framer-motion';
import '../App.css';

const ClaimFormPage = () => {
  const [form, setForm] = useState({ name: '', email: '', policy: '', description: '' });
  const [success, setSuccess] = useState(false);
  const [imagePreview, setImagePreview] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSuccess(true);
    setTimeout(() => setSuccess(false), 3000);
    setForm({ name: '', email: '', policy: '', description: '' });
    setImagePreview(null);
  };

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  return (
    <motion.div
      className="claim-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="claim-form-glass"
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        <h2 className="glow-title">📄 Submit Your Claim</h2>
        <form onSubmit={handleSubmit}>
          <input placeholder="Full Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <input placeholder="Email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          <input placeholder="Policy Number" value={form.policy} onChange={e => setForm({ ...form, policy: e.target.value })} />
          <textarea placeholder="Issue description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <input type="file" onChange={handleFile} />
          {imagePreview && (
            <motion.img
              src={imagePreview}
              alt="Preview"
              className="image-preview"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.4 }}
            />
          )}
          <p className="ocr-placeholder">🧠 OCR will parse this image after submission</p>
          <button type="submit">Submit</button>
          {success && <p className="success">✅ Claim submitted!</p>}
        </form>
      </motion.div>
    </motion.div>
  );
};

export default ClaimFormPage;
