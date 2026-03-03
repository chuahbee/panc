(function () {
  const toggle = document.getElementById("ai-assistant-toggle");
  const panel = document.getElementById("ai-assistant-panel");
  const message = document.getElementById("ai-assistant-message");

  if (!toggle || !panel || !message) return;

  const replies = {
    courses:
      "我们提供艺术课程信息展示，包含老师、地点、日期与课程类型。你可以在课程页快速浏览并点击“我要报名”。",
    products:
      "Products 页面用于展示你的产品和服务入口（比如 Credit Card/P2P 相关板块），帮助访客快速进入对应内容。",
    about:
      "About Us 区块会介绍品牌背景与内容导航。首页四个面板是你的主入口：Home / Art Class / Products / About Us。",
  };

  toggle.addEventListener("click", function () {
    const isOpen = !panel.hasAttribute("hidden");
    if (isOpen) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    } else {
      panel.removeAttribute("hidden");
      toggle.setAttribute("aria-expanded", "true");
    }
  });

  panel.querySelectorAll("[data-topic]").forEach(function (button) {
    button.addEventListener("click", function () {
      const topic = button.getAttribute("data-topic");
      message.textContent = replies[topic] || "我可以帮你介绍网站结构与主要页面内容。";
    });
  });
})();