from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from io import BytesIO

def apply_corrections_to_text(original_text: str, errors: list) -> str:
    """
    Применяет исправления к тексту.
    Это очень упрощенная версия. В реальности нужно более умное сопоставление.
    Для лучшего результата, AI должен возвращать не только snippet, но и его позицию.
    Здесь мы просто заменяем первое вхождение оригинального сниппета.
    """
    corrected_text = original_text
    # Сортируем ошибки по длине оригинального сниппета (от длинных к коротким)
    # чтобы избежать проблем, когда короткий сниппет является частью длинного
    sorted_errors = sorted(errors, key=lambda e: len(e.get("original_snippet", "")), reverse=True)

    for error in sorted_errors:
        original_snippet = error.get("original_snippet")
        corrected_snippet = error.get("corrected_snippet")
        if original_snippet and corrected_snippet and original_snippet != "N/A":
            # Заменяем только первое вхождение, чтобы не испортить другие части текста, если сниппеты повторяются
            # В идеале, нам нужны индексы или более точные локаторы ошибок от AI
            if original_snippet in corrected_text:
                 corrected_text = corrected_text.replace(original_snippet, corrected_snippet, 1)
    return corrected_text

def create_pdf_with_corrected_text(pages_data: list, all_errors: list) -> BytesIO:
    """
    Создает новый PDF файл с текстом, к которому применены исправления.
    pages_data: [{'page_number': int, 'text': str}, ...]
    all_errors: список всех ошибок из AI анализа
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = []

    # Группируем ошибки по страницам для удобства
    errors_by_page = {}
    for error in all_errors:
        page_num = error.get("page_number")
        if page_num not in errors_by_page:
            errors_by_page[page_num] = []
        errors_by_page[page_num].append(error)

    first_page = True
    for page_content in pages_data:
        original_page_text = page_content.get("text", "")
        page_num = page_content.get("page_number")

        errors_on_this_page = errors_by_page.get(page_num, [])
        
        # Применяем исправления к тексту этой страницы
        # Этот шаг самый сложный для идеального результата.
        # Текущая реализация apply_corrections_to_text очень базовая.
        corrected_page_text = apply_corrections_to_text(original_page_text, errors_on_this_page)

        if not first_page:
            story.append(PageBreak())
        first_page = False
        
        story.append(Paragraph(f"Page {page_num} (Corrected)", styles['h2']))
        story.append(Spacer(1, 0.2 * inch))
        
        # Разбиваем текст на параграфы (по пустым строкам) и добавляем в PDF
        text_paragraphs = corrected_page_text.split('\n\n')
        for para_text in text_paragraphs:
            if para_text.strip():
                p = Paragraph(para_text.replace('\n', '<br/>'), styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer