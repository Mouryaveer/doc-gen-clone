"""
schema.py — Document type schemas for Turn2Law document generation system.

Each entry defines:
  required : fields that MUST be present and non-empty
  optional : fields that MAY be present; if absent, the placeholder is replaced
             with an empty string so ifthenelse guards in templates work
"""

DOCUMENT_SCHEMAS = {

    # ─────────────────────────────────────────────────────────────────────────
    "Onboarding_Letter": {
        "required": [
            "Employee_Name",
            "Emp_ID",
            "Role",
            "Joining_Date",
            "Document_Date",
        ],
        "optional": [],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "NDA": {
        "required": [
            "Name",           # Receiving party's name
            "Company",        # Receiving party's company / address
            "Date",           # Effective date
            "Term",           # Duration e.g. "two (2) years"
            "Jurisdiction",   # Seat of arbitration / governing court
        ],
        "optional": [
            "Confidential_Info_Description",  # Specific CI description
            "Governing_Law",                  # Additional governing law note
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Offer_Letter": {
        "required": [
            "Name",       # Candidate's full name
            "Company",    # Candidate's current address / company
            "Position",   # Job title being offered
            "Start_Date", # Date of joining
            "Salary",     # Fixed CTC
        ],
        "optional": [
            "Manager_Name",          # Reporting manager
            "Response_Date",         # Offer acceptance deadline
            "HR_Manager",            # HR contact name
            "Benefits_Description",  # Additional benefits narrative
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Contract": {
        "required": [
            "Client_Name",            # Name of the client
            "Company",                # Client's company / address
            "Contract_Creation_Date", # Effective date
            "Service_Description",    # Scope of services
            "Payment_Amount",         # Total contract value
            "Start_Date",             # Service period start
            "End_Date",               # Service period end
        ],
        "optional": [
            "Payment_Schedule",   # Detailed payment milestones
            "Termination_Clause", # Additional termination terms
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "MOU": {
        "required": [
            "PartyA_Name",  # First party
            "PartyB_Name",  # Second party
            "Date",         # Effective date
            "Purpose",      # Collaboration purpose
            "Term",         # Duration
            "Jurisdiction", # Governing jurisdiction
        ],
        "optional": [
            "Confidentiality",    # Custom confidentiality clause text
            "Termination_Clause", # Additional termination terms
            "Governing_Law",      # Additional governing law note
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "IP_Agreement": {
        "required": [
            "Name",         # Assignor's name
            "Company",      # Assignor's company / address
            "Date",         # Effective date
            "Term",         # Duration of assignment obligations
            "Jurisdiction", # Governing jurisdiction
        ],
        "optional": [
            "IP_Description", # Specific description of assigned IP
            "Governing_Law",  # Additional governing law note
        ],
    },
}
