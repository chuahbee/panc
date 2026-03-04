(function () {
  const toggle = document.getElementById("ai-assistant-toggle");
  const panel = document.getElementById("ai-assistant-panel");
  const chat = document.getElementById("ai-assistant-chat");
  const input = document.getElementById("ai-assistant-input");
  const send = document.getElementById("ai-assistant-send");

 if (!toggle || !panel || !chat || !input || !send) return;

  const conversation = [];
  let pending = false;

  function appendMessage(role, text) {
    conversation.push({ role, content: text });

    const item = document.createElement("div");
    item.className = `ai-msg ai-msg-${role}`;
    item.textContent = text;
    chat.appendChild(item);
    chat.scrollTop = chat.scrollHeight;
  }

  function updateSendState() {
    send.disabled = pending;
    send.textContent = pending ? "思考中..." : "发送";
  }

  function getPageContext() {
    const root = document.querySelector("main") || document.body;
    const text = (root.innerText || "").replace(/\s+/g, " ").trim();
    return text.slice(0, 7000);
  }

  async function askLLM(userText) {
    pending = true;
    updateSendState();

    const messages = conversation.slice(-12);

    try {
      const response = await fetch("/api/ai-assistant/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages,
          page_context: getPageContext(),
          page_url: window.location.href,
          page_title: document.title || "",
        }),
      });

      const data = await response.json();
      const reply = data.reply || "我暂时没有生成有效回复，请稍后再试。";
      appendMessage("assistant", reply);
    } catch (error) {
      appendMessage("assistant", "AI 服务连接失败，请稍后再试。");
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
    await askLLM(prompt);
  }

  const topicPrompts = {
    courses: "请解释这个页面里和课程相关的重点。",
    products: "请解释这个页面里和产品相关的重点。",
    about: "请解释这个页面里关于我们的重点。",
    explain: "请根据当前页面内容做一个简明解释。",
  };

  toggle.addEventListener("click", function () {
    const isOpen = !panel.hasAttribute("hidden");
    if (isOpen) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    } else {
      panel.removeAttribute("hidden");
      toggle.setAttribute("aria-expanded", "true");
      if (!conversation.length) {
        appendMessage("assistant", "你好，我是 AI 助手。你可以直接让我解释当前页面。比如：这页主要讲什么？");
      }
    }
  });

  panel.querySelectorAll("[data-topic]").forEach(function (button) {
    button.addEventListener("click", function () {
      const topic = button.getAttribute("data-topic");
      ask(topicPrompts[topic] || "请解释当前页面");
    });
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
})();