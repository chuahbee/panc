window.isRotating = false;

window.targetRotationY = 0;

window.triggerMascotSpin = function (direction = "right") {
  if (!window.modelGroup || window.isRotating) return;

  window.isRotating = true;

  // 每次点击右转：加 360°，左转：减 360°
  const delta = direction === "left" ? -Math.PI * 2 : Math.PI * 2;
  window.targetRotationY += delta;

  gsap.to(window.modelGroup.rotation, {
    y: window.targetRotationY,
    duration: 1,
    ease: "power2.inOut",
    onComplete: () => {
      window.isRotating = false;
    },
  });
};


let currentSectionIndex = -1;

/* static/js/break.js */
gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);

/* 1. 把所有 panel 收集起来 */
const sections = gsap.utils.toArray(".panel");
const n = sections.length;
const vw = () => window.innerWidth; // 当前屏宽（实时取）

/* 2. 建立唯一的横向滚动 ScrollTrigger */
const tween = gsap.to(sections, {
  xPercent: -100 * (n - 1),
  ease: "none",
  scrollTrigger: {
    trigger: "#wrapper",
    pin: true,
    scrub: 1,
    end: () => "+=" + (n - 1) * vw(), // 滚 (n‑1) 屏高
    invalidateOnRefresh: true,
    onUpdate: (self) => {
      const index = Math.round(self.progress * (n - 1));
      if (index !== currentSectionIndex) {
        currentSectionIndex = index;
    
        if (window.triggerMascotSpin) {
          window.triggerMascotSpin(); // 默认右转
        }
    
        setActive(index);
      }
    }
  },
});
const ST = tween.scrollTrigger;

/* 3. 通用跳转函数（首尾循环） */
function scrollToIdx(idx) {
  idx = (idx + n) % n;
  gsap.to(window, {
    scrollTo: ST.start + idx * vw(),
    duration: 1,
    ease: "power2.inOut",
  });
}

/* 4. 左右箭头 */
prevBtn.onclick = () => {
  const newIndex = Math.round(ST.progress * (n - 1)) - 1;
  scrollToIdx(newIndex, "left");
};

nextBtn.onclick = () => {
  const newIndex = Math.round(ST.progress * (n - 1)) + 1;
  scrollToIdx(newIndex, "right");
};

/* 5. 时间轴点击 */
document.querySelectorAll("#timeline li").forEach((li) => {
  li.onclick = () => scrollToIdx(+li.dataset.index);
});

/* 6. 高亮 */
function setActive(i) {
  document
    .querySelectorAll("#timeline li")
    .forEach((li, idx) => li.classList.toggle("active", idx === i));
}
