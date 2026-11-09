/* home.js — the boarding screen: sunburst, steam whistle on the funnels, bouncy letters. */
(() => {
  "use strict";
  const T = window.Titanic;
  const boarding = document.querySelector(".boarding");
  const hero = document.querySelector(".hero-ship");

  requestAnimationFrame(() => boarding?.classList.add("ready"));

  // The whistle blows once the last letter of the title lands (if sound is on).
  setTimeout(() => T.sound.horn(2.2), T.reduced ? 0 : 2600);

  // Click the ship (a funnel especially) for the steam whistle and a burst of smoke.
  hero?.addEventListener("click", (e) => {
    const funnel = e.target.closest(".funnel, .funnel-top");
    T.sound.horn(funnel ? 1.8 : 0.9);
    hero.classList.add("blast");
    clearTimeout(hero._t);
    hero._t = setTimeout(() => hero.classList.remove("blast"), 1600);
    if (funnel) T.toast("WHOOOOOOM STOP THE WHISTLE CAN BE HEARD ELEVEN MILES AWAY STOP", 2600);
  });

  // Letters leap like flying fish when touched.
  document.querySelectorAll(".letter").forEach((el) => {
    el.addEventListener("pointerenter", () => {
      if (T.reduced) return;
      el.animate(
        [{ transform: "translateY(0) rotate(0)" }, { transform: "translateY(-.22em) rotate(-6deg)" }, { transform: "translateY(0) rotate(0)" }],
        { duration: 650, easing: "cubic-bezier(.34,1.56,.64,1)" }
      );
    });
  });
})();
