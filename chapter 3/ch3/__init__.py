"""Chapter 3 companion package: tools, the side-effect boundary, and MCP.

The modules map onto the chapter's sections:

- ``deps``: the run context object the orchestration layer owns.
- ``erp_tools``: three intent-shaped ERP tools in place of one generic one.
- ``errors``: the error shape the agent loop, the user, and the audit log share.
- ``payments``: the sqlite-backed refund store with an atomic, idempotent write.
- ``refund_tools``: the refund tools, including the approval-gated execute.
- ``previews``: preview and execute with a content hash.
- ``approvals``: the approval loop and a scripted reviewer for the drills.
- ``journal``: the tool-call journal used by the audit-prep agent.
"""
