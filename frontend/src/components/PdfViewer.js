import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

// Убедись, что путь к worker'у правильный
pdfjs.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL}/pdf.worker.min.js`; 
// или pdfjs.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL}/pdf.worker.min.mjs`;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1';

function PdfViewer({ pdfFileUrl, analysisResult, originalPdfFile }) {
  const [numPages, setNumPages] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pdfContainerWidth, setPdfContainerWidth] = useState(0);
  const pdfWrapperRef = useRef(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const errorsForCurrentPage = useMemo(() => {
    if (analysisResult && analysisResult.errors) {
      return analysisResult.errors.filter(
        err => parseInt(String(err.page_number), 10) === currentPage
      );
    }
    return [];
  }, [analysisResult, currentPage]);

  useEffect(() => {
    const updateWidth = () => {
      if (pdfWrapperRef.current) {
        setPdfContainerWidth(pdfWrapperRef.current.offsetWidth * 0.98); 
      }
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  useEffect(() => {
    setCurrentPage(1);
    setNumPages(null);
  }, [pdfFileUrl]);

  function onDocumentLoadSuccess({ numPages: nextNumPages }) {
    setNumPages(nextNumPages);
  }

  function onDocumentLoadError(error) {
    console.error('Failed to load PDF document with react-pdf:', error.message);
  }

  const goToPrevPage = () => setCurrentPage(prevPage => Math.max(1, prevPage - 1));
  const goToNextPage = () => setCurrentPage(prevPage => Math.min(numPages, prevPage + 1));

  const handleDownloadCorrectedPdf = async () => {
    if (!originalPdfFile || !analysisResult || !analysisResult.errors) {
      alert("Cannot download corrected PDF: missing original file or analysis data.");
      return;
    }
    setIsDownloading(true);
    try {
      const formData = new FormData();
      formData.append('file', originalPdfFile);
      formData.append('errors_json_str', JSON.stringify(analysisResult.errors));

      const response = await fetch(`${API_BASE_URL}/download-corrected-pdf/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Server error during PDF download" }));
        throw new Error(errorData.detail || `Failed to download corrected PDF: ${response.status}`);
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      let filename = `corrected_${originalPdfFile.name}`;
      const disposition = response.headers.get('content-disposition');
      if (disposition && disposition.indexOf('attachment') !== -1) {
          const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
          const matches = filenameRegex.exec(disposition);
          if (matches != null && matches[1]) { 
            filename = matches[1].replace(/['"]/g, '');
          }
      }
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

    } catch (error) {
      console.error("Error downloading corrected PDF:", error);
      alert(`Error: ${error.message}`);
    } finally {
      setIsDownloading(false);
    }
  };

  // ЭКСПЕРИМЕНТАЛЬНЫЙ textRenderer
  const textRenderer = useCallback((textItem) => {
    // textItem = { str: string, dir: string, width: number, height: number, transform: number[], fontName: string }
    if (!textItem || !textItem.str) {
      // Если textItem пустой, лучше вернуть пустую строку, чтобы не было ошибок рендеринга
      return ''; 
    }

    let originalTextSegment = textItem.str;
    
    // Если нет ошибок на странице, весь текст из TextLayer должен быть "скрыт" (сделан прозрачным через CSS)
    // чтобы мы видели только текст с канваса.
    if (errorsForCurrentPage.length === 0) {
      return `<span class="pdf-original-text">${originalTextSegment}</span>`;
    }

    // Собираем все уникальные ошибочные сниппеты для текущей страницы
    const snippetsToHighlight = errorsForCurrentPage
      .map(error => error.original_snippet)
      .filter(snippet => snippet && snippet !== "N/A" && snippet.trim() !== "");

    if (snippetsToHighlight.length === 0) {
      return `<span class="pdf-original-text">${originalTextSegment}</span>`;
    }

    // Экранируем все сниппеты и создаем одно большое регулярное выражение
    // для поиска любого из этих сниппетов в textItem.str
    const escapedSnippets = snippetsToHighlight.map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const combinedRegex = new RegExp(`(${escapedSnippets.join('|')})`, 'g');

    let outputHtml = '';
    let lastIndex = 0;
    let match;

    while ((match = combinedRegex.exec(originalTextSegment)) !== null) {
      // Текст до найденной ошибки (будет скрыт CSS)
      if (match.index > lastIndex) {
        outputHtml += `<span class="pdf-original-text">${originalTextSegment.substring(lastIndex, match.index)}</span>`;
      }
      // Сама ошибка - оборачиваем в mark (будет красной)
      outputHtml += `<mark class="pdf-highlight">${match[0]}</mark>`;
      lastIndex = combinedRegex.lastIndex;
    }

    // Текст после последней ошибки (будет скрыт CSS)
    if (lastIndex < originalTextSegment.length) {
      outputHtml += `<span class="pdf-original-text">${originalTextSegment.substring(lastIndex)}</span>`;
    }
    
    // Если не было найдено ни одного совпадения в этом конкретном textItem.str,
    // но на странице есть ошибки, значит этот textItem.str - это обычный текст.
    if (outputHtml === '') {
        return `<span class="pdf-original-text">${originalTextSegment}</span>`;
    }

    return outputHtml;
  }, [errorsForCurrentPage]);

  return (
    <div className="pdf-viewer-layout">
      <div className="pdf-document-view" ref={pdfWrapperRef}>
        {pdfFileUrl && (
          <Document
            file={pdfFileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={<div className="message-bubble loading-spinner">Loading PDF document...</div>}
            error={<div className="message-bubble error-message">Failed to load PDF. Please try another file.</div>}
          >
            {pdfContainerWidth > 0 && currentPage > 0 && numPages > 0 && (
              <Page 
                pageNumber={currentPage} 
                width={pdfContainerWidth}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                customTextRenderer={textRenderer}
              />
            )}
          </Document>
        )}
        {numPages && numPages > 0 && (
          <div className="pdf-pagination">
            <button onClick={goToPrevPage} disabled={currentPage <= 1}>‹ Prev</button>
            <span> Page {currentPage} of {numPages} </span>
            <button onClick={goToNextPage} disabled={currentPage >= numPages}>Next ›</button>
          </div>
        )}
      </div>

      <div className="errors-panel">
        <h4> 
          Bot's Feedback (Page {currentPage}): 
          {errorsForCurrentPage.length > 0 
            ? ` Found ${errorsForCurrentPage.length} potential issue${errorsForCurrentPage.length > 1 ? 's' : ''}.` 
            : ''}
        </h4>
         {errorsForCurrentPage.length > 0 ? (
          <ul>
            {errorsForCurrentPage.map((err, index) => (
              <li key={`${currentPage}-${index}-${err.original_snippet}`} className="error-item">
                <p><strong>Error Type:</strong> {err.error_type || 'N/A'}</p>
                <p><strong>Found:</strong> <span className="original-snippet">{err.original_snippet || 'N/A'}</span></p>
                <p><strong>Suggestion:</strong> <span className="corrected-snippet">{err.corrected_snippet || 'N/A'}</span></p>
                <p><strong>Explanation:</strong> {err.explanation || 'N/A'}</p>
              </li>
            ))}
          </ul>
        ) : (
          <div className="message-bubble info-message" style={{textAlign: 'left', marginTop: '10px', borderLeftColor: 'var(--success-color)'}}> 
            Looks good on this page! The bot didn't detect any errors here.
          </div>
        )}
        {analysisResult && analysisResult.errors && analysisResult.errors.length > 0 && (
          <div style={{ marginTop: 'auto', paddingTop: '15px', borderTop: '1px solid var(--border-color)', textAlign: 'center' }}>
            <button 
              onClick={handleDownloadCorrectedPdf} 
              disabled={isDownloading || !originalPdfFile}
              className="pdf-upload-label"
              style={{
                backgroundColor: isDownloading ? 'var(--secondary-color)' : 'var(--success-color)',
                marginBottom: '15px'
              }}
            >
              {isDownloading ? 'Generating PDF...' : 'Download Corrected PDF'}
            </button>
            <h4 className="total-errors-summary" style={{marginTop: 0, borderTop: 'none', textAlign:'center'}}>
              Total issues in document: {analysisResult.errors.length}
            </h4>
          </div>
        )}
      </div>
    </div> 
  );
}

export default PdfViewer;