(function () {
  const STORAGE_KEY = "ai_assistant_conversation_v1";
  const MAX_STORED_MESSAGES = 50;
  const PAGE_CONTEXT_LIMIT = 12000;
  const toggle = document.getElementById("ai-assistant-toggle");
  const panel = document.getElementById("ai-assistant-panel");
  const chat = document.getElementById("ai-assistant-chat");
  const input = document.getElementById("ai-assistant-input");
  const send = document.getElementById("ai-assistant-send");

  if (!toggle || !panel || !chat || !input || !send) return;

  const conversation = [];
  let pending = false;

  function getConversationStore() {
    try {
      return window.sessionStorage;
    } catch (error) {
      return null;
    }
  }

  function saveConversation() {
    const store = getConversationStore();
    if (!store) return;
    try {
      store.setItem(STORAGE_KEY, JSON.stringify(conversation.slice(-MAX_STORED_MESSAGES)));
    } catch (error) {}
  }

  function loadConversation() {
    const store = getConversationStore();
    if (!store) return [];
    try {
      const raw = store.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(
          (item) =>
            item &&
            (item.role === "user" || item.role === "assistant") &&
            typeof item.content === "string"
        )
        .slice(-MAX_STORED_MESSAGES);
    } catch (error) {
      return [];
    }
  }

  function renderSavedConversation(items) {
    items.forEach((msg) => {
      conversation.push(msg);
      const item = document.createElement("div");
      item.className = `ai-msg ai-msg-${msg.role}`;
      if (msg.role === "assistant") {
        renderAssistantContent(item, msg.content);
      } else {
        item.textContent = msg.content;
      }
      chat.appendChild(item);
    });
    chat.scrollTop = chat.scrollHeight;
  }

  function normalizeAssistantText(text) {
    return (text || "")
      .replace(/\*\*/g, "")
      .replace(/`/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function renderAssistantContent(container, text) {
    const safeText = normalizeAssistantText(text);
    const lines = safeText.split("\n");
    const urlRegex = /(https?:\/\/[^\s]+|\/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)/g;

    lines.forEach((line, lineIndex) => {
      const parts = line.split(urlRegex);
      parts.forEach((part) => {
        if (!part) return;
        if (/^https?:\/\/[^\s]+$/.test(part) || /^\/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$/.test(part)) {
          const link = document.createElement("a");
          link.href = part;
          // link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = part;
          container.appendChild(link);
        } else {
          container.appendChild(document.createTextNode(part));
        }
      });
      if (lineIndex < lines.length - 1) {
        container.appendChild(document.createElement("br"));
      }
    });
  }

  function appendMessage(role, text) {
    const normalizedText = role === "assistant" ? normalizeAssistantText(text) : text;
    conversation.push({ role, content: normalizedText });

    const item = document.createElement("div");
    item.className = `ai-msg ai-msg-${role}`;
    if (role === "assistant") {
      renderAssistantContent(item, normalizedText);
    } else {
      item.textContent = normalizedText;
    }
    chat.appendChild(item);
    chat.scrollTop = chat.scrollHeight;
    saveConversation();
  }

  function updateSendState() {
    send.disabled = pending;
    if (pending) {
      send.innerHTML = '<span class="iconify ai-send-icon ai-send-icon-spin" data-icon="mdi:loading" data-inline="false"></span>';
      send.title = "Thinking... / 思考中... / Sedang berfikir...";
      send.setAttribute("aria-label", "Thinking... / 思考中... / Sedang berfikir...");
      return;
    }

    send.innerHTML = '<span class="iconify ai-send-icon" data-icon="mdi:send" data-inline="false"></span>';
    send.title = "发送 / Send / Hantar";
    send.setAttribute("aria-label", "发送 / Send / Hantar");
  }

  function getStructuredCourseContext() {
    const cards = Array.from(document.querySelectorAll(".course-card, .course-detail"));
    if (!cards.length) return "";

    const rows = cards
      .map((card) => {
        const title = (card.querySelector("h3")?.innerText || "").trim();
        if (!title) return "";
        const link = (card.querySelector("a")?.getAttribute("href") || "").trim();

        const fields = {};
        card.querySelectorAll("p").forEach((p) => {
          const strong = p.querySelector("strong");
          const key = (strong?.innerText || "").replace(":", "").trim();
          const value = (p.innerText || "").replace((strong?.innerText || ""), "").trim();
          if (key && value) fields[key] = value;
        });

        const priceRaw = (card.querySelector("h4")?.innerText || "").trim();
        const parts = [`Course: ${title}`];
        if (priceRaw) parts.push(`Price: ${priceRaw}`);
        if (link) {
          try {
            parts.push(`URL: ${new URL(link, window.location.href).href}`);
          } catch (error) {
            parts.push(`URL: ${link}`);
          }
        }
        [
          "Teacher",
          "Location",
          "Start Date",
          "Age",
          "Weekday",
          "Time",
          "Type",
        ].forEach((key) => {
          if (fields[key]) parts.push(`${key}: ${fields[key]}`);
        });
        return parts.join(" | ");
      })
      .filter(Boolean);

    if (!rows.length) return "";
    return `Structured course data:\n${rows.join("\n")}`;
  }

  function getStructuredProductContext() {
    const cards = Array.from(document.querySelectorAll(".product"));
    if (!cards.length) return "";

    const rows = cards
      .map((card) => {
        const title = (card.querySelector("h3")?.innerText || "").trim();
        if (!title) return "";
        const link = (card.querySelector("a")?.getAttribute("href") || "").trim();
        const priceRaw = (card.querySelector("h4")?.innerText || "").trim();
        const parts = [`Product: ${title}`];
        if (priceRaw) parts.push(`Price: ${priceRaw}`);
        if (link) {
          try {
            parts.push(`URL: ${new URL(link, window.location.href).href}`);
          } catch (error) {
            parts.push(`URL: ${link}`);
          }
        }
        return parts.join(" | ");
      })
      .filter(Boolean);

    if (!rows.length) return "";
    return `Structured product data:\n${rows.join("\n")}`;
  }

  function getPageContext() {
    const root = document.querySelector("main") || document.body;
    const rawText = root.innerText || "";
    const normalizedText = rawText
      .replace(/\r/g, "")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    const blocks = [getStructuredCourseContext(), getStructuredProductContext()].filter(Boolean);
    const structuredContext = blocks.join("\n\n");
    if (!structuredContext) {
      return normalizedText.slice(0, PAGE_CONTEXT_LIMIT);
    }

    const prefix = `${structuredContext}\n\nPage text:\n`;
    const remaining = Math.max(0, PAGE_CONTEXT_LIMIT - prefix.length);
    return `${prefix}${normalizedText.slice(0, remaining)}`;
  }

  function getCookie(name) {
    const cookieParts = document.cookie ? document.cookie.split(";") : [];
    for (const part of cookieParts) {
      const item = part.trim();
      if (item.startsWith(`${name}=`)) {
        return decodeURIComponent(item.slice(name.length + 1));
      }
    }
    return "";
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const metaToken = ((meta && meta.content) || "").trim();
    return metaToken && metaToken !== "NOTPROVIDED" ? metaToken : getCookie("csrftoken");
  }

  async function askLLM() {
    pending = true;
    updateSendState();

    const messages = conversation.slice(-12);

    try {
      const response = await fetch("/api/ai-assistant/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          messages,
          page_context: getPageContext(),
          page_url: window.location.href,
          page_title: document.title || "",
        }),
      });

      const isJson = (response.headers.get("content-type") || "").includes("application/json");
      const data = isJson ? await response.json() : {};

      if (!response.ok) {
        appendMessage(
          "assistant",
          data.reply ||
            "AI service is temporarily unavailable. / AI 服务暂不可用。 / Perkhidmatan AI tidak tersedia buat sementara."
        );
        return;
      }

      const reply =
        data.reply ||
        "No valid reply generated. Please try again. / 暂未生成有效回复，请重试。 / Tiada jawapan sah dijana. Sila cuba lagi.";
      appendMessage("assistant", reply);
    } catch (error) {
      appendMessage(
        "assistant",
        "AI connection failed. Please try again later. / AI 连接失败，请稍后再试。 / Sambungan AI gagal. Sila cuba lagi."
      );
    } finally {
      pending = false;
      updateSendState();
    }
  }

  async function ask(text) {
    const prompt = (text || "").trim();
    if (!prompt || pending) return;

    appendMessage("user", prompt);
    input.value = "";
    await askLLM();
  }

  const savedConversation = loadConversation();
  if (savedConversation.length) {
    renderSavedConversation(savedConversation);
  }

  toggle.addEventListener("click", function () {
    const isOpen = !panel.hasAttribute("hidden");
    if (isOpen) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    } else {
      panel.removeAttribute("hidden");
      toggle.setAttribute("aria-expanded", "true");
      if (!conversation.length) {
        appendMessage(
          "assistant",
          "支持语言: 中文, English, Malay"
        );
      }
    }
  });

  send.addEventListener("click", function () {
    ask(input.value);
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      ask(input.value);
    }
  });

  updateSendState();
})();
