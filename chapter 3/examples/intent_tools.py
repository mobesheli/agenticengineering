"""Three intent-shaped ERP tools and the schemas the model actually sees.

    python -m examples.intent_tools

Prints each tool's name, its description, and its model-facing JSON schema, and
confirms that ``idempotency_key`` is not in any of them. The second tool
receives the key through the run context, which the SDK keeps out of the schema.
"""

from __future__ import annotations

import json

from ch3.erp_tools import ERP_TOOLS


def main() -> None:
    leaked = []
    for tool in ERP_TOOLS:
        schema = tool.params_json_schema
        print(tool.name)
        print(f"  description: {tool.description.splitlines()[0]}")
        print(f"  parameters : {', '.join(schema['properties'])}")
        print("  schema     :")
        for line in json.dumps(schema, indent=2).splitlines():
            print(f"    {line}")
        if "idempotency_key" in json.dumps(schema):
            leaked.append(tool.name)
        print()
    assert not leaked, f"idempotency_key leaked into {leaked}"
    print("idempotency_key present in any model-facing schema: no")


if __name__ == "__main__":
    main()
