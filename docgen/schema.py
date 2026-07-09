DOCUMENT_SCHEMAS = {
    "NDA": {
        "required": ["Name", "Company", "Date", "Term", "Jurisdiction"],
        "optional": ["Confidential_Info_Description", "Governing_Law"]
    },
    "Offer_Letter": {
        "required": ["Name", "Company", "Position", "Start_Date", "Salary"],
        "optional": ["Manager_Name", "Response_Date", "HR_Manager", "Benefits_Description"]
    },
    "Contract": {
        "required": [
            "Client_Name", "Company", "Contract_Creation_Date",
            "Service_Description", "Payment_Amount", "Start_Date", "End_Date"
        ],
        "optional": ["Payment_Schedule", "Termination_Clause"]
    },
    "MOU": {
        "required": ["PartyA_Name", "PartyB_Name", "Date", "Purpose", "Term", "Jurisdiction"],
        "optional": ["Confidentiality", "Termination_Clause", "Governing_Law"]
    },
    "IP_Agreement": {
        "required": ["Name", "Company", "Date", "Term", "Jurisdiction"],
        "optional": ["IP_Description", "Governing_Law"]
    },
    "Onboarding_Letter": {
        "required": [
        "Employee_Name",
        "Emp_ID",
        "Role",
        "Joining_Date",
        "Document_Date"
    ],
    "optional": []
}
}