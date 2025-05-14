// Toggle mobile menu visibility
const menuToggle = document.getElementById("menu-toggle");
const mobileNav = document.getElementById("mobile-nav");

if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    mobileNav.classList.toggle("hidden");
  });
}
console.log("menu toggle clicked");
