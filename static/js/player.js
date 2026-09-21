/* dictare.ro audio player: play/pause/replay/seek, waveform peaks, slow mode, listening telemetry.
   Vanilla JS, no dependencies. Re-initialised after every htmx swap. */
(function () {
  "use strict";

  const SLOW_RATE = 0.75;
  let active = null;

  function fmt(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0;
    const s = Math.round(seconds);
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  function csrfToken() {
    try {
      return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"] || "";
    } catch (e) {
      return "";
    }
  }

  function pickBritishVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    const gb = voices.filter((v) => /en[-_]GB/i.test(v.lang));
    const preferred = gb.find((v) => /natural|neural|online|google/i.test(v.name));
    return preferred || gb[0] || null;
  }

  class Player {
    constructor(el) {
      this.el = el;
      this.playBtn = el.querySelector("[data-play]");
      this.wave = el.querySelector("[data-wave]");
      this.bars = Array.from(this.wave.children);
      this.currentEl = el.querySelector("[data-current]");
      this.durationEl = el.querySelector("[data-duration]");
      const scope = el.closest("[data-exercise]") || el.parentElement;
      this.replayBtn = scope.querySelector("[data-replay]");
      this.slowBtn = scope.querySelector("[data-slow]");
      this.statusEl = scope.querySelector("[data-player-status]");
      this.listenUrl = el.dataset.listenUrl;
      this.speechUrl = el.dataset.speechUrl || "";
      this.duration = (parseInt(el.dataset.durationMs, 10) || 0) / 1000;
      this.slow = false;
      this.stats = { plays: 0, replays: 0, ms: 0, slowed: false };
      this.totalPlays = 0;
      this.playStartedAt = null;
      this.useSpeech = Boolean(this.speechUrl) && "speechSynthesis" in window;

      if (!this.useSpeech) {
        this.audio = new Audio();
        this.audio.preload = "metadata";
        this.audio.src = el.dataset.src;
        this.audio.preservesPitch = true;
        this.bindAudio();
        this.loadPeaks();
      }
      this.bindControls();
    }

    setState(state, message) {
      this.el.dataset.state = state;
      if (state === "playing") markStep("listen");
      const playing = state === "playing";
      this.playBtn.setAttribute("aria-label", playing ? "Pauză" : "Redă fraza");
      if (message && this.statusEl) this.statusEl.textContent = message;
    }

    bindAudio() {
      const a = this.audio;
      a.addEventListener("loadedmetadata", () => {
        if (isFinite(a.duration) && a.duration > 0) {
          this.duration = a.duration;
          this.durationEl.textContent = fmt(a.duration);
          this.wave.setAttribute("aria-valuemax", a.duration.toFixed(1));
        }
      });
      a.addEventListener("waiting", () => this.setState("loading"));
      a.addEventListener("playing", () => this.setState("playing", "Se redă"));
      a.addEventListener("pause", () => {
        if (!a.ended) this.setState("paused", "Pauză");
        this.stopClock();
      });
      a.addEventListener("ended", () => {
        this.setState("ended", "Fraza s-a terminat");
        this.stopClock();
        this.paint(1);
        this.flush();
      });
      a.addEventListener("timeupdate", () => {
        this.paint(this.duration ? a.currentTime / this.duration : 0);
      });
      a.addEventListener("error", () => {
        this.setState("error", "Audio indisponibil");
        this.el.insertAdjacentHTML(
          "afterend",
          '<p class="audio-error" role="alert">Nu am putut încărca fișierul audio. Verifică conexiunea și reîncarcă pagina.</p>'
        );
      });
    }

    bindControls() {
      this.playBtn.addEventListener("click", () => this.toggle());
      if (this.replayBtn) this.replayBtn.addEventListener("click", () => this.replay());
      if (this.slowBtn) {
        this.slowBtn.addEventListener("click", () => {
          this.slow = !this.slow;
          this.slowBtn.setAttribute("aria-pressed", String(this.slow));
          if (this.slow) this.stats.slowed = true;
          if (this.audio) this.audio.playbackRate = this.slow ? SLOW_RATE : 1;
        });
      }
      this.wave.addEventListener("click", (e) => {
        const rect = this.wave.getBoundingClientRect();
        this.seek((e.clientX - rect.left) / rect.width);
      });
      this.wave.addEventListener("keydown", (e) => {
        const step = this.duration ? 0.5 / this.duration : 0.1;
        const pos = this.audio && this.duration ? this.audio.currentTime / this.duration : 0;
        if (e.key === "ArrowRight") { this.seek(pos + step); e.preventDefault(); }
        if (e.key === "ArrowLeft") { this.seek(pos - step); e.preventDefault(); }
        if (e.key === "Home") { this.seek(0); e.preventDefault(); }
        if (e.key === "End") { this.seek(0.999); e.preventDefault(); }
        if (e.key === " " || e.key === "Enter") { this.toggle(); e.preventDefault(); }
      });
    }

    paint(fraction) {
      const f = Math.max(0, Math.min(1, fraction));
      const lit = Math.round(f * this.bars.length);
      this.bars.forEach((bar, i) => bar.classList.toggle("is-played", i < lit));
      const t = f * (this.duration || 0);
      this.currentEl.textContent = fmt(t);
      this.wave.setAttribute("aria-valuenow", t.toFixed(1));
      this.wave.setAttribute("aria-valuetext", fmt(t) + " din " + fmt(this.duration));
    }

    seek(fraction) {
      if (!this.audio || !this.duration) return;
      const f = Math.max(0, Math.min(0.999, fraction));
      this.audio.currentTime = f * this.duration;
      this.paint(f);
    }

    countPlay(fromStart) {
      if (!fromStart) return;
      this.totalPlays += 1;
      this.stats.plays += 1;
      if (this.totalPlays > 1) this.stats.replays += 1;
    }

    startClock() {
      this.playStartedAt = performance.now();
    }

    stopClock() {
      if (this.playStartedAt !== null) {
        this.stats.ms += Math.round(performance.now() - this.playStartedAt);
        this.playStartedAt = null;
      }
    }

    toggle() {
      if (this.useSpeech) return this.speak();
      const a = this.audio;
      if (!a.paused && !a.ended) {
        a.pause();
        return;
      }
      if (active && active !== this) active.stop();
      active = this;
      const fromStart = a.ended || a.currentTime < 0.05;
      if (a.ended) a.currentTime = 0;
      a.playbackRate = this.slow ? SLOW_RATE : 1;
      this.countPlay(fromStart);
      this.setState("loading");
      this.startClock();
      a.play().catch(() => {
        this.stopClock();
        this.setState("paused", "Apasă din nou pentru redare");
      });
    }

    replay() {
      if (this.useSpeech) {
        window.speechSynthesis.cancel();
        this.speaking = false;
        return this.speak();
      }
      this.audio.pause();
      this.audio.currentTime = 0;
      this.paint(0);
      this.toggle();
    }

    stop() {
      if (this.audio) this.audio.pause();
      if (this.useSpeech && this.speaking) window.speechSynthesis.cancel();
    }

    /* Development fallback: browser en-GB speech synthesis for placeholder audio. */
    async speak() {
      const synth = window.speechSynthesis;
      if (this.speaking) {
        synth.cancel();
        return;
      }
      if (!this.speech) {
        this.setState("loading");
        try {
          const res = await fetch(this.speechUrl, { credentials: "same-origin" });
          if (!res.ok) throw new Error(res.status);
          this.speech = await res.json();
        } catch (e) {
          this.setState("error", "Audio indisponibil");
          return;
        }
      }
      if (active && active !== this) active.stop();
      active = this;
      const u = new SpeechSynthesisUtterance(this.speech.text);
      u.lang = "en-GB";
      const voice = pickBritishVoice();
      if (voice) u.voice = voice;
      u.rate = (this.speech.rate || 1) * (this.slow ? SLOW_RATE : 1);
      const expected = Math.max(this.duration / u.rate, 1);
      let started = 0;
      let raf = 0;
      const tick = () => {
        this.paint((performance.now() - started) / 1000 / expected);
        raf = requestAnimationFrame(tick);
      };
      u.onstart = () => {
        started = performance.now();
        this.speaking = true;
        this.countPlay(true);
        this.startClock();
        this.setState("playing", "Se redă");
        raf = requestAnimationFrame(tick);
      };
      const done = () => {
        cancelAnimationFrame(raf);
        this.speaking = false;
        this.stopClock();
        this.paint(1);
        this.setState("ended", "Fraza s-a terminat");
        this.flush();
      };
      u.onend = done;
      u.onerror = done;
      synth.cancel();
      synth.speak(u);
    }

    async loadPeaks() {
      const Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (!Ctx || !window.fetch) return;
      const run = async () => {
        try {
          const res = await fetch(this.el.dataset.src, { credentials: "same-origin" });
          if (!res.ok) return;
          const buf = await res.arrayBuffer();
          const ctx = new Ctx(1, 2, 44100);
          const audio = await ctx.decodeAudioData(buf);
          const data = audio.getChannelData(0);
          const n = this.bars.length;
          const size = Math.floor(data.length / n) || 1;
          const peaks = [];
          for (let i = 0; i < n; i++) {
            let max = 0;
            for (let j = i * size; j < Math.min((i + 1) * size, data.length); j += 16) {
              const v = Math.abs(data[j]);
              if (v > max) max = v;
            }
            peaks.push(max);
          }
          const top = Math.max(...peaks) || 1;
          peaks.forEach((p, i) => {
            this.bars[i].style.setProperty("--h", Math.max(10, Math.round((p / top) * 100)) + "%");
          });
        } catch (e) {
          /* keep the decorative waveform */
        }
      };
      if ("requestIdleCallback" in window) window.requestIdleCallback(run, { timeout: 1500 });
      else setTimeout(run, 300);
    }

    flush() {
      const s = this.stats;
      if (!this.listenUrl || (!s.plays && !s.ms && !s.slowed)) return;
      const body = new URLSearchParams({
        plays: s.plays, replays: s.replays, ms: s.ms, slowed: s.slowed ? "1" : "0",
      });
      this.stats = { plays: 0, replays: 0, ms: 0, slowed: false };
      fetch(this.listenUrl, {
        method: "POST",
        body,
        keepalive: true,
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken() },
      }).catch(() => {});
    }

    destroy() {
      this.stopClock();
      this.stop();
      this.flush();
    }
  }

  /* Step list (listen state): nothing is lit until the learner starts.
     Playing lights "listen"; typing marks it done and lights "write". */
  function markStep(step) {
    const listen = document.querySelector('#step-list [data-step="listen"]');
    const write = document.querySelector('#step-list [data-step="write"]');
    if (!listen || !write || listen.classList.contains("is-done") && step === "listen") return;
    if (step === "listen" && !write.classList.contains("is-current")) {
      listen.classList.add("is-current");
    } else if (step === "write") {
      listen.classList.remove("is-current");
      listen.classList.add("is-done");
      write.classList.add("is-current");
    }
  }

  document.addEventListener("input", (e) => {
    if (e.target.matches && e.target.matches("[data-answer]") && e.target.value.trim()) markStep("write");
  });

  /* Result hero: count the score up and celebrate a top score. Only right after "Verifică". */
  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function celebrate(hero) {
    if (!hero.classList.contains("is-fresh") || hero._celebrated || reducedMotion()) return;
    hero._celebrated = true;
    const num = hero.querySelector("[data-count-to]");
    if (num) {
      const target = parseInt(num.dataset.countTo, 10) || 0;
      const start = performance.now() + 150;
      const tick = (now) => {
        const t = Math.min(1, Math.max(0, (now - start) / 1100));
        num.textContent = Math.round(target * (1 - Math.pow(1 - t, 3)));
        if (t < 1) requestAnimationFrame(tick);
      };
      num.textContent = "0";
      requestAnimationFrame(tick);
    }
    if (hero.dataset.tier === "top" || hero.dataset.tier === "great") {
      const colors = ["#16a34a", "#0f9f7a", "#1f6fe5", "#7a5af8", "#ff7a1a", "#f5b700"];
      const box = document.createElement("div");
      box.className = "confetti";
      box.setAttribute("aria-hidden", "true");
      const count = hero.dataset.tier === "top" ? 60 : 28;
      for (let i = 0; i < count; i++) {
        const p = document.createElement("i");
        p.style.cssText =
          `--x:${Math.random() * 100}%;--dx:${(Math.random() - 0.5) * 120}px;` +
          `--r:${(Math.random() - 0.5) * 900}deg;--d:${0.9 + Math.random() * 0.5}s;` +
          `--t:${1.3 + Math.random() * 0.9}s;--c:${colors[i % colors.length]}`;
        box.appendChild(p);
      }
      hero.appendChild(box);
      setTimeout(() => box.remove(), 3500);
    }
  }

  function init(root) {
    document.querySelectorAll("[data-result-hero]").forEach(celebrate);
    (root || document).querySelectorAll("[data-player]").forEach((el) => {
      if (el._player) return;
      el._player = new Player(el);
    });
    const answer = document.querySelector("[data-answer]");
    if (answer && answer.value.trim()) markStep("write");
  }

  document.addEventListener("DOMContentLoaded", () => init(document));
  document.addEventListener("htmx:beforeSwap", (e) => {
    const target = e.detail.target;
    if (target) target.querySelectorAll("[data-player]").forEach((el) => el._player && el._player.destroy());
  });
  document.addEventListener("htmx:afterSettle", (e) => init(e.detail.elt && e.detail.elt.parentElement));
  document.addEventListener("htmx:load", (e) => init(e.detail.elt));
  window.addEventListener("pagehide", () => {
    document.querySelectorAll("[data-player]").forEach((el) => el._player && el._player.destroy());
  });
  if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = () => {};

  /* Keyboard shortcuts inside the exercise: Ctrl+Enter = check, Ctrl+Space = play/pause */
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    const exercise = document.querySelector("[data-exercise]");
    if (!exercise) return;
    if (e.key === "Enter") {
      const form = exercise.querySelector("form.answer");
      if (form) {
        e.preventDefault();
        form.requestSubmit();
      }
    } else if (e.code === "Space") {
      const player = exercise.querySelector("[data-player]");
      if (player && player._player) {
        e.preventDefault();
        player._player.toggle();
      }
    }
  });
})();
