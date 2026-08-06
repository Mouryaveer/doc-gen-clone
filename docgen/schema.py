"""
schema.py — Document type schemas for Turn2Law document generation system.

Each entry defines:
  required : fields that MUST be present and non-empty
  optional : fields that MAY be present; if absent, the placeholder is replaced
             with an empty string so ifthenelse guards in templates work

Company-profile fields (CP_*) are injected automatically by api.py /
_generate_direct_to() from the company_profile form data.  They are listed
here as optional so the schema validator accepts them without error.
"""

# ---------------------------------------------------------------------------
# Shared company-profile optional fields present on EVERY document type.
# The actual values arrive via the company_profile_json form field (API) or
# are set to Turn2Law defaults in _build_company_profile_defaults().
# ---------------------------------------------------------------------------
_CP_OPTIONAL = [
    "CP_Company_Name",
    "CP_Signatory_Name",
    "CP_Designation",
    "CP_Company_Address",
    "CP_Company_Email",
    "CP_Company_Phone",
    "CP_Company_Website",
    "CP_Signature_Image",   # filename stem of uploaded signature PNG
    "CP_Title_Suffix",      # appended to "Onboarding Letter" title — blank for custom mode
]

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
        "optional": _CP_OPTIONAL,
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
            "Confidential_Info_Description",
            "Governing_Law",
        ] + _CP_OPTIONAL,
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Offer_Letter": {
        "required": [
            "Name",
            "Company",
            "Position",
            "Start_Date",
            "Salary",
        ],
        "optional": [
            "Manager_Name",
            "Response_Date",
            "HR_Manager",
            "Benefits_Description",
        ] + _CP_OPTIONAL,
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Contract": {
        "required": [
            "Client_Name",
            "Company",
            "Contract_Creation_Date",
            "Service_Description",
            "Payment_Amount",
            "Start_Date",
            "End_Date",
        ],
        "optional": [
            "Payment_Schedule",
            "Termination_Clause",
        ] + _CP_OPTIONAL,
    },

    # ─────────────────────────────────────────────────────────────────────────
    "MOU": {
        "required": [
            "PartyA_Name",
            "PartyB_Name",
            "Date",
            "Purpose",
            "Term",
            "Jurisdiction",
        ],
        "optional": [
            "Confidentiality",
            "Termination_Clause",
            "Governing_Law",
        ] + _CP_OPTIONAL,
    },

    # ─────────────────────────────────────────────────────────────────────────
    "IP_Agreement": {
        "required": [
            "Name",
            "Company",
            "Date",
            "Term",
            "Jurisdiction",
        ],
        "optional": [
            "IP_Description",
            "Governing_Law",
        ] + _CP_OPTIONAL,
    },
}
