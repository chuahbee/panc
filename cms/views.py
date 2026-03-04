import json
import os
from urllib import error, request

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def ai_assistant_chat(request_):
    expected_token = os.environ.get("AI_ASSISTANT_API_TOKEN", "").strip()
    if expected_token:
        provided_token = request_.headers.get("X-AI-Token", "").strip()
        if provided_token != expected_token:
            return JsonResponse(
                {
                    "error": "Unauthorized",
                    "reply": "当前 AI 服务未授权访问。",
                },
                status=401,
            )

    try:
        payload = json.loads(request_.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    messages = payload.get("messages") or []
    raw_page_context = payload.get("page_context")
    if raw_page_context is None:
        page_context = ""
    elif isinstance(raw_page_context, str):
        page_context = raw_page_context.strip()
    else:
        return JsonResponse({"error": "page_context must be a string."}, status=400)
    if not isinstance(messages, list):
        return JsonResponse({"error": "messages must be a list."}, status=400)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return JsonResponse(
            {
                "error": "OPENAI_API_KEY is not configured.",
                "reply": "当前未配置 AI 服务密钥（OPENAI_API_KEY），请先在服务器环境变量中配置后再使用 AI 解释。",
            },
            status=503,
        )

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    endpoint = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")

    system_prompt = (
        "你是网站内嵌助手。请优先基于给定的页面上下文回答，"
        "回答使用简体中文，简洁清楚，避免编造不存在的信息。"
        "如果上下文没有答案，请明确说没有找到并给出下一步建议。"
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    if page_context:
        llm_messages.append(
            {
                "role": "system",
                "content": f"当前页面文本上下文（可能被截断）:\n{page_context[:6000]}",
            }
        )

    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        raw_content = item.get("content")
        if raw_content is None:
            content = ""
        elif isinstance(raw_content, str):
            content = raw_content.strip()
        else:
            continue
        if role in {"user", "assistant"} and content:
            llm_messages.append({"role": role, "content": content[:2000]})

    body = {
        "model": model,
        "messages": llm_messages,
        "temperature": 0.3,
    }

    req = request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return JsonResponse(
            {
                "error": "LLM upstream HTTP error",
                "detail": detail[:1000],
                "reply": "AI 服务暂时不可用，请稍后重试。",
            },
            status=502,
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {
                "error": "LLM request failed",
                "detail": str(exc),
                "reply": "AI 服务连接失败，请稍后再试。",
            },
            status=502,
        )

    reply = ""
    choices = data.get("choices") or []
    if choices:
        reply = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()

    if not reply:
        reply = "我暂时没有生成有效回复，请换个问题再试试。"

    return JsonResponse({"reply": reply})