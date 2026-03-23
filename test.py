from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from datetime import datetime

# -----------------------------
# Mock data (same as JSON fields)
# -----------------------------
report = {
    "report_id": "RPT-" + datetime.now().strftime("%Y%m%d%H%M%S"),
    "contract_name": "Vendor Services Agreement",
    "contract_type": "Vendor Agreement",
    "submission_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "reviewed_by": "AgenticAI_v1",
    "version": "1.0",
    "metadata": {
        "parties": ["Company A", "Vendor B"],
        "effective_date": "2026-03-01",
        "expiry_date": "2028-03-01",
        "term": "2 years",
        "renewal_clauses": "Automatic renewal unless notice given 90 days prior",
        "penalty_liability_caps": "$500,000",
        "jurisdiction": "California, USA"
    },
    "clauses": [
        {
            "clause_id": "1",
            "clause_number": "1",
            "clause_heading": "Confidentiality",
            "raw_text": "All confidential information must be protected.",
            "canonical_title": "Confidentiality",
            "category": "IP/Confidentiality",
            "similarity_score": 0.95,
            "deviation_flag": False,
            "risk_severity": "Low",
            "suggested_redline": ""
        },
        {
            "clause_id": "2",
            "clause_number": "5",
            "clause_heading": "Liability Cap",
            "raw_text": "Maximum liability limited to $1,000,000.",
            "canonical_title": "Liability Cap",
            "category": "Liability",
            "similarity_score": 0.70,
            "deviation_flag": True,
            "risk_severity": "High",
            "suggested_redline": "Limit liability to $500,000 per standard clause"
        }
    ],
    "risk_register": {
        "total_clauses": 2,
        "high_risk_count": 1,
        "medium_risk_count": 0,
        "low_risk_count": 1,
        "risk_summary": {
            "high_risk": ["Liability Cap"],
            "medium_risk": [],
            "low_risk": ["Confidentiality"]
        }
    },
    "recommendations": {
        "overall_recommendations": "Review high-risk clauses and apply standard redlines before signing.",
        "clauses_to_redline": ["2"]
    }
}

# -----------------------------
# Function to create PDF
# -----------------------------
def generate_pdf(report, filename="mock_legal_risk_brief.pdf"):
    c = canvas.Canvas(filename, pagesize=LETTER)
    width, height = LETTER
    y = height - 40

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Legal Risk Brief: {report['contract_name']}")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Report ID: {report['report_id']}")
    y -= 15
    c.drawString(40, y, f"Contract Type: {report['contract_type']}")
    y -= 15
    c.drawString(40, y, f"Reviewed By: {report['reviewed_by']}")
    y -= 15
    c.drawString(40, y, f"Submission Date: {report['submission_date']}")
    y -= 30

    # Metadata
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Contract Metadata:")
    y -= 15
    c.setFont("Helvetica", 10)
    for key, value in report["metadata"].items():
        c.drawString(50, y, f"{key.replace('_',' ').title()}: {value}")
        y -= 15
    y -= 10

    # Clauses
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Clause Analysis:")
    y -= 15
    c.setFont("Helvetica", 10)
    for clause in report["clauses"]:
        c.drawString(50, y, f"{clause['clause_number']}. {clause['clause_heading']} ({clause['risk_severity']})")
        y -= 12
        c.drawString(60, y, f"Text: {clause['raw_text']}")
        y -= 12
        if clause["deviation_flag"]:
            c.drawString(60, y, f"Suggested Redline: {clause['suggested_redline']}")
            y -= 12
        y -= 5

    # Risk Register
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Risk Register:")
    y -= 15
    c.setFont("Helvetica", 10)
    for severity, clauses in report["risk_register"]["risk_summary"].items():
        c.drawString(50, y, f"{severity.title()}: {', '.join(clauses) if clauses else 'None'}")
        y -= 12
    y -= 10

    # Recommendations
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Recommendations:")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(50, y, report["recommendations"]["overall_recommendations"])
    y -= 12
    c.drawString(50, y, f"Clauses to Redline: {', '.join(report['recommendations']['clauses_to_redline'])}")

    # Save PDF
    c.save()
    print(f"PDF report generated: {filename}")


# -----------------------------
# Run PDF generation
# -----------------------------
if __name__ == "__main__":
    generate_pdf(report)