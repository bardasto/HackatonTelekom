import React, { useState, useEffect } from 'react';
import PdfUpload from './components/PdfUpload';
import PdfViewer from './components/PdfViewer';
import './App.css'; // Убедись, что этот файл содержит все стили, которые мы обсуждали

// Читаем базовый URL API из переменной окружения или используем значение по умолчанию
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1';

function App() {
  // Состояние для оригинального объекта файла PDF (File object)
  const [pdfFile, setPdfFile] = useState(null); 
  // Состояние для URL объекта, созданного из pdfFile, для отображения в react-pdf
  const [pdfFileUrl, setPdfFileUrl] = useState(''); 
  // Состояние для хранения результата анализа от AI
  const [analysisResult, setAnalysisResult] = useState(null);
  // Состояние для индикатора загрузки во время анализа
  const [isLoading, setIsLoading] = useState(false);
  // Состояние для отображения сообщений об ошибках
  const [error, setError] = useState('');

  // Обработчик выбора файла и запуска анализа
  const handleFileAnalysis = async (file) => {
    // Если файл не выбран (например, пользователь отменил выбор), сбрасываем состояния
    if (!file) {
      setPdfFile(null);
      if (pdfFileUrl) URL.revokeObjectURL(pdfFileUrl); // Освобождаем предыдущий Object URL
      setPdfFileUrl('');
      setAnalysisResult(null);
      setError('');
      return;
    }
    
    // Сохраняем оригинальный файл
    setPdfFile(file); 
    
    // Освобождаем предыдущий Object URL, если он был, и создаем новый
    if (pdfFileUrl) URL.revokeObjectURL(pdfFileUrl); 
    setPdfFileUrl(URL.createObjectURL(file));
    
    // Устанавливаем состояния для начала процесса анализа
    setIsLoading(true);
    setError('');
    setAnalysisResult(null); // Очищаем предыдущие результаты

    // Создаем FormData для отправки файла на бэкенд
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Отправляем запрос на эндпоинт анализа
      const response = await fetch(`${API_BASE_URL}/analyze-pdf/`, {
        method: 'POST',
        body: formData,
        // Заголовок 'Content-Type': 'multipart/form-data' устанавливается браузером автоматически для FormData
      });

      // Проверяем, успешен ли ответ сервера
      if (!response.ok) {
        let errorData;
        try {
          // Пытаемся получить детали ошибки из JSON ответа бэкенда
          errorData = await response.json();
        } catch (e) {
          // Если ответ не JSON, формируем ошибку на основе статуса
          errorData = { detail: `Server responded with status: ${response.status} ${response.statusText}` };
        }
        // Выбрасываем ошибку, чтобы она была поймана в блоке catch
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      // Если ответ успешен, получаем данные (результат анализа)
      const data = await response.json();
      setAnalysisResult(data);
    } catch (err) {
      // Обрабатываем любые ошибки, возникшие во время запроса или обработки ответа
      console.error("Error uploading or analyzing file:", err);
      setError(err.message || 'Failed to analyze PDF. Check console for more details.');
    } finally {
      // В любом случае (успех или ошибка) убираем индикатор загрузки
      setIsLoading(false);
    }
  };

  // useEffect для очистки Object URL при размонтировании компонента или изменении pdfFileUrl
  // Это важно для предотвращения утечек памяти в браузере
  useEffect(() => {
    return () => {
      if (pdfFileUrl) {
        URL.revokeObjectURL(pdfFileUrl);
      }
    };
  }, [pdfFileUrl]); // Зависимость: эффект будет запускаться при изменении pdfFileUrl

  return (
    <div className="App"> {/* Корневой div приложения */}
      <header className="App-header"> {/* Хедер приложения */}
        <h1>AI PDF Proofreader Bot</h1>
      </header>
      <div className="app-wrapper"> {/* Обертка для основного контента, создающая "рамку" */}
        <main> {/* Основная контентная часть */}
          <PdfUpload onFileSelect={handleFileAnalysis} disabled={isLoading} />
          
          {/* Отображение индикатора загрузки */}
          {isLoading && (
            <div className="message-bubble loading-spinner">
              The bot is thinking... Analyzing your PDF, please wait!
            </div>
          )}
          
          {/* Отображение сообщения об ошибке */}
          {error && (
            <div className="message-bubble error-message">
              <strong>Oops! An error occurred:</strong> {error}
            </div>
          )}
          
          {/* Отображение компонента просмотра PDF и результатов, если есть URL файла и результаты анализа */}
          {pdfFileUrl && analysisResult && (
            <PdfViewer 
              pdfFileUrl={pdfFileUrl} 
              analysisResult={analysisResult}
              originalPdfFile={pdfFile} // Передаем оригинальный файл для функции скачивания
            />
          )}
          
          {/* Отображение приветственного сообщения, если файл еще не загружен и нет ошибок/загрузки */}
          {!pdfFileUrl && !isLoading && !error && (
            <div className="message-bubble info-message">
              Hello! I'm your PDF Proofreader Bot. Upload a PDF file, and I'll check it for errors.
            </div>
          )}
        </main>
        {/* 
        <footer className="app-footer"> // Пример футера, если он понадобится
          © 2024 Your Company
        </footer> 
        */}
      </div> {/* Конец .app-wrapper */}
    </div>
  );
}

export default App;