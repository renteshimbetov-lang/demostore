/**
 * BlackStore.uz - Taplink / Linktree Interactive Logic
 */

// State
let activeLinkData = null;

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupEventListeners();
  renderQrCode(window.location.href);
  initZoomLock();
});

// Native Mobile App Zoom Lock (Prevent accidental zooming/pinch)
function initZoomLock() {
  document.addEventListener('gesturestart', function(e) { e.preventDefault(); }, { passive: false });
  document.addEventListener('gesturechange', function(e) { e.preventDefault(); }, { passive: false });
  document.addEventListener('gestureend', function(e) { e.preventDefault(); }, { passive: false });
  
  let lastTouchTime = 0;
  document.addEventListener('touchend', function(e) {
    const now = Date.now();
    if (now - lastTouchTime < 320) {
      if (!e.target.closest('a, button, input, textarea, select, .floating-pill-content')) {
        e.preventDefault();
      }
    }
    lastTouchTime = now;
  }, { passive: false });
}

// Theme Management
function initTheme() {
  const savedTheme = localStorage.getItem('blackstore_theme') || 'light';
  setTheme(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  setTheme(newTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('blackstore_theme', theme);
  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) {
    themeBtn.setAttribute('title', theme === 'dark' ? "Yorug' rejimga o'tish" : "Qorong'i rejimga o'tish");
    themeBtn.innerHTML = theme === 'dark' 
      ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`
      : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
  }
}

// Event Listeners
function setupEventListeners() {
  // Share modal trigger
  const shareBtn = document.getElementById('topShareBtn');
  if (shareBtn) {
    shareBtn.addEventListener('click', handlePageShare);
  }

  // Floating dock share / close
  const floatingDock = document.getElementById('floatingBottomDock');
  const floatingClose = document.getElementById('floatingCloseBtn');
  if (floatingClose) {
    floatingClose.addEventListener('click', (e) => {
      e.stopPropagation();
      if (floatingDock) floatingDock.style.display = 'none';
    });
  }

  // Setup click handler for three dots
  const threeDotBtns = document.querySelectorAll('.btn-three-dots');
  threeDotBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const title = btn.getAttribute('data-title');
      const url = btn.getAttribute('data-url');
      openLinkActionModal({ title, url });
    });
  });

  // Close modals on backdrop click
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeAllModals();
      }
    });
  });

  // Esc key to close modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllModals();
    }
  });
}

// Share handler
function handlePageShare() {
  const shareData = {
    title: 'DemoStore.uz - Apple mahsulotlari markazi',
    text: "DemoStore.uz rasmiy havolalari va aloqa kanallari!",
    url: window.location.href
  };

  if (navigator.share && /mobile|android|iphone|ipad/i.test(navigator.userAgent)) {
    navigator.share(shareData).catch(() => {
      openShareModal();
    });
  } else {
    openShareModal();
  }
}

function openShareModal() {
  closeAllModals();
  const modal = document.getElementById('shareModal');
  const shareInput = document.getElementById('shareUrlInput');
  if (shareInput) {
    shareInput.value = window.location.href;
  }
  if (modal) modal.classList.add('active');
}

function closeShareModal() {
  const modal = document.getElementById('shareModal');
  if (modal) modal.classList.remove('active');
}

// Link Actions Modal (3 dots)
function openLinkActionModal(item) {
  closeAllModals();
  activeLinkData = item;
  const modal = document.getElementById('linkActionModal');
  const titleEl = document.getElementById('linkActionTitle');
  const urlEl = document.getElementById('linkActionUrl');

  if (titleEl) titleEl.textContent = item.title;
  if (urlEl) urlEl.textContent = item.url;
  if (modal) modal.classList.add('active');
}

function closeLinkActionModal() {
  const modal = document.getElementById('linkActionModal');
  if (modal) modal.classList.remove('active');
  activeLinkData = null;
}

function copyActiveLinkUrl() {
  if (!activeLinkData) return;
  copyToClipboard(activeLinkData.url, `${activeLinkData.title} havolasi nusxalandi!`);
  closeLinkActionModal();
}

function shareActiveLinkUrl() {
  if (!activeLinkData) return;
  if (navigator.share) {
    navigator.share({
      title: activeLinkData.title,
      url: activeLinkData.url
    }).catch(() => {});
  } else {
    copyActiveLinkUrl();
  }
}

function openActiveLinkDirectly() {
  if (!activeLinkData) return;
  window.open(activeLinkData.url, '_blank', 'noopener,noreferrer');
  closeLinkActionModal();
}

// QR Code Modal
function openQrModal() {
  closeAllModals();
  const modal = document.getElementById('qrModal');
  if (modal) modal.classList.add('active');
}

function closeQrModal() {
  const modal = document.getElementById('qrModal');
  if (modal) modal.classList.remove('active');
}

function closeAllModals() {
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.classList.remove('active');
  });
}

// Clipboard copy helper
function copyPageUrl() {
  copyToClipboard(window.location.href, "Havola buferga nusxalandi");
}

function copyToClipboard(text, message) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(message || "Nusxa olindi");
    }).catch(() => {
      fallbackCopyText(text, message);
    });
  } else {
    fallbackCopyText(text, message);
  }
}

function fallbackCopyText(text, message) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    showToast(message || "Nusxa olindi");
  } catch (err) {
    showToast("Nusxalashda xatolik yuz berdi");
  }
  document.body.removeChild(textarea);
}

// Toast System
let toastTimeout = null;
function showToast(message) {
  const toast = document.getElementById('toastMsg');
  const toastText = document.getElementById('toastText');
  if (!toast || !toastText) return;

  toastText.textContent = message;
  toast.classList.add('show');

  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.classList.remove('show');
  }, 2600);
}

// Lightweight Dynamic QR Code generation using QuickChart / SVG API
function renderQrCode(url) {
  const qrContainer = document.getElementById('qrCodeContainer');
  if (!qrContainer) return;

  const encoded = encodeURIComponent(url);
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encoded}&bgcolor=ffffff&color=000000&margin=2`;

  const img = new Image();
  img.src = qrUrl;
  img.alt = "DemoStore QR Code";
  img.width = 200;
  img.height = 200;
  img.style.borderRadius = "12px";
  img.style.display = "block";

  img.onload = () => {
    qrContainer.innerHTML = '';
    qrContainer.appendChild(img);
  };
  
  img.onerror = () => {
    qrContainer.innerHTML = `
      <div style="width: 200px; height: 200px; display:flex; align-items:center; justify-content:center; background:#eee; border-radius:12px; font-size:12px; color:#555;">
        DemoStore.uz QR
      </div>
    `;
  };
}

// Interactive buttons showcase in Taplink
document.addEventListener('DOMContentLoaded', () => {
  const tapLiquid = document.getElementById('taplinkLiquidDemo');
  const tapBounce = document.getElementById('taplinkBounceDemo');
  const tapRipple = document.getElementById('taplinkRippleDemo');
  const tap3d = document.getElementById('taplink3dDemo');
  const tapSubmit = document.getElementById('taplinkSubmitBtn');

  tapLiquid?.addEventListener('click', () => showToast('💎 Liquid Glass: Shaffof shisha effekti!'));
  tapBounce?.addEventListener('click', () => showToast('⚡ Spring Bounce: Yumshoq sakrash!'));
  tapRipple?.addEventListener('click', () => showToast('🌊 Ripple Wave: Suv to‘lqini effekti!'));
  tap3d?.addEventListener('click', () => showToast('🎮 3D Tactile: Duolingo chuqur bosilish effekti!'));
  tapSubmit?.addEventListener('click', () => {
    if (window.MiniApp && typeof window.MiniApp.showLoading === 'function') {
      window.MiniApp.showLoading(tapSubmit);
      setTimeout(() => {
        window.MiniApp.hideLoading(tapSubmit);
        window.MiniApp.haptic('success');
        showToast('✅ Yuklanish muvaffaqiyatli yakunlandi!');
      }, 1400);
    }
  });
});
