gsap.registerPlugin(ScrollTrigger, ScrollSmoother, MorphSVGPlugin, SplitText, DrawSVGPlugin);

document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("overflow-hidden");

  const title = new SplitText(".loader-title", { type: "chars" });
  const chars = title.chars;

  gsap.fromTo(chars, 
    { y: 60, opacity: 0, scale: 0.6 }, 
    {
      y: 0,
      opacity: 1,
      duration: 0.6,
      stagger: 0.04,
      ease: "back.out(1.7)",
      scale: 1,
      repeat: -1,
      repeatDelay: 0.2,
      yoyo: true
    }
  );

  startProgressCounter();
});

let isWindowLoaded = false;
let progress = 0;

window.addEventListener("load", () => {
  isWindowLoaded = true;
});

function startProgressCounter() {
  const percentText = document.querySelector(".loader-percent");
  const fill = document.querySelector(".progress-fill");
  const loaderBg = document.querySelector(".loader-bg");

  const progressInterval = setInterval(() => {
    if (!isWindowLoaded) {
      if (progress < 89) progress++;
      else if (progress < 97) progress += 0.2;
      progress = Math.min(progress, 97);
    } else {
      progress += 2;
    }

    progress = Math.min(progress, 100);
    fill.style.width = progress + "%";
    percentText.textContent = Math.floor(progress) + "%";
    if (loaderBg) loaderBg.style.opacity = progress / 100;

    if (isWindowLoaded && progress >= 100) {
      clearInterval(progressInterval);
      finishLoader();
    }
  }, 25);
}

function finishLoader() {
  const tl = gsap.timeline({ defaults: { ease: "power2.inOut" } });
  gsap.killTweensOf(".loader-title .char");

  tl.to([
      ".loader-title",
      ".loader-percent",
      ".loader-logo",
      ".loader-loading",
      ".progress-fill",
      ".progress-bar"
    ], {
      opacity: 0,
      y: -20,
      duration: 0.35,
      stagger: 0.05
    })
    .to([".morph-me", "#clip-wave"], {
      duration: 0.65,
      morphSVG: "M0,0H1920V560.5s-403.5-149-960-149S0,560.5,0,560.5Z",
      ease: "power3.inOut"
    }, "-=0.35")
    .to(".preloader-area", {
      duration: 0.65,
      y: "-100%",
      opacity: 0,
      ease: "power3.inOut"
    }, "-=0.35")
    .call(() => {
      setTimeout(() => document.body.classList.remove("overflow-hidden"), 1000);
      initAnimations();
    }, [], "-=.8");
}

// ✅ Scroll-to button logic (safe ScrollSmoother check)
const innerBtn = document.querySelector('.scroll-to-inner');
const homeBtn = document.querySelector('.scroll-to-home');

if (innerBtn) {
  innerBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const target = document.querySelector('#inner');
    if (typeof ScrollSmoother !== "undefined" && ScrollSmoother.get()) {
      const smoother = ScrollSmoother.get();
      smoother.scrollTo(target, true, "top top");
    } else {
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
}

if (homeBtn) {
  homeBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const target = document.querySelector('#home');
    if (typeof ScrollSmoother !== "undefined" && ScrollSmoother.get()) {
      const smoother = ScrollSmoother.get();
      smoother.scrollTo(target, true, "top top");
    } else {
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
}
