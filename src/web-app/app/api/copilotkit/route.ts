import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";

import { createRuntimeAgent } from "../../../lib/agent";
import { repairCopilotRuntimeRequest } from "../../../lib/copilotRuntime";

export const runtime = "nodejs";

async function buildRuntimeRequest(request: Request): Promise<Request> {
  if (request.method !== "POST") {
    return request;
  }

  const bodyText = await request.text();
  if (!bodyText) {
    return new Request(request, { body: bodyText });
  }

  try {
    const parsedBody = JSON.parse(bodyText) as unknown;
    const repairResult = await repairCopilotRuntimeRequest(parsedBody, request.headers);
    if (repairResult.repaired) {
      console.info(
        "Repaired CopilotKit request history for thread %s (%d -> %d messages, restored %d missing tool results)",
        repairResult.threadId,
        repairResult.requestMessageCount,
        repairResult.repairedMessageCount,
        repairResult.missingToolCallIds?.length ?? 0,
      );
    }

    return new Request(request, {
      body: JSON.stringify(repairResult.body),
    });
  } catch {
    return new Request(request, { body: bodyText });
  }
}

async function handleCopilotRequest(request: Request): Promise<Response> {
  const runtimeRequest = await buildRuntimeRequest(request);
  const runtimeInstance = new CopilotRuntime({
    agents: {
      default: await createRuntimeAgent(runtimeRequest.headers),
    },
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    endpoint: "/api/copilotkit",
    runtime: runtimeInstance,
    serviceAdapter: new ExperimentalEmptyAdapter(),
  });

  return handleRequest(runtimeRequest);
}

export async function GET(request: Request): Promise<Response> {
  return handleCopilotRequest(request);
}

export async function POST(request: Request): Promise<Response> {
  return handleCopilotRequest(request);
}