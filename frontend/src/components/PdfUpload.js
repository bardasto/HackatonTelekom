import React from 'react';

function PdfUpload({ onFileSelect, disabled }) {
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    
    if (file && file.type === "application/pdf") {
      onFileSelect(file);
    } else {
      onFileSelect(null);
      if (file) {
        alert("Please select a PDF file.");
      }
    }
    event.target.value = null; 
  };

  return (
    <div className="pdf-upload-container"> {/* Класс используется из App.css */}
      <label 
        htmlFor="pdf-upload-input" 
        className={`pdf-upload-label ${disabled ? 'disabled' : ''}`} /* Класс используется из App.css */
      >
        {disabled ? "Processing..." : "Select PDF File"}
      </label>
      <input 
        id="pdf-upload-input"
        type="file" 
        accept="application/pdf"
        onChange={handleFileChange} 
        disabled={disabled} 
        style={{ display: 'none' }}
      />
    </div>
  );
}

export default PdfUpload;