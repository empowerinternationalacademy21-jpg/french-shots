/* ═══════════════════════════════════════════════
   FrenchShots — main.js
   Feed · Vocab drawer · Upload modal · Likes
   ═══════════════════════════════════════════════ */

"use strict";

/* ─────────────────────────────────────────────
   CSRF TOKEN
   ───────────────────────────────────────────── */

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || "";
}

/* ─────────────────────────────────────────────
   FLASH MESSAGES — auto dismiss
   ───────────────────────────────────────────── */

function initFlash() {
  document.querySelectorAll(".flash-close").forEach(btn => {
    btn.addEventListener("click", () => dismissFlash(btn.closest(".flash")));
  });
  setTimeout(() => {
    document.querySelectorAll(".flash").forEach(el => dismissFlash(el));
  }, 5000);
}

function dismissFlash(el) {
  if (!el) return;
  el.style.transition = "opacity 0.4s ease, transform 0.4s ease";
  el.style.opacity = "0";
  el.style.transform = "translateX(16px)";
  setTimeout(() => el.remove(), 400);
}

/* ─────────────────────────────────────────────
   VIDEO FEED — play/pause on tap
   ───────────────────────────────────────────── */

function initFeed() {
  const feed = document.querySelector(".feed");
  if (!feed) return;

  // Intersection observer — autoplay visible shot
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const video = entry.target.querySelector(".shot-video");
      if (!video) return;
      if (entry.isIntersecting) {
        video.play().catch(() => {});
      } else {
        video.pause();
        video.currentTime = 0;
      }
    });
  }, { threshold: 0.6 });

  document.querySelectorAll(".shot").forEach(shot => {
    observer.observe(shot);

    const video     = shot.querySelector(".shot-video");
    const indicator = shot.querySelector(".pause-indicator");

    if (!video) return;

    // Tap to pause/play
    video.addEventListener("click", () => {
      if (video.paused) {
        video.play();
        showIndicator(indicator, false);
      } else {
        video.pause();
        showIndicator(indicator, true);
      }
    });
  });
}

function showIndicator(el, isPaused) {
  if (!el) return;
  el.innerHTML = isPaused
    ? `<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>`
    : `<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>`;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 700);
}

/* ─────────────────────────────────────────────
   VOCAB DRAWER
   ───────────────────────────────────────────── */

const vocabDrawer  = document.getElementById("vocab-drawer");
const vocabOverlay = document.getElementById("vocab-overlay");
const vocabList    = document.getElementById("vocab-list");
const vocabTitle   = document.getElementById("vocab-video-title");

function openVocabDrawer(videoId, videoTitle) {
  vocabTitle.textContent = videoTitle || "Vocabulary";
  vocabDrawer.classList.add("open");
  vocabOverlay.classList.add("open");
  document.body.style.overflow = "hidden";

  // Show loading
  vocabList.innerHTML = `
    <div class="vocab-loading">
      <div class="spinner"></div>
      Analysing vocabulary…
    </div>`;

  fetch(`/api/vocab/${videoId}`)
    .then(r => r.json())
    .then(data => renderVocab(data.vocab || []))
    .catch(() => {
      vocabList.innerHTML = `<div class="vocab-empty">Could not load vocabulary. Try again.</div>`;
    });
}

function closeVocabDrawer() {
  vocabDrawer.classList.remove("open");
  vocabOverlay.classList.remove("open");
  document.body.style.overflow = "";
}

function renderVocab(words) {
  if (!words || words.length === 0) {
    vocabList.innerHTML = `<div class="vocab-empty">No vocabulary available for this video.</div>`;
    return;
  }

  vocabList.innerHTML = `<div class="vocab-list">` +
    words.map((w, i) => `
      <div class="vocab-card" style="animation-delay:${i * 0.04}s">
        <div class="vocab-word">${esc(w.word)}</div>
        <div class="vocab-type">${esc(w.type || "word")}</div>
        <div class="vocab-translation">${esc(w.translation)}</div>
        ${w.pronunciation ? `<div class="vocab-pronunciation">${esc(w.pronunciation)}</div>` : ""}
        ${(w.example_fr || w.example_en) ? `
          <div class="vocab-examples">
            ${w.example_fr ? `<div class="vocab-ex-fr">${esc(w.example_fr)}</div>` : ""}
            ${w.example_en ? `<div class="vocab-ex-en">${esc(w.example_en)}</div>` : ""}
          </div>` : ""}
      </div>`
    ).join("") +
  `</div>`;
}

function esc(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

// Close drawer on overlay click or close button
vocabOverlay?.addEventListener("click", closeVocabDrawer);
document.getElementById("vocab-close")?.addEventListener("click", closeVocabDrawer);

// Swipe down to close
(function() {
  if (!vocabDrawer) return;
  let startY = 0;
  vocabDrawer.addEventListener("touchstart", e => { startY = e.touches[0].clientY; }, { passive: true });
  vocabDrawer.addEventListener("touchend", e => {
    if (e.changedTouches[0].clientY - startY > 60) closeVocabDrawer();
  }, { passive: true });
})();

/* ─────────────────────────────────────────────
   LIKE BUTTON
   ───────────────────────────────────────────── */

function initLikes() {
  document.querySelectorAll(".like-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const videoId = btn.dataset.videoId;
      try {
        const res  = await fetch(`/api/like/${videoId}`, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken() },
        });
        const data = await res.json();
        if (data.error === "login_required") {
          window.location.href = "/auth/login";
          return;
        }
        btn.classList.toggle("liked", data.liked);
        const countEl = btn.querySelector(".action-count");
        if (countEl) countEl.textContent = data.count;

        // Heart animation
        const icon = btn.querySelector(".action-icon");
        if (icon) {
          icon.style.transform = "scale(1.25)";
          setTimeout(() => icon.style.transform = "", 200);
        }
      } catch (err) {
        console.error("Like failed", err);
      }
    });
  });
}

/* ─────────────────────────────────────────────
   UPLOAD MODAL
   ───────────────────────────────────────────── */

const uploadOverlay = document.getElementById("upload-overlay");
const uploadModal   = document.getElementById("upload-modal");
const uploadForm    = document.getElementById("upload-form");
const dropZone      = document.getElementById("drop-zone");
const fileInput     = document.getElementById("video-file-input");
const filePreview   = document.getElementById("file-preview");

function openUploadModal() {
  if (!uploadOverlay) return;
  uploadOverlay.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeUploadModal() {
  if (!uploadOverlay) return;
  uploadOverlay.classList.remove("open");
  document.body.style.overflow = "";
}

uploadOverlay?.addEventListener("click", e => {
  if (e.target === uploadOverlay) closeUploadModal();
});

document.getElementById("upload-close")?.addEventListener("click", closeUploadModal);
document.getElementById("open-upload-btn")?.addEventListener("click", openUploadModal);

// Drag & drop
dropZone?.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone?.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) {
    fileInput.files = e.dataTransfer.files;
    showFilePreview(file.name);
  }
});

fileInput?.addEventListener("change", () => {
  if (fileInput.files[0]) showFilePreview(fileInput.files[0].name);
});

function showFilePreview(name) {
  if (filePreview) {
    filePreview.textContent = name;
    filePreview.style.display = "block";
  }
}

// Submit with loading state
uploadForm?.addEventListener("submit", () => {
  const btn = uploadForm.querySelector(".btn-submit");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner" style="border-top-color:#fff"></div> Uploading…`;
  }
});

/* ─────────────────────────────────────────────
   INIT
   ───────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  initFlash();
  initFeed();
  initLikes();
});
