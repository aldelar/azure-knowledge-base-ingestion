"""Azure Functions v2 entry point.

Registers both fn-convert and fn-index as HTTP-triggered functions.
For local development, use the shell scripts in scripts/functions/ instead.
"""

import azure.functions as func

app = func.FunctionApp()


# TODO: Register fn-convert and fn-index functions (future epic — Azure deployment)
