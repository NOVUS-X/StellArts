import io
from datetime import datetime
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.models.booking import Booking
from app.models.user import User

def generate_invoice_pdf(booking: Booking, amount: Decimal, client_user: User, artisan_user: User) -> bytes:
    """
    Generate a simple PDF invoice for a completed booking/payment release.
    Returns the PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=2))
    styles.add(ParagraphStyle(name='TitleStyle', parent=styles['Heading1'], alignment=1, spaceAfter=20))

    elements = []

    # Title
    elements.append(Paragraph("INVOICE / RECEIPT", styles['TitleStyle']))
    elements.append(Spacer(1, 0.25 * inch))

    # Header Info
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    header_data = [
        ["StellArts", f"Date: {date_str}"],
        ["Decentralized Marketplace", f"Invoice #: {str(booking.id)[:8].upper()}"],
        ["", f"Booking ID: {str(booking.id)}"],
    ]
    
    t_header = Table(header_data, colWidths=[3 * inch, 3.5 * inch])
    t_header.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 0.5 * inch))

    # Parties
    parties_data = [
        ["Bill To:", "From (Artisan):"],
        [client_user.full_name or "Client", artisan_user.full_name or "Artisan"],
        [client_user.email, artisan_user.email]
    ]
    
    t_parties = Table(parties_data, colWidths=[3 * inch, 3.5 * inch])
    t_parties.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_parties)
    elements.append(Spacer(1, 0.5 * inch))

    # Service Details
    service_name = booking.service if booking.service else "Artisan Service"
    items_data = [
        ["Description", "Amount (XLM)"],
        [service_name, str(amount)],
        ["", ""],
        ["Total", str(amount)]
    ]

    t_items = Table(items_data, colWidths=[4.5 * inch, 2 * inch])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 0.5 * inch))

    # Footer
    elements.append(Paragraph(
        "Thank you for using StellArts. Payment has been released from escrow securely via the Stellar network.",
        styles['Normal']
    ))

    # Build the PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
