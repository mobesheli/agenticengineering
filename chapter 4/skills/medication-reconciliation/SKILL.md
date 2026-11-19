---
name: medication-reconciliation
description: Reconcile a patient's medications against pharmacy fills before a visit.
---
Steps:
1. Fetch active medications from the patient record via the FHIR tool.
2. Fetch the last 180 days of pharmacy fills.
3. Align by drug and dose. Flag duplicates, gaps, and discontinued-but-filled.
4. Recall prior reconciliations for this patient before flagging anything twice.
5. Check the surviving medications against the interaction knowledge base.
6. Draft a reconciliation note for the clinician to review. Do not finalize it.
