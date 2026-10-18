// DemoStore Telegram Mini App — Mobile-First Architecture
(function () {
  'use strict';

  // 1. Telegram WebApp Initsializatsiyasi (To'liq ekranga to'lish & Header himoyasi)
  const tg = window.Telegram?.WebApp;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      // Telegram Bot API 8.0+: To'liq ekranga ochish (Fullscreen mode)
      if (typeof tg.requestFullscreen === 'function') {
        tg.requestFullscreen();
      }
      if (typeof tg.disableVerticalSwipes === 'function') {
        tg.disableVerticalSwipes();
      }
      if (typeof tg.enableClosingConfirmation === 'function') {
        tg.enableClosingConfirmation();
      }
      if (typeof tg.setHeaderColor === 'function') {
        tg.setHeaderColor('#ffffff');
      }
      if (typeof tg.setBackgroundColor === 'function') {
        tg.setBackgroundColor('#ffffff');
      }
    } catch (e) {
      console.warn('Telegram WebApp init ogohlantirish:', e);
    }
  }

  // Foydalanuvchi ekranga birinchi marta teginganda to'liq ekranga kirishni kafolatlash
  function ensureFullscreenMode() {
    if (tg && !tg.isFullscreen && typeof tg.requestFullscreen === 'function') {
      try {
        tg.requestFullscreen();
      } catch (e) {}
    }
  }
  window.addEventListener('touchstart', ensureFullscreenMode, { passive: true, once: true });
  window.addEventListener('click', ensureFullscreenMode, { once: true });

  // Telegram Top Clearance va Safe Area (Ustma-ust tushishni 100% oldini olish)
  let lastSafeTop = 0;
  let lastSafeBottom = 0;
  function updateSafeArea() {
    try {
      const isTg = Boolean(window.Telegram?.WebApp?.initData || window.Telegram?.WebApp?.platform);
      const isFullscreen = Boolean(tg?.isFullscreen);

      const contentTop = Number(tg?.contentSafeAreaInset?.top) || 0;
      const safeTop = Number(tg?.safeAreaInset?.top) || 0;
      const isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

      let finalTop = 14;

      if (contentTop >= 60) {
        // Telegram Bot API 8.0 content safe area (floating bar included)
        finalTop = contentTop + 4;
      } else if (safeTop > 0) {
        // Safe area (Notch/Dynamic Island 47-59px) + Telegram native floating bar (44px) = 91-103px
        finalTop = safeTop + 44;
      } else if (isTg && isMobileDevice) {
        // Mobil Telegram mini ilovada insetlar 0 bo'lsa zaxira
        finalTop = 90;
      } else if (isTg) {
        // Telegram Desktop
        finalTop = 18;
      } else if (isMobileDevice) {
        finalTop = 14;
      }

      if (finalTop !== lastSafeTop) {
        lastSafeTop = finalTop;
        document.documentElement.style.setProperty('--app-safe-top', `${finalTop}px`);
        updateHeaderHeight();
      }

      const contentBottom = Number(tg?.contentSafeAreaInset?.bottom) || 0;
      const safeBottom = Number(tg?.safeAreaInset?.bottom) || 0;
      let finalBottom = Math.max(contentBottom, safeBottom, 16);
      if (finalBottom !== lastSafeBottom) {
        lastSafeBottom = finalBottom;
        document.documentElement.style.setProperty('--app-safe-bottom', `${finalBottom}px`);
      }
    } catch (e) {}
  }
  updateSafeArea();
  tg?.onEvent?.('safeAreaChanged', updateSafeArea);
  tg?.onEvent?.('contentSafeAreaChanged', updateSafeArea);
  tg?.onEvent?.('fullscreenChanged', () => {
    updateSafeArea();
  });
  tg?.onEvent?.('fullscreenFailed', () => {
    tg?.expand?.();
    updateSafeArea();
  });
  tg?.onEvent?.('viewportChanged', updateSafeArea);

  // 1.1 Xavfsiz API so'rov yordamchisi (Telegram WebApp initData bilan)
  function getTelegramInitData() {
    return window.Telegram?.WebApp?.initData || '';
  }

  async function apiFetch(url, options = {}) {
    const opts = { ...options };
    const headers = { ...(opts.headers || {}) };
    const initData = getTelegramInitData();
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }
    opts.headers = headers;
    return fetch(url, opts);
  }

  function updateHeaderHeight() {
    const header = document.getElementById('mobileHeader');
    if (header && !header.classList.contains('hidden')) {
      const h = header.offsetHeight;
      if (h > 0) {
        document.documentElement.style.setProperty('--header-height', `${h}px`);
      }
    }
  }
  window.addEventListener('resize', updateHeaderHeight);
  window.addEventListener('orientationchange', updateHeaderHeight);

  // Haptic feedback yordamchisi (Native Telegram Mini App haptic physics)
  function triggerHaptic(type = 'light') {
    try {
      if (tg?.HapticFeedback) {
        if (type === 'success' || type === 'error' || type === 'warning') {
          tg.HapticFeedback.notificationOccurred(type);
        } else if (type === 'selection') {
          tg.HapticFeedback.selectionChanged();
        } else {
          tg.HapticFeedback.impactOccurred(type);
        }
      } else if (navigator.vibrate) {
        if (type === 'success') navigator.vibrate([15, 30, 20]);
        else navigator.vibrate(20);
      }
    } catch (err) {}
  }

  // Narxni har doim AQSH dollari ($ USD) formatida chiqarish
  function formatPrice(amount) {
    if (!amount) return '$0';
    return '$' + amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  // So'm miqdorini formatlash (masalan 299 000 soʻm)
  function formatUzsAmount(amount) {
    if (!amount) return '0 soʻm';
    return Math.round(Number(amount)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' soʻm';
  }

  // Narxni joriy jonli dollar kursi bo'yicha so'mda chiqarish
  function formatPriceUzs(amountUsd) {
    if (!amountUsd) return '0 soʻm';
    const rate = state?.currentUsdRate || 12850;
    const uzs = Math.round(amountUsd * rate);
    return formatUzsAmount(uzs);
  }

  // Mahsulot kartochkasi narx blokini chizish (so'mda kiritilgan mahsulotlar FAQAT SO'MDA chiqadi)
  function renderProductPriceBlock(p) {
    if (p && p.currency === 'UZS' && p.price_uzs) {
      return `
        <div class="price-wrap">
          <span class="price-current">${formatUzsAmount(p.price_uzs)}</span>
        </div>
      `;
    }
    return `
      <div class="price-wrap">
        <span class="price-current">${formatPrice(p.price)}</span>
        <span class="price-uzs">≈ ${formatPriceUzs(p.price)}</span>
      </div>
    `;
  }

  // Sarlavhadagi jonli kurs belgisini (badge) yangilash (foydalanuvchi talabiga ko'ra o'chirildi)
  function updateLiveUsdBadge(rate) {
    const el = document.getElementById('liveUsdBadge');
    if (el) el.style.display = 'none';
  }

  const CURRENCY_CACHE_TTL_MS = 10 * 60 * 1000; // 10 daqiqa (10-15 daqiqalik yengil kesh)

  // Barcha sahifalardagi so'm narxlarini joriy kurs bo'yicha dinamik yangilash
  function refreshAllUzsPrices() {
    if (Array.isArray(state.products)) {
      state.products.forEach(p => {
        p.current_usd_rate = state.currentUsdRate;
        if (p.currency !== 'UZS' || !p.price_uzs) {
          p.price_uzs = Math.round((p.price || 0) * state.currentUsdRate);
        }
      });
      try {
        localStorage.setItem('demostore_cached_products', JSON.stringify(state.products));
      } catch (e) {}
    }

    // 1. Asosiy va katalog mahsulot kartalarini yangilash
    if (typeof renderProducts === 'function') renderProducts(true);
    if (typeof renderCatalogProducts === 'function') renderCatalogProducts();
    if (typeof renderDiscountsSlider === 'function') renderDiscountsSlider();

    // 2. Savatcha va to'lov summasini yangilash
    if (typeof renderCartSection === 'function') renderCartSection();
    if (typeof updateCartBadges === 'function') updateCartBadges();

    // 3. Agar mahsulot tafsilot sahifasi/modal ochiq bo'lsa, undagi so'm narxini yangilash
    if (state.selectedProduct) {
      const isUzsOnly = Boolean(state.selectedProduct.currency === 'UZS' && state.selectedProduct.price_uzs);
      const pdBottomPriceUzsEl = document.getElementById('pdBottomPriceUzs');
      if (pdBottomPriceUzsEl) {
        pdBottomPriceUzsEl.textContent = isUzsOnly ? '' : `≈ ${formatPriceUzs(state.selectedProduct.price)}`;
      }
      const pdHeroUzsEl = document.querySelector('.pd-hero-uzs');
      if (pdHeroUzsEl) {
        pdHeroUzsEl.textContent = isUzsOnly ? '' : `≈ ${formatPriceUzs(state.selectedProduct.price)}`;
      }
    }
  }

  // Markaziy Bank kursini API orqali olish (10 daqiqalik yengil kesh mexanizmi bilan)
  async function fetchLiveCurrencyRate(force = false) {
    try {
      const lastFetchTime = parseInt(localStorage.getItem('demostore_cached_usd_rate_time') || '0', 10);
      const now = Date.now();
      if (!force && lastFetchTime && (now - lastFetchTime) < CURRENCY_CACHE_TTL_MS && state.currentUsdRate > 1000) {
        return; // Keshdagi kurs 10 daqiqadan oshmagan, ortiqcha so'rov yuborilmaydi
      }

      const res = await apiFetch('/api/currency' + (force ? '?force=1' : ''));
      if (res.ok) {
        const data = await res.json();
        if (data && data.rate && data.rate > 0) {
          const oldRate = state.currentUsdRate;
          state.currentUsdRate = data.rate;
          localStorage.setItem('demostore_cached_usd_rate', String(data.rate));
          localStorage.setItem('demostore_cached_usd_rate_time', String(now));
          updateLiveUsdBadge(data.rate);

          // Kurs o'zgarsa yoki yangilansa ilovadagi barcha so'm narxlarini qayta hisoblash
          if (oldRate !== data.rate || (state.products && state.products.length > 0)) {
            refreshAllUzsPrices();
          }
        }
      }
    } catch (e) {
      console.warn('Jonli kurs yuklashda ogohlantirish:', e);
    }
  }

  // Barcha matnlardan stiker va emojilarni tozalovchi sof funksiya
  function stripAllEmojis(str) {
    if (!str) return '';
    return str
      .replace(/[\p{Extended_Pictographic}\uFE0F\uFE0E\u200D\u200C]/gu, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  // Tavsif matnidagi parametrlarni to'liq va aqlli ajratib olish (Telefon va Noutbuklar uchun)
  function parseSpecs(desc) {
    if (!desc) return [];
    const lines = desc.split('\n');
    const specs = [];
    const seenKeys = new Set();

    function addSpec(key, val) {
      if (!key || !val) return;
      let cleanVal = stripAllEmojis(val).trim();
      if (!cleanVal) return;
      const cleanKey = stripAllEmojis(key).trim();

      // Agar qiymat boshida kalit so'zi (masalan, "Protsessor: M1", "Ekran: 13.3") takrorlangan bo'lsa, tozalaymiz
      const keyPrefix = cleanKey.split(/[\s(]/)[0].trim();
      if (keyPrefix) {
        cleanVal = cleanVal.replace(new RegExp(`^${keyPrefix}[:\\s-]*`, 'i'), '').trim();
      }
      cleanVal = cleanVal.replace(/^(?:protsessor|chip|ekran|display|rangi?|xotira|ram|holat|holati?)[:\\s-]*/i, '').trim();

      if (!cleanVal) return;
      if (seenKeys.has(cleanKey)) return;
      seenKeys.add(cleanKey);
      specs.push({ key: cleanKey, val: cleanVal });
    }

    lines.forEach(line => {
      const raw = line.trim();
      if (!raw) return;
      const lower = raw.toLowerCase();

      // Narx, aloqa, manzil va menejer ma'lumotlarini o'tkazib yuborish
      if (
        lower.includes('menejer') || lower.includes('telefon') || lower.includes('+998') ||
        lower.includes('kanal') || lower.includes('lokatsiya') || lower.includes('malika') ||
        lower.includes('beruniy') || lower.includes('bog’lanish') || lower.includes('bog\'lanish') ||
        lower.includes('narxi') || lower.includes('narx') || lower.includes('заказ') ||
        lower.includes('t.me') || lower.includes('telegram') || lower.includes('улгуриб') ||
        lower.includes('муддатли') || lower.includes('бошига') || lower.includes('ой ')
      ) {
        return;
      }

      // 1. Xotira (Storage / Hotirasi)
      if (raw.includes('🧠') || (lower.includes('xotira') && !lower.includes('operativ')) || /^(\d+\s*(?:gb|tb))$/i.test(lower)) {
        const m = raw.match(/(\d+\s*(?:gb|tb))/i);
        if (m) {
          addSpec('Xotira (Hotirasi)', m[1].toUpperCase());
          return;
        }
      }

      // 2. Batareya / Yomkost
      if (raw.includes('🔋') || lower.includes('yomkost') || lower.includes('ёмкость') || lower.includes('batereya') || lower.includes('batareya')) {
        const pctM = raw.match(/(\d{2,3}\s*%)/);
        const cycM = raw.match(/(\d+\s*(?:sikl|цикл))/i);
        let val = pctM ? pctM[1].trim() : '';
        if (cycM) {
          val = val ? `${val} (${cycM[1].trim()})` : cycM[1].trim();
        }
        if (!val) {
          val = raw.replace(/^[^\w\d%]+/, '').trim();
        }
        if (val) {
          addSpec('Batareya (Yomkost)', val);
          return;
        }
      }

      // 3. Batareya sikli (Alohida sikl qatori)
      if (/^\d+\s*(?:цикл|sikl)/i.test(lower)) {
        addSpec('Batareya sikli', raw.trim());
        return;
      }

      // 4. Rangi (Color)
      if (
        raw.includes('🎨') || lower.startsWith('rangi') ||
        ['black', 'blue', 'silver', 'natural', 'gold', 'desert', 'white', 'pink', 'space black'].includes(lower)
      ) {
        let val = raw.replace(/^[^\w\d]+/, '').trim();
        val = val.replace(/^rangi?[:\s]*/i, '').trim();
        if (val) {
          const capVal = val.charAt(0).toUpperCase() + val.slice(1);
          addSpec('Rangi', capVal);
          return;
        }
      }

      // 5. Region / SIM formati
      if (raw.includes('🌍') || lower.includes('e/sim') || lower.includes('esim') || /^[A-Z]{2}\/[A-Z]$/.test(raw.trim())) {
        const regM = raw.match(/([A-Z]{2}\/[A-Z])/);
        if (regM) {
          addSpec('Region', regM[1]);
        } else {
          const simClean = raw.replace(/^[^\w\d/+\s]+/, '').trim();
          addSpec('SIM formati', simClean);
        }
        return;
      }

      // 6. Karobka & Hujjatlar
      if (raw.includes('📦') || raw.includes('🎁') || lower.includes('box') || lower.includes('karobka')) {
        if (lower.includes('nobox') || raw.includes('❌')) {
          addSpec('Karobka & Hujjat', 'Nobox (Karobkasiz)');
        } else {
          addSpec('Karobka & Hujjat', "To'liq komplekt mavjud");
        }
        return;
      }

      // 7. Tashqi holati (Condition)
      if (raw.includes('🛠') || lower.includes('holat') || lower.includes('состояние') || lower.includes('как новый')) {
        if (raw.includes('⭐️') || raw.includes('⭐')) {
          addSpec('Tashqi holati', "A'lo darajada");
        } else {
          const val = stripAllEmojis(raw.replace(/^[^\w\d]+/, ''));
          addSpec('Tashqi holati', val);
        }
        return;
      }

      // 8. IMEI / Kod / Part number
      if (raw.includes('📟') || raw.includes('🔎') || lower.includes('imei') || lower.includes('part number') || lower.includes('seriya') || /^[a-z]\d{3,5}$/i.test(raw.replace(/^[^\w\d]+/, '').trim())) {
        const val = stripAllEmojis(raw.replace(/^[^\w\d]+/, ''));
        if (val) {
          addSpec('Kod / IMEI', val);
          return;
        }
      }

      // 9. Kafolat
      if (lower.includes('kafolat') || lower.includes('гарантия')) {
        const val = stripAllEmojis(raw.replace(/^[^\w\d]+/, ''));
        addSpec('Kafolat', val);
        return;
      }

      // 9. Operativ xotira (RAM)
      if (lower.includes('operativ') || lower.includes('ram')) {
        const m = raw.match(/(\d+\s*gb)/i);
        if (m) {
          addSpec('Operativ xotira (RAM)', m[1].toUpperCase());
          return;
        }
      }

      // 10. Protsessor
      if (lower.includes('protsessor') || lower.includes('chip')) {
        let val = stripAllEmojis(raw);
        val = val.replace(/^(?:protsessor|chip)[:\s-]*/i, '').trim();
        val = val.replace(/^[^\w\d]+/, '').trim();
        if (val) {
          addSpec('Protsessor', val);
          return;
        }
      }

      // 11. Ekran
      if (lower.includes('ekran') || lower.includes('display')) {
        let val = stripAllEmojis(raw);
        val = val.replace(/^(?:ekran|display)[:\s-]*/i, '').trim();
        val = val.replace(/^[^\w\d]+/, '').trim();
        if (val) {
          addSpec('Ekran', val);
          return;
        }
      }

      // 12. Touch ID
      if (lower.includes('touch id')) {
        addSpec('Xavfsizlik', 'Touch ID');
        return;
      }

      // 13. Standart Key: Value juftliklari
      if (raw.includes(':')) {
        const parts = raw.split(':');
        const k = parts[0].replace(/^[^\w\d]+/, '').trim();
        const v = parts.slice(1).join(':').trim();
        if (k && v && k.length < 30 && v.length < 60) {
          addSpec(k, v);
        }
      }
    });

    return specs;
  }

  // Mahsulot matnidan faqat mahsulotga oid to'liq ma'lumotlarni qoldirish (do'kon reklamalari, kontaktlar va narxlarni olib tashlash)
  function getCleanProductDescription(desc) {
    if (!desc) return '';
    const lines = desc.split('\n');
    const cleaned = [];

    lines.forEach(line => {
      const trimmed = line.trim();
      if (!trimmed) {
        if (cleaned.length > 0 && cleaned[cleaned.length - 1] !== '') {
          cleaned.push('');
        }
        return;
      }
      const lower = trimmed.toLowerCase();

      // Kontaktlar, menejer, manzil va narx satrlarini tozalash
      if (
        lower.includes('menejer') || lower.includes('telefon') || lower.includes('+998') ||
        lower.includes('lokatsiya') || lower.includes('malika') || lower.includes('beruniy') ||
        lower.includes('bog’lanish') || lower.includes('bog\'lanish') || lower.includes('murojaat') ||
        lower.includes('t.me/') || lower.includes('telegram kanal') ||
        (lower.includes('@') && !lower.includes('display')) ||
        lower.includes('manzil') || lower.includes('do\'kon') || lower.includes('dokon') ||
        lower.startsWith('narxi:') || lower.startsWith('narx:') || lower.startsWith('baho:') ||
        lower.includes('муддатли тулов') || lower.includes('бошига:') || lower.includes('muddatli to\'lov')
      ) {
        return;
      }

      cleaned.push(trimmed);
    });

    return cleaned.join('\n').trim();
  }

  // Bo'lib to'lash (Muddatli to'lov) rejalarini ajratib olish
  function parseInstallmentPlan(desc) {
    if (!desc) return null;
    const lines = desc.split('\n');
    const plans = [];
    let initialPay = '';
    let hasInstallment = false;

    lines.forEach(line => {
      const lower = line.toLowerCase();
      if (lower.includes('муддатли') || lower.includes('muddatli')) {
        hasInstallment = true;
      }
      if (lower.includes('бошига') || lower.includes('boshiga')) {
        initialPay = line.replace(/^[^\w\d]+/, '').trim();
        hasInstallment = true;
      }
      const match = line.match(/(\d+)\s*(?:ой|oy)\s*(\d+[\$]?)/i);
      if (match) {
        plans.push(`${match[1]} oy: ${match[2]}`);
        hasInstallment = true;
      }
    });

    if (!hasInstallment) return null;
    return {
      initialPay: initialPay || "Boshlang'ich to'lov mavjud",
      plans: plans
    };
  }

  // Mahsulot kartasida ko'rsatiladigan asosiy nishonlar (Storage, Color, Battery)
  function getProductKeyBadges(prod) {
    const specs = parseSpecs(prod.description);
    const badges = [];
    const storage = specs.find(s => s.key.includes('Xotira'));
    if (storage) badges.push({ text: stripAllEmojis(storage.val), type: 'storage' });
    const color = specs.find(s => s.key === 'Rangi');
    if (color) badges.push({ text: stripAllEmojis(color.val), type: 'color' });
    const bat = specs.find(s => s.key.includes('Batareya'));
    if (bat) {
      const pctMatch = bat.val.match(/\d+%/);
      badges.push({ text: pctMatch ? pctMatch[0] : stripAllEmojis(bat.val), type: 'battery' });
    }
    const ram = specs.find(s => s.key.includes('RAM'));
    if (ram && badges.length < 3) badges.push({ text: `RAM ${stripAllEmojis(ram.val)}`, type: 'ram' });
    return badges;
  }

  // Mahsulot kartasida faqat toza model nomini ko'rsatish (stikerlar, emojilar va qavslarsiz 100% toza)
  function getCleanCardTitle(name) {
    if (!name) return 'Mahsulot';
    return stripAllEmojis(
      name
        .replace(/\s*\([^)]*\)/g, '')
        .replace(/\s*-\s*\$?\d+\$?\s*$/g, '')
        .replace(/[^\p{L}\p{N}]+$/gu, '')
    ) || 'Mahsulot';
  }

  // Toifa bo'yicha qat'iy va xatosiz filtrlash (Noutbuklar, soatlar, quloqchinlar hech qachon smartfonga kirmaydi)
  function isProductInCategory(p, catId) {
    if (!catId || catId === 0) return true;
    const name = (p.name || '').toLowerCase();
    const catName = (p.category_name || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();

    // 1. SMARTFONLAR (Smartphones)
    if (catId === 1) {
      // Noutbuk, soat, quloqchin hech qachon smartfon toifasiga kirmaydi
      if (
        name.includes('macbook') || name.includes('surface') || name.includes('asus') || name.includes('laptop') || name.includes('noutbuk') ||
        name.includes('watch') || name.includes('soat') || name.includes('iwatch') ||
        name.includes('airpods') || name.includes('quloqchin') || name.includes('naushnik') || name.includes('headphone')
      ) {
        return false;
      }
      if (p.category_id === 1 && !catName.includes('soat') && !catName.includes('audio') && !catName.includes('noutbuk')) return true;
      if (catName.includes('smartfon') || name.includes('iphone') || name.includes('samsung') || name.includes('galaxy') || name.includes('redmi')) {
        return true;
      }
      return false;
    }

    // 2. NOUTBUKLAR (Laptops)
    if (catId === 2) {
      if (
        name.includes('iphone') || name.includes('smartfon') || name.includes('redmi') || name.includes('galaxy') ||
        name.includes('watch') || name.includes('soat') || name.includes('iwatch') ||
        name.includes('airpods') || name.includes('quloqchin')
      ) {
        return false;
      }
      if (p.category_id === 2) return true;
      if (catName.includes('noutbuk') || catName.includes('laptop') || name.includes('macbook') || name.includes('surface') || name.includes('asus') || desc.includes('macbook')) {
        return true;
      }
      return false;
    }

    // 3. QULOQCHINLAR VA AUDIO
    if (catId === 3) {
      if (name.includes('macbook') || name.includes('iphone') || name.includes('watch') || name.includes('soat') || name.includes('iwatch')) {
        return false;
      }
      return p.category_id === 3 || catName.includes('audio') || name.includes('airpods') || name.includes('quloqchin') || name.includes('naushnik') || name.includes('buds');
    }

    // 4. AQLLI SOATLAR
    if (catId === 4) {
      if (name.includes('macbook') || name.includes('iphone') || name.includes('airpods')) {
        return false;
      }
      return p.category_id === 4 || catName.includes('soat') || name.includes('watch') || name.includes('soat') || name.includes('iwatch') || desc.includes('iwatch') || desc.includes('apple watch');
    }

    // 5. AKSESSUARLAR
    if (catId === 5) {
      return p.category_id === 5 || catName.includes('aksessuar');
    }

    return p.category_id === catId;
  }

  // ==========================================================================
  // KO'P TILLILIK TIZIMI (I18N: UZ / RU / EN)
  // ==========================================================================
  const I18N = {
    uz: {
      lang_name: "Oʻzbek tili",
      lang_code: "UZ",
      nav_home: "Bosh sahifa",
      nav_catalog: "Katalog",
      nav_cart: "Savat",
      nav_wishlist: "Sevimlilar",
      nav_profile: "Profil",
      search_placeholder: "Mahsulotlarni qidirish...",
      cat_all: "Barchasi",
      cat_smartphones: "Smartfonlar",
      cat_laptops: "Noutbuklar",
      cat_audio: "Quloqchinlar va Audio",
      cat_watches: "Aqlli soatlar",
      cat_accessories: "Aksessuarlar",
      weekly_discounts: "Hafta chegirmalari",
      see_all: "Hammasini koʻrish",
      popular_products: "Ommabop tovarlar",
      search_results: "Qidiruv natijalari",
      filter: "Filtr",
      filter_title: "Saralash & Filtr",
      sort_default: "Odatiy (Kanal tartibi)",
      sort_popular: "Eng ommabop mahsulotlar",
      sort_price_asc: "Arzonroqdan qimmatroqqa ($)",
      sort_price_desc: "Qimmatroqdan arzonroqqa ($)",
      sort_newest: "Eng yangi qoʻshilganlar",
      apply: "Qoʻllash",
      add_to_cart: "Savatga",
      buy_now: "Savatga",
      go_to_order: "Buyurtmaga",
      filter_price_title: "Narx boʻyicha qidirish",
      sort_title: "Saralash tartibi",
      price_dan: "Dan",
      price_gacha: "Gacha",
      price_range_all: "Barchasi",
      view_in_channel: "Kanaldan koʻrish",
      adding: "Qo'shilmoqda...",
      added: "Qo'shildi!",
      clear: "Tozalash",
      checkout: "Buyurtma berish",
      subtotal: "Tovarlar narxi:",
      total: "Jami toʻlov:",
      price_label: "Narxi:",
      back: "Orqaga",
      empty_title: "Hech narsa topilmadi",
      empty_desc: "Qidiruv soʻrovingiz yoki tanlangan toifa boʻyicha mahsulot mavjud emas.",
      reset_filters: "Filtrlarni tozalash",
      cart_empty_title: "Savatingiz boʻsh",
      cart_empty_desc: "Siz hali savatga birorta ham mahsulot qoʻshmadingiz.",
      wishlist_empty_title: "Sevimlilar roʻyxati boʻsh",
      wishlist_empty_desc: "Yoqqan mahsulotlaringizning yurakchasini bosib shu yerda saqlab qoʻyishingiz mumkin.",
      start_shopping: "Mahsulotlarni koʻrish",
      cart_cleared: "Savatingiz tozalandi",
      app_settings: "Ilova sozlamalari",
      theme_label: "Tungi / Kunduzgi rejim",
      theme_dark_active: "Tungi rejim faol",
      theme_light_active: "Kunduzgi rejim faol",
      app_language: "Ilova tili",
      select_language: "Ilova tili:",
      support_title: "Bogʻlanish va Qoʻllab-quvvatlash",
      tg_channel: "Rasmiy Telegram Kanal",
      tg_manager: "Menejer bilan aloqa (Buyurtma)",
      phone_call: "Telefon orqali qoʻngʻiroq",
      guarantee_title: "DEMOSTORE KAFOLATI",
      guarantee_desc: "Barcha Apple qurilmalari yangi va qadoqlangan holatda yetkaziladi. Toshkent boʻylab 2 soatda, viloyatlarga 1 kunda yetkazib berish mavjud.",
      work_hours: "Ish vaqti: Har kuni 09:00 dan 22:00 gacha",
      original_apple: "Asl Apple",
      customer_badge: "DemoStore mijozi",
      catalog_title: "Katalog",
      catalog_subtitle: "Toifani tanlang yoki barcha tovarlarni koʻring",
      wishlist_title: "Sevimlilar",
      profile_title: "Profil va Aloqa",
      profile_subtitle: "Shaxsiy kabinet va qoʻllab-quvvatlash",
      cart_title: "Savat",
      items_suffix: "ta mahsulot",
      saved_suffix: "ta saqlangan mahsulot"
    },
    ru: {
      lang_name: "Русский язык",
      lang_code: "RU",
      nav_home: "Главная",
      nav_catalog: "Каталог",
      nav_cart: "Корзина",
      nav_wishlist: "Избранное",
      nav_profile: "Профиль",
      search_placeholder: "Поиск товаров...",
      cat_all: "Все товары",
      cat_smartphones: "Смартфоны",
      cat_laptops: "Ноутбуки",
      cat_audio: "Наушники и аудио",
      cat_watches: "Умные часы",
      cat_accessories: "Аксессуары",
      weekly_discounts: "Скидки недели",
      see_all: "Все товары",
      popular_products: "Популярные товары",
      search_results: "Результаты поиска",
      filter: "Фильтр",
      filter_title: "Сортировка и фильтр",
      sort_default: "По умолчанию (порядок канала)",
      sort_popular: "Самые популярные товары",
      sort_price_asc: "Сначала дешевле ($)",
      sort_price_desc: "Сначала дороже ($)",
      sort_newest: "Сначала новинки",
      apply: "Применить",
      add_to_cart: "В корзину",
      buy_now: "В корзину",
      go_to_order: "К заказу",
      filter_price_title: "Поиск по цене",
      sort_title: "Порядок сортировки",
      price_dan: "От",
      price_gacha: "До",
      price_range_all: "Все цены",
      view_in_channel: "В канале",
      adding: "Добавление...",
      added: "Добавлено!",
      clear: "Очистить",
      checkout: "Оформить заказ",
      subtotal: "Стоимость товаров:",
      total: "Итого к оплате:",
      price_label: "Цена:",
      back: "Назад",
      empty_title: "Ничего не найдено",
      empty_desc: "По вашему запросу товары не найдены.",
      reset_filters: "Сбросить фильтры",
      cart_empty_title: "Корзина пуста",
      cart_empty_desc: "Вы еще не добавили ни одного товара в корзину.",
      wishlist_empty_title: "Список избранного пуст",
      wishlist_empty_desc: "Нажмите на сердечко, чтобы сохранить понравившийся товар.",
      start_shopping: "Перейти к покупкам",
      cart_cleared: "Корзина очищена",
      app_settings: "Настройки приложения",
      theme_label: "Тёмная / Светлая тема",
      theme_dark_active: "Тёмная тема активна",
      theme_light_active: "Светлая тема активна",
      app_language: "Язык интерфейса",
      select_language: "Язык приложения:",
      support_title: "Связь и поддержка",
      tg_channel: "Официальный Telegram канал",
      tg_manager: "Связь с менеджером (Заказ)",
      phone_call: "Звонок по телефону",
      guarantee_title: "ГАРАНТИЯ DEMOSTORE",
      guarantee_desc: "Все устройства Apple доставляются новыми и запечатанными. Доставка по Ташкенту за 2 часа, в регионы — за 1 день.",
      work_hours: "Режим работы: Ежедневно с 09:00 до 22:00",
      original_apple: "Оригинал Apple",
      customer_badge: "Клиент DemoStore",
      catalog_title: "Каталог",
      catalog_subtitle: "Выберите категорию или посмотрите все товары",
      wishlist_title: "Избранное",
      profile_title: "Профиль и контакты",
      profile_subtitle: "Личный кабинет и поддержка",
      cart_title: "Корзина",
      items_suffix: "товаров",
      saved_suffix: "сохраненных товаров"
    },
    en: {
      lang_name: "English",
      lang_code: "EN",
      nav_home: "Home",
      nav_catalog: "Catalog",
      nav_cart: "Cart",
      nav_wishlist: "Favorites",
      nav_profile: "Profile",
      search_placeholder: "Search products...",
      cat_all: "All Products",
      cat_smartphones: "Smartphones",
      cat_laptops: "Laptops",
      cat_audio: "Headphones & Audio",
      cat_watches: "Smart Watches",
      cat_accessories: "Accessories",
      weekly_discounts: "Weekly Deals",
      see_all: "See all",
      popular_products: "Popular Products",
      search_results: "Search Results",
      filter: "Filter",
      filter_title: "Sort & Filter",
      sort_default: "Default (Channel order)",
      sort_popular: "Most Popular",
      sort_price_asc: "Price: Low to High ($)",
      sort_price_desc: "Price: High to Low ($)",
      sort_newest: "Newest Arrivals",
      apply: "Apply",
      add_to_cart: "To Cart",
      buy_now: "To Cart",
      go_to_order: "To Order",
      filter_price_title: "Filter by Price",
      sort_title: "Sort Order",
      price_dan: "From",
      price_gacha: "To",
      price_range_all: "All prices",
      view_in_channel: "In Channel",
      adding: "Adding...",
      added: "Added!",
      clear: "Clear",
      checkout: "Proceed to Checkout",
      subtotal: "Products total:",
      total: "Grand total:",
      price_label: "Price:",
      back: "Back",
      empty_title: "No products found",
      empty_desc: "No items match your search or selected filter.",
      reset_filters: "Reset filters",
      cart_empty_title: "Your cart is empty",
      cart_empty_desc: "You haven't added any products to your cart yet.",
      wishlist_empty_title: "Favorites is empty",
      wishlist_empty_desc: "Tap the heart on any product to save it here.",
      start_shopping: "Browse Products",
      cart_cleared: "Cart has been cleared",
      app_settings: "App Settings",
      theme_label: "Dark / Light Mode",
      theme_dark_active: "Dark Mode Active",
      theme_light_active: "Light Mode Active",
      app_language: "Language",
      select_language: "Language:",
      support_title: "Contact & Support",
      tg_channel: "Official Telegram Channel",
      tg_manager: "Contact Manager (Order)",
      phone_call: "Phone Call",
      guarantee_title: "DEMOSTORE GUARANTEE",
      guarantee_desc: "All Apple devices are delivered brand new and sealed. Express delivery across Tashkent within 2 hours, regions within 1 day.",
      work_hours: "Working hours: Daily 09:00 to 22:00",
      original_apple: "100% Genuine",
      customer_badge: "DemoStore Customer",
      catalog_title: "Catalog",
      catalog_subtitle: "Select a category or browse all devices",
      wishlist_title: "Favorites",
      profile_title: "Profile & Support",
      profile_subtitle: "Personal account and help center",
      cart_title: "Shopping Cart",
      items_suffix: "items",
      saved_suffix: "saved items"
    }
  };

  // Keshdan dastlabki mahsulotlar va dollar kursini o'qish (0ms ochilish)
  let cachedInitialProducts = [];
  try {
    const raw = localStorage.getItem('demostore_cached_products');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) cachedInitialProducts = parsed;
    }
  } catch (e) {}

  let cachedInitialRate = 12850;
  try {
    const r = parseFloat(localStorage.getItem('demostore_cached_usd_rate'));
    if (r && !isNaN(r) && r > 1000) cachedInitialRate = r;
  } catch (e) {}

  // Holat (State)
  const state = {
    lang: localStorage.getItem('demostore_lang') || 'uz',
    currentUsdRate: cachedInitialRate,
    selectedCategory: 0,
    selectedSort: 'default',
    searchQuery: '',
    searchCurrencyMode: 'ALL', // 'ALL', 'USD', 'UZS'
    priceFilter: {
      currency: 'USD', // 'USD' yoki 'UZS'
      min: null,
      max: null
    },
    catalogPriceFilter: {
      min: null,
      max: null
    },
    products: cachedInitialProducts,
    isLoading: false,
    selectedProduct: null,
    wishlist: new Set(),
    cart: {}, // { [productId]: { product, qty } }
    currentTab: 'home', // 'home', 'catalog', 'cart', 'wishlist', 'profile', 'product-detail'
    previousTab: 'home',
    savedScroll: {} // { [tab]: scrollY }
  };

  function t(key) {
    const lang = state.lang || 'uz';
    return I18N[lang]?.[key] || I18N.uz[key] || key;
  }

  // LocalStorage dan Wishlist va Savatni o'qish
  try {
    const savedWish = JSON.parse(localStorage.getItem('demostore_wishlist') || '[]');
    state.wishlist = new Set(savedWish);
  } catch (e) {}

  try {
    const savedCart = JSON.parse(localStorage.getItem('demostore_cart') || '{}');
    state.cart = savedCart;
  } catch (e) {}

  // ==========================================================================
  // DOM ELEMENTLARI
  // ==========================================================================
  // 1. Asosiy Bo'limlar (App Sections)
  const sections = {
    home: document.getElementById('sectionHome'),
    catalog: document.getElementById('sectionCatalog'),
    cart: document.getElementById('sectionCart'),
    wishlist: document.getElementById('sectionWishlist'),
    profile: document.getElementById('sectionProfile'),
    'product-detail': document.getElementById('sectionProductDetail')
  };

  const mobileDockEl = document.getElementById('mobileDock');
  const dockItems = document.querySelectorAll('.dock-item');

  // Header elementlari
  const backdropEl = document.getElementById('drawerBackdrop');
  const leftDrawerEl = document.getElementById('leftNavDrawer');
  const bottomFilterEl = document.getElementById('bottomFilterDrawer');
  const btnOpenMenuEl = document.getElementById('btnOpenMenu');
  const btnCloseMenuEl = document.getElementById('btnCloseMenu');
  const btnOpenFilterEl = document.getElementById('btnOpenFilter');
  const btnCloseFilterEl = document.getElementById('btnCloseFilter');
  const btnApplyFilterEl = document.getElementById('btnApplyFilter');
  const btnResetFilterEl = document.getElementById('btnResetFilter');
  const filterCurrencySwitcherEl = document.getElementById('filterCurrencySwitcher');
  const filterPriceMinEl = document.getElementById('filterPriceMin');
  const filterPriceMaxEl = document.getElementById('filterPriceMax');
  const filterPriceHintEl = document.getElementById('filterPriceHint');
  const filterQuickChipsEl = document.getElementById('filterQuickChips');
  const pricePrefixMinEl = document.getElementById('pricePrefixMin');
  const pricePrefixMaxEl = document.getElementById('pricePrefixMax');
  const activeFilterBarEl = document.getElementById('activeFilterBar');
  const activeFilterTextEl = document.getElementById('activeFilterText');
  const btnRemoveActiveFilterEl = document.getElementById('btnRemoveActiveFilter');
  const catalogActiveFilterBarEl = document.getElementById('catalogActiveFilterBar');
  const catalogActiveFilterTextEl = document.getElementById('catalogActiveFilterText');
  const btnRemoveCatalogActiveFilterEl = document.getElementById('btnRemoveCatalogActiveFilter');
  const btnToggleThemeEl = document.getElementById('btnToggleTheme');
  const btnHeaderCartEl = document.getElementById('btnHeaderCart');
  const headerCartBadgeEl = document.getElementById('headerCartBadge');
  const dockCartBadgeEl = document.getElementById('dockCartBadge');
  const dockWishBadgeEl = document.getElementById('dockWishBadge');
  const searchInputEl = document.getElementById('searchInput');
  const clearSearchBtnEl = document.getElementById('clearSearchBtn');
  const logoBtnEl = document.getElementById('logoBtn');
  const toastEl = document.getElementById('toast');
  const toastMsgEl = document.getElementById('toastMsg');

  // Til boshqaruvi elementlari
  const btnLangSwitchEl = document.getElementById('btnLangSwitch');
  const currentLangLabelEl = document.getElementById('currentLangLabel');
  const currentProfileLangLabelEl = document.getElementById('currentProfileLangLabel');
  const drawerLangChips = document.querySelectorAll('.drawer-lang-selector .lang-chip');
  const profileLangBtns = document.querySelectorAll('.profile-lang-chips .profile-lang-btn');

  // Hafta chegirmalari slayderi elementlari
  const discountsSliderSectionEl = document.getElementById('discountsSliderSection');
  const dealsTitleGroupEl = document.getElementById('dealsTitleGroup');
  const btnDiscountsSeeAllEl = document.getElementById('btnDiscountsSeeAll');
  const discountsTrackEl = document.getElementById('discountsTrack');

  // Bosh Sahifa elementlari
  const sectionTitleEl = document.getElementById('sectionTitle');
  const resultsCountEl = document.getElementById('resultsCount');
  const productsGridEl = document.getElementById('productsGrid');
  const emptyStateEl = document.getElementById('emptyState');
  const resetFiltersBtnEl = document.getElementById('resetFiltersBtn');

  // Katalog elementlari
  const catalogCategorySliderEl = document.getElementById('catalogCategorySlider');
  const catalogSectionTitleEl = document.getElementById('catalogSectionTitle');
  const catalogResultsCountEl = document.getElementById('catalogResultsCount');
  const catalogProductsGridEl = document.getElementById('catalogProductsGrid');

  // Savat elementlari
  const cartSectionSubtitleEl = document.getElementById('cartSectionSubtitle');
  const btnClearCartEl = document.getElementById('btnClearCart');
  const cartSectionContentEl = document.getElementById('cartSectionContent');
  const cartSectionItemsListEl = document.getElementById('cartSectionItemsList');
  const cartSubtotalPriceEl = document.getElementById('cartSubtotalPrice');
  const cartFinalTotalPriceEl = document.getElementById('cartFinalTotalPrice');
  const btnCheckoutSectionEl = document.getElementById('btnCheckoutSection');
  const cartSectionEmptyEl = document.getElementById('cartSectionEmpty');
  const btnStartShoppingEl = document.getElementById('btnStartShopping');

  // Sevimlilar elementlari
  const wishlistSectionSubtitleEl = document.getElementById('wishlistSectionSubtitle');
  const wishlistProductsGridEl = document.getElementById('wishlistProductsGrid');
  const wishlistSectionEmptyEl = document.getElementById('wishlistSectionEmpty');
  const btnBrowseProductsEl = document.getElementById('btnBrowseProducts');

  // Profil elementlari
  const profileAvatarEl = document.getElementById('profileAvatar');
  const profileUserNameEl = document.getElementById('profileUserName');
  const profileUserHandleEl = document.getElementById('profileUserHandle');
  const statCartCountEl = document.getElementById('statCartCount');
  const statWishCountEl = document.getElementById('statWishCount');
  const rowToggleThemeEl = document.getElementById('rowToggleTheme');
  const currentThemeLabelEl = document.getElementById('currentThemeLabel');
  const statCartBoxEl = document.getElementById('statCartBox');
  const statWishBoxEl = document.getElementById('statWishBox');

  // Mahsulot batafsil elementlari
  const pdBackBtnEl = document.getElementById('pdBackBtn');
  const pdWishlistBtnEl = document.getElementById('pdWishlistBtn');
  const pdBodyContentEl = document.getElementById('pdBodyContent');
  const pdBottomPriceEl = document.getElementById('pdBottomPrice');
  const pdBottomPriceUzsEl = document.getElementById('pdBottomPriceUzs');
  const pdAddToCartBtnEl = document.getElementById('pdAddToCartBtn');
  const pdBtnTextEl = document.getElementById('pdBtnText');
  const pdChannelIconBtnEl = document.getElementById('pdChannelIconBtn');

  // To'liq ekranda rasm ko'rish (Lightbox) elementlari
  const fsViewerEl = document.getElementById('fullscreenImageViewer');
  const fsViewerTrackEl = document.getElementById('fsViewerTrack');
  const fsViewerCounterEl = document.getElementById('fsViewerCounter');
  const fsViewerCloseBtnEl = document.getElementById('fsViewerCloseBtn');
  const fsViewerDotsEl = document.getElementById('fsViewerDots');

  // ==========================================================================
  // TILNI QO'LLASH (APPLY LANGUAGE DYNAMICALLY)
  // ==========================================================================
  function applyLanguage(lang) {
    if (!I18N[lang]) lang = 'uz';
    state.lang = lang;
    localStorage.setItem('demostore_lang', lang);

    // Header til yorlig'i
    if (currentLangLabelEl) currentLangLabelEl.textContent = I18N[lang].lang_code;

    // Profil sozlamalari til yorlig'i
    if (currentProfileLangLabelEl) currentProfileLangLabelEl.textContent = I18N[lang].lang_name;

    // Yon menyu chiplari
    document.querySelectorAll('.drawer-lang-selector .lang-chip').forEach(chip => {
      chip.classList.toggle('active', chip.dataset.lang === lang);
    });

    // Profil bo'limidagi chiplar
    document.querySelectorAll('.profile-lang-chips .profile-lang-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });

    // Qidiruv input placeholderi
    if (searchInputEl) searchInputEl.placeholder = t('search_placeholder');

    // Barcha data-i18n elementlarini matn bilan to'ldirish
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const k = el.dataset.i18n;
      if (k && I18N[lang][k]) {
        el.textContent = I18N[lang][k];
      }
    });

    // Mobil dock tugmalari yozuvlari
    const dockHome = document.querySelector('#dockHome span');
    if (dockHome) dockHome.textContent = t('nav_home');
    const dockCatalog = document.querySelector('#dockCatalog span');
    if (dockCatalog) dockCatalog.textContent = t('nav_catalog');
    const dockCart = document.querySelector('#dockCart span');
    if (dockCart) dockCart.textContent = t('nav_cart');
    const dockWishlist = document.querySelector('#dockWishlist span');
    if (dockWishlist) dockWishlist.textContent = t('nav_wishlist');
    const dockProfile = document.querySelector('#dockProfile span');
    if (dockProfile) dockProfile.textContent = t('nav_profile');

    // Mahsulot batafsil va barcha kartochka tugmalari yozuvlarini sinxronlash
    syncAllProductButtons();

    // Agar mahsulotlar mavjud bo'lsa, joriy bo'limni yangilash
    if (state.products && state.products.length > 0) {
      renderDiscountsSlider();
      if (state.currentTab === 'catalog') renderCatalog();
      else if (state.currentTab === 'cart') renderCartSection();
      else if (state.currentTab === 'wishlist') renderWishlistSection();
      else if (state.currentTab === 'profile') renderProfileSection();
      else renderProducts(true);
    }
  }

  // ==========================================================================
  // HAFTA CHEGIRMALARI SLAYDERINI CHIZISH (BLACK STORE USLUBI)
  // ==========================================================================
  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  const FALLBACK_IMAGE_URL = '/static/apple_3d_logo.png';

  function getProductImageUrl(prod) {
    if (!prod) return FALLBACK_IMAGE_URL;
    // 1. Agar to'g'ridan-to'g'ri Telegram CDN yoki tashqi havola bo'lsa (https://...)
    if (prod.image_url && (String(prod.image_url).startsWith('http://') || String(prod.image_url).startsWith('https://'))) {
      return prod.image_url;
    }
    // 2. Agar Telegram photo_file_id bo'lsa
    if (prod.photo_file_id) return '/api/photo/' + prod.photo_file_id;
    // 3. Agar mavjud image_url bo'lsa
    if (prod.image_url && String(prod.image_url).trim()) return prod.image_url;
    if (prod.image && String(prod.image).trim()) return prod.image;
    return FALLBACK_IMAGE_URL;
  }

  // ==========================================================================
  // XARID VA BUYURTMAGA O'TISH TUGMALARI (SOTIB OLISH -> BUYURTMAGA)
  // ==========================================================================
  function getCartButtonHtml(pid) {
    const inCart = Boolean(state.cart && state.cart[pid]);
    if (inCart) {
      return `
        <button class="btn-buy btn-add-cart btn-goto-order btn-bounce" data-id="${pid}" data-haptic="medium">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          <span>${t('go_to_order')}</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
        </button>
      `;
    }
    return `
      <button class="btn-buy btn-add-cart btn-bounce" data-id="${pid}" data-haptic="medium">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
        <span>${t('buy_now')}</span>
      </button>
    `;
  }

  function getDealCartButtonHtml(pid) {
    const inCart = Boolean(state.cart && state.cart[pid]);
    if (inCart) {
      return `
        <button class="deal-cart-btn btn-buy btn-goto-order btn-bounce" data-id="${pid}" data-haptic="medium">
          <span class="deal-cart-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </span>
          <span>${t('go_to_order')}</span>
        </button>
      `;
    }
    return `
      <button class="deal-cart-btn btn-buy btn-bounce" data-id="${pid}" data-haptic="medium">
        <span class="deal-cart-icon">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
        </span>
        <span>${t('buy_now')}</span>
      </button>
    `;
  }

  function updatePdCartButton(inCart) {
    if (!pdAddToCartBtnEl) return;
    if (pdAddToCartBtnEl.dataset.animating === 'true') return;
    if (inCart) {
      pdAddToCartBtnEl.classList.add('btn-goto-order');
      pdAddToCartBtnEl.innerHTML = `
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span id="pdBtnText" class="btn-order-text">${t('go_to_order')}</span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      `;
    } else {
      pdAddToCartBtnEl.classList.remove('btn-goto-order');
      pdAddToCartBtnEl.innerHTML = `
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
        <span id="pdBtnText">${t('buy_now')}</span>
      `;
    }
  }

  function syncAllProductButtons() {
    document.querySelectorAll('.btn-add-cart[data-id]').forEach(btn => {
      if (btn.dataset.animating === 'true') return;
      const pid = parseInt(btn.dataset.id, 10);
      const inCart = Boolean(state.cart && state.cart[pid]);
      if (inCart) {
        btn.classList.add('btn-goto-order');
        btn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          <span class="btn-order-text">${t('go_to_order')}</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
        `;
      } else {
        btn.classList.remove('btn-goto-order');
        btn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
          <span>${t('buy_now')}</span>
        `;
      }
    });

    document.querySelectorAll('.deal-cart-btn[data-id]').forEach(btn => {
      if (btn.dataset.animating === 'true') return;
      const pid = parseInt(btn.dataset.id, 10);
      const inCart = Boolean(state.cart && state.cart[pid]);
      if (inCart) {
        btn.classList.add('btn-goto-order');
        btn.innerHTML = `
          <span class="deal-cart-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </span>
          <span class="btn-order-text">${t('go_to_order')}</span>
        `;
      } else {
        btn.classList.remove('btn-goto-order');
        btn.innerHTML = `
          <span class="deal-cart-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
          </span>
          <span>${t('buy_now')}</span>
        `;
      }
    });

    if (state.selectedProduct && pdAddToCartBtnEl && pdAddToCartBtnEl.dataset.animating !== 'true') {
      updatePdCartButton(Boolean(state.cart && state.cart[state.selectedProduct.id]));
    }
  }

  function renderDiscountsSlider() {
    if (!discountsTrackEl) return;

    // Qidiruv faol bo'lsa, hafta chegirmalarini ko'rsatmaslik
    const isSearching = Boolean(state.searchQuery && state.searchQuery.trim().length > 0);
    if (isSearching) {
      if (discountsSliderSectionEl) discountsSliderSectionEl.classList.add('hidden');
      return;
    } else {
      if (discountsSliderSectionEl) discountsSliderSectionEl.classList.remove('hidden');
    }

    if (!state.products || state.products.length === 0) return;

    // 1. FAQAT va FAQAT admin tomonidan 'Hafta chegirmalari'ga biriktirilgan (is_discount === 1) tovarlar chiqadi!
    // Oddiy 'Ha, joylansin' bilan tasdiqlangan tovarlar hech qachon bu yerga kirmaydi!
    let discountItems = state.products.filter(p => Number(p.is_discount) === 1);
    if (discountItems.length === 0) {
      if (discountsSliderSectionEl) discountsSliderSectionEl.classList.add('hidden');
      return;
    }
    // Hafta chegirmalari ham toifalar bo'yicha aralash (interleaved) tartibda ko'rsatiladi
    discountItems = getMixedCatalogProducts(discountItems);
    const discountRates = [15, 20, 12, 18, 25, 16, 22, 10];

    let html = '';
    discountItems.forEach((p, idx) => {
      const rate = discountRates[idx % discountRates.length];
      const oldPrice = Math.round(p.price / (1 - rate / 100));
      const isFav = state.wishlist.has(p.id);

      html += `
        <div class="deal-card" data-id="${p.id}">
          <div class="deal-image-box">
            <span class="deal-discount-badge">↓ -${rate}%</span>
            <button class="deal-wishlist-btn ${isFav ? 'active' : ''}" data-id="${p.id}" aria-label="${t('nav_wishlist')}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="${isFav ? '#ef4444' : 'none'}" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="deal-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="deal-content">
            <div class="deal-price-block">
              ${p.currency === 'UZS' && p.price_uzs ? `
                <div class="deal-current-price">
                  ${formatUzsAmount(p.price_uzs)}
                </div>
              ` : `
                <div class="deal-current-price">
                  ${formatPrice(p.price)}
                  <span class="deal-price-uzs">≈ ${formatPriceUzs(p.price)}</span>
                </div>
                <div class="deal-old-price-row">
                  <span class="deal-old-price">${formatPrice(oldPrice)}</span>
                  <span class="deal-drop-tag">-${rate}%</span>
                </div>
              `}
            </div>
            <h3 class="deal-title" title="${escapeHtml(getCleanCardTitle(p.name))}">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            <div class="deal-footer-action">
              ${getDealCartButtonHtml(p.id)}
            </div>
          </div>
        </div>
      `;
    });

    discountsTrackEl.innerHTML = html;
    setupDealsSliderSwipe();
  }

  // Hafta chegirmalari trek hodisasi (Event Delegation)
  discountsTrackEl?.addEventListener('click', (e) => {
    const card = e.target.closest('.deal-card');
    if (!card) return;
    const pid = parseInt(card.dataset.id, 10);
    const prod = state.products.find(x => x.id === pid);
    if (!prod) return;

    const wishlistBtn = e.target.closest('.deal-wishlist-btn');
    if (wishlistBtn) {
      e.stopPropagation();
      toggleWishlist(prod, e);
      return;
    }

    const cartBtn = e.target.closest('.deal-cart-btn');
    if (cartBtn) {
      e.stopPropagation();
      if (cartBtn.classList.contains('btn-goto-order') || (state.cart && state.cart[pid])) {
        switchTab('cart');
        return;
      }
      handleAddToCart(prod, cartBtn);
      return;
    }

    openProductModal(prod);
  });

  // Sichqoncha va sensor bilan erkin surish (Touch & Mouse Drag Swipe)
  function setupDealsSliderSwipe() {
    if (!discountsTrackEl || discountsTrackEl.dataset.dragInit === 'true') return;
    discountsTrackEl.dataset.dragInit = 'true';

    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;

    discountsTrackEl.addEventListener('mousedown', (e) => {
      isDown = true;
      discountsTrackEl.classList.add('is-dragging');
      startX = e.pageX - discountsTrackEl.offsetLeft;
      scrollLeft = discountsTrackEl.scrollLeft;
    });

    const stopDrag = () => {
      if (!isDown) return;
      isDown = false;
      discountsTrackEl.classList.remove('is-dragging');
    };

    discountsTrackEl.addEventListener('mouseleave', stopDrag);
    discountsTrackEl.addEventListener('mouseup', stopDrag);
    discountsTrackEl.addEventListener('mousemove', (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - discountsTrackEl.offsetLeft;
      const walk = (x - startX) * 1.5;
      discountsTrackEl.scrollLeft = scrollLeft - walk;
    });
  }

  // ==========================================================================
  // 2. BO'LIMLARNI BOSHQARISH VA ROUTING (NAV HISTORY, BACK BUTTON & IPHONE SWIPE)
  // ==========================================================================
  function isAnyDrawerOpen() {
    return (
      (leftDrawerEl && leftDrawerEl.classList.contains('active')) ||
      (bottomFilterEl && bottomFilterEl.classList.contains('active')) ||
      (backdropEl && backdropEl.classList.contains('active'))
    );
  }

  function updateBackButtons() {
    // Mahsulot batafsil yoki rasm fullscreen lightbox ochilganda Telegram BackButton ko'rsatiladi
    if (tg?.BackButton) {
      try {
        const isFsOpen = fsViewerEl && !fsViewerEl.classList.contains('hidden');
        if (state.currentTab === 'product-detail' || isFsOpen) {
          tg.BackButton.show();
        } else {
          tg.BackButton.hide();
        }
      } catch (e) {}
    }
  }

  function goBack() {
    triggerHaptic('light');

    // 0. Agar rasm fullscreen lightbox ochiq bo'lsa, avval uni yopamiz
    if (fsViewerEl && !fsViewerEl.classList.contains('hidden')) {
      closeFullscreenGallery();
      return;
    }

    // 1. Agar yon menyu yoki filtr ochiq bo'lsa, avval uni yopamiz
    if (isAnyDrawerOpen()) {
      closeAllDrawers();
      return;
    }

    // 2. Agar mahsulot batafsil sahifasida bo'lsa:
    // Qaysi bo'limdan (Catalog, Wishlist, Cart, Home) ochilgan bo'lsa, aniq o'sha bo'limga va o'sha skroll joyiga qaytadi
    if (state.currentTab === 'product-detail') {
      const returnTab = (state.previousTab && state.previousTab !== 'product-detail') ? state.previousTab : 'home';
      switchTab(returnTab, null, false, true);
      return;
    }

    // 3. Agar qidiruv yoki filtr aktiv bo'lsa -> tozalash
    if (state.searchQuery || state.selectedCategory !== 0 || (state.selectedSort && state.selectedSort !== 'default')) {
      resetHomeView();
      return;
    }

    // 4. Agar foydalanuvchi Bosh sahifada (home) bo'lmasa, Bosh sahifaga qaytish (1 qadam)
    if (state.currentTab !== 'home') {
      switchTab('home', null, false);
      return;
    }

    // 5. Agar allaqachon Bosh sahifada (home) turgan bo'lsa:
    // FOYDALANUVCHI TALABI: Mini ilovadan chiqib ketish MUTLAQO TAQIQLANGAN!
    // tg.close() chaqirilmaydi. Bosh sahifa yuqorisiga silliq scroll qiladi.
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function resetHomeView() {
    const hadFilterOrSearch = Boolean(state.searchQuery || state.selectedCategory !== 0 || (state.selectedSort && state.selectedSort !== 'default'));
    state.searchQuery = '';
    state.selectedCategory = 0;
    state.selectedSort = 'default';

    if (searchInputEl) {
      searchInputEl.value = '';
      searchInputEl.blur();
    }
    clearSearchBtnEl?.classList.add('hidden');
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.remove('hidden');
    }
    if (sectionTitleEl) {
      sectionTitleEl.textContent = t('popular_products');
    }
    document.body.classList.remove('search-focused', 'keyboard-open');
    mobileDockEl?.classList.remove('dock-hidden-keyboard');

    catalogCategorySliderEl?.querySelectorAll('.category-pill').forEach(p => {
      p.classList.toggle('active', p.dataset.category === '0');
    });

    if (hadFilterOrSearch) {
      const cached = localStorage.getItem('demostore_cached_products');
      if (cached) {
        try {
          state.products = JSON.parse(cached);
          renderProducts(true);
          renderDiscountsSlider();
        } catch (e) {}
      }
      loadProducts(true);
    } else {
      renderProducts(true);
      renderDiscountsSlider();
    }
  }

  function switchTab(tabKey, categoryId = null, pushState = true, restoreScroll = false) {
    if (!sections[tabKey]) return;
    triggerHaptic('light');
    closeAllDrawers();

    const fromTab = state.currentTab;

    // Agar mahsulot batafsilga o'tayotgan bo'lsa, qaysi bo'limdan kelganini va skrollini eslab qolamiz
    if (tabKey === 'product-detail') {
      if (fromTab !== 'product-detail') {
        state.previousTab = fromTab;
        state.savedScroll[fromTab] = window.scrollY || window.pageYOffset || 0;
      }
    } else if (fromTab !== 'product-detail') {
      state.previousTab = fromTab;
    }

    state.currentTab = tabKey;

    if (pushState) {
      if (tabKey === 'product-detail') {
        try {
          history.pushState({ tab: 'product-detail', from: state.previousTab }, '', '#product-detail');
        } catch (e) {}
      } else {
        // Asosiy bo'limlar (Home, Catalog, Cart, Wishlist, Profile) uchun replaceState ishlatamiz.
        // Bu orqali foydalanuvchi mini ilovadan chiqish uchun 10 marta orqaga bosib yurmaydi!
        try {
          history.replaceState({ tab: tabKey, categoryId }, '', '#' + tabKey);
        } catch (e) {}
      }
    }

    // Pastki dockdagi faol tugmani belgilash
    dockItems.forEach(d => {
      d.classList.toggle('active', d.dataset.tab === tabKey);
    });

    // Bo'limlarni almashtirish
    Object.keys(sections).forEach(key => {
      const sec = sections[key];
      if (sec) {
        if (key === tabKey) {
          sec.classList.remove('hidden');
          sec.classList.add('active');
        } else {
          sec.classList.remove('active');
          sec.classList.add('hidden');
        }
      }
    });

    // Header va Dock holatini boshqarish
    const mobileHeaderEl = document.getElementById('mobileHeader');
    const mainContentEl = document.getElementById('mainContent');
    if (tabKey === 'product-detail') {
      mobileHeaderEl?.classList.add('hidden');
      mobileDockEl?.classList.add('hidden');
      if (mainContentEl) mainContentEl.style.paddingTop = 'var(--app-safe-top, 12px)';
    } else {
      mobileHeaderEl?.classList.remove('hidden');
      mobileDockEl?.classList.remove('hidden');
      if (mainContentEl) mainContentEl.style.paddingTop = '';
      setTimeout(updateHeaderHeight, 10);
    }

    updateBackButtons();

    // Har bir bo'limga mos render
    if (tabKey === 'home') {
      if (fromTab !== 'product-detail') {
        resetHomeView();
      }
    } else if (tabKey === 'catalog') {
      if (categoryId !== null) {
        state.selectedCategory = categoryId;
      }
      catalogCategorySliderEl?.querySelectorAll('.category-pill').forEach(pill => {
        const isActive = parseInt(pill.dataset.category, 10) === state.selectedCategory;
        pill.classList.toggle('active', isActive);
        // Faol pill ko'rinadigan joyga scroll qilsin
        if (isActive) {
          setTimeout(() => pill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }), 80);
        }
      });
      renderCatalog();
    } else if (tabKey === 'cart') {
      renderCartSection();
    } else if (tabKey === 'wishlist') {
      renderWishlistSection();
    } else if (tabKey === 'profile') {
      renderProfileSection();
    }

    // Skroll holatini boshqarish: yangi bo'limga (ayniqsa Cart/Savatga) o'tganda TEPADAN boshlansin!
    if (restoreScroll) {
      const targetY = state.savedScroll[tabKey] || 0;
      setTimeout(() => {
        window.scrollTo({ top: targetY, behavior: 'instant' });
        const mc = document.getElementById('mainContent');
        if (mc) mc.scrollTop = targetY;
      }, 15);
    } else {
      window.scrollTo({ top: 0, behavior: 'instant' });
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      const mc = document.getElementById('mainContent');
      if (mc) mc.scrollTop = 0;
      const sec = sections[tabKey];
      if (sec) sec.scrollTop = 0;
    }
  }

  // Telegram native BackButton
  if (tg?.BackButton) {
    try {
      tg.BackButton.onClick(goBack);
    } catch (e) {}
  }

  // Brauzer / Android apparat tugmasi / iOS Safari / MacBook trackpad popstate
  try {
    history.pushState({ app: 'demostore' }, '', location.href);
  } catch (e) {}

  window.addEventListener('popstate', (e) => {
    // Mini ilovadan trackpad yoki brauzer orqaga tugmasi orqali tasodifiy chiqib ketmaslik uchun tarixni ushlab turamiz
    try {
      history.pushState({ app: 'demostore' }, '', location.href);
    } catch (err) {}
    goBack();
  });

  // Klaviatura Escape tugmasi
  // ==========================================================================
  // UNIVERSAL EDGE EXIT & SWIPE-TO-BACK (Barcha qurilmalar uchun: iPhone, Android, MacBook Trackpad)
  // ==========================================================================

  // 1. Klaviatura va sichqoncha qo'shimcha tugmalari
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (fsViewerEl && !fsViewerEl.classList.contains('hidden')) {
        closeFullscreenGallery();
        return;
      }
      goBack();
      return;
    }
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    // Mac Cmd+[ yoki Windows/Linux Alt+LeftArrow
    if ((e.metaKey && e.key === '[') || (e.altKey && e.key === 'ArrowLeft')) {
      e.preventDefault();
      goBack();
    }
  });

  window.addEventListener('mouseup', (e) => {
    // Sichqonchaning "Orqaga" (Back - button 3) tugmasi
    if (e.button === 3) {
      e.preventDefault();
      goBack();
    }
  });

  // 2. Sensor ekranlar (iPhone, iPad, Android) chetidan surish (Touch Edge-Swipe)
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;
  let isEdgeSwipeGesture = false;

  window.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1) return;
    // Agar fullscreen rasm tomoshasi ochiq bo'lsa, chetdan surish to'xtatiladi
    if (fsViewerEl && !fsViewerEl.classList.contains('hidden')) return;

    // Faqat orqaga qaytadigan sahifa yoki ochiq menyu bo'lsa
    const canGoBack = state.currentTab !== 'home' || isAnyDrawerOpen() || Boolean(state.searchQuery || state.selectedCategory !== 0);
    if (!canGoBack) return;

    const touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    isEdgeSwipeGesture = false;

    // Chetdan boshlanish chegarasi:
    // Mahsulot batafsil yoki ochiq menyuda kengroq (ekranning 35% gacha), odatiy holatda chap chekka (<= 80px)
    const isModalOrDetail = state.currentTab === 'product-detail' || isAnyDrawerOpen();
    const edgeLimit = isModalOrDetail ? Math.min(window.innerWidth * 0.35, 140) : 80;

    if (touchStartX <= edgeLimit) {
      isEdgeSwipeGesture = true;
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (!isEdgeSwipeGesture) return;
    const touch = e.touches[0];
    const diffX = touch.clientX - touchStartX;
    const diffY = Math.abs(touch.clientY - touchStartY);

    // Agar vertikal skroll ustun bo'lsa, jestni to'xtatamiz
    if (diffY > 28 && diffY > diffX * 1.15) {
      isEdgeSwipeGesture = false;
    }
  }, { passive: true });

  window.addEventListener('touchend', (e) => {
    if (!isEdgeSwipeGesture) return;
    const touch = e.changedTouches[0];
    const diffX = touch.clientX - touchStartX;
    const diffY = Math.abs(touch.clientY - touchStartY);
    const elapsed = Date.now() - touchStartTime;

    isEdgeSwipeGesture = false;

    // Kamida 42px o'ngga surilsa va gorizontal harakat bo'lsa
    if (diffX >= 42 && diffX > diffY * 1.05 && elapsed < 650) {
      goBack();
    }
  }, { passive: true });

  // ==========================================================================
  // 3. MIKRO-ANIMATSIYALAR TIZIMI (PREMIUM MICRO-ANIMATIONS)
  // ==========================================================================
  // 1. Savat hisoblagichi (Badge) va pastki dock animatsiyasi
  // DIQQAT: Tepadagi savat (#btnHeaderCart) foydalanuvchi talabiga binoan MUTLAQO QIMIRLAMAYDI!
  function triggerCartJump() {
    const bottomCartItem = document.querySelector('.mobile-dock .dock-item[data-tab="cart"]');
    const bottomBadge = bottomCartItem?.querySelector('.dock-badge');

    if (bottomCartItem) {
      bottomCartItem.classList.remove('bottom-cart-jump-anim');
      void bottomCartItem.offsetWidth; // DOM reflow
      bottomCartItem.classList.add('bottom-cart-jump-anim');
      setTimeout(() => {
        bottomCartItem.classList.remove('bottom-cart-jump-anim');
      }, 700);
    }

    if (bottomBadge) {
      bottomBadge.classList.remove('badge-pop-anim');
      void bottomBadge.offsetWidth;
      bottomBadge.classList.add('badge-pop-anim');
      setTimeout(() => {
        bottomBadge.classList.remove('badge-pop-anim');
      }, 600);
    }
  }

  // 2. Savatga qo'shish tugmasining "Buyurtmaga" holatiga jonli ko'p bosqichli o'tish animatsiyasi
  function animateCartButton(btn) {
    if (!btn) return;
    btn.dataset.animating = 'true';

    // 1-bosqich: Aylanuvchi yuklanish spinneri (Spinner + "Qo'shilmoqda...")
    btn.classList.remove('is-success', 'btn-goto-order');
    const addingText = t('adding') || "Qo'shilmoqda...";
    btn.innerHTML = `<span class="btn-spinner"></span><span>${addingText}</span>`;

    // Mayin bosilish hissi
    btn.style.transform = 'scale(0.96)';
    btn.style.transition = 'transform 0.08s cubic-bezier(0.2, 0, 0, 1)';
    setTimeout(() => {
      btn.style.transform = 'scale(1)';
      btn.style.transition = 'transform 0.2s cubic-bezier(0.25, 1.4, 0.5, 1)';
    }, 80);

    // 2-bosqich: 280ms o'tgach, Yashil ptichka sakrashi (Checkmark Pop + "Qo'shildi!")
    // Aynan shu lahzada pastki dockdagi savatcha ham yorqin sariq/oltin nur sochib sakraydi!
    setTimeout(() => {
      btn.classList.add('is-success');
      const addedText = t('added') || "Qo'shildi!";
      btn.innerHTML = `
        <svg class="checkmark-pop-anim" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>${addedText}</span>
      `;
      triggerHaptic('success');
      triggerCartJump(); // Savatcha sariq nur bilan sakraydi!

      // 3-bosqich: "Qo'shildi!" dan so'ng (650ms o'tgach), tugma shaffof qora Apple dizaynidagi "Buyurtmaga" holatiga o'tadi
      setTimeout(() => {
        btn.classList.remove('is-success');
        btn.classList.add('btn-goto-order');

        if (btn.classList.contains('pd-add-btn')) {
          btn.innerHTML = `
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span id="pdBtnText" class="btn-order-text">${t('go_to_order')}</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          `;
        } else if (btn.classList.contains('deal-cart-btn')) {
          btn.innerHTML = `
            <span class="deal-cart-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </span>
            <span class="btn-order-text">${t('go_to_order')}</span>
          `;
        } else {
          btn.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            <span class="btn-order-text">${t('go_to_order')}</span>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
          `;
        }

        btn.style.transform = '';
        btn.style.transition = '';
        btn.dataset.animating = 'false';
        syncAllProductButtons();
      }, 650);
    }, 280);
  }

  // 3. Telegram kanaldagi postni ochish funksiyasi
  function openChannelPost(postUrl, productId) {
    if (!postUrl) return;
    triggerHaptic('light');

    // Bazada statistika (views_count) ni oshirish
    if (productId) {
      try {
        apiFetch(`/api/products/${productId}/click`, { method: 'POST' }).catch(() => {});
      } catch (e) {}
    }

    // Telegram ilovasi ichida to'g'ridan-to'g'ri kanal postiga o'tish
    if (window.Telegram?.WebApp?.openTelegramLink && postUrl.includes('t.me')) {
      window.Telegram.WebApp.openTelegramLink(postUrl);
    } else {
      window.open(postUrl, '_blank');
    }
  }

  // 4. Universal Savatga qo'shish funksiyasi
  function handleAddToCart(product, btn) {
    triggerHaptic('medium');
    const pid = product.id;
    if (state.cart[pid]) {
      state.cart[pid].qty += 1;
    } else {
      state.cart[pid] = { product, qty: 1 };
    }
    saveCart();

    // A) Tugmani ko'p bosqichli jonlantirish (Spinner -> Yashil Qo'shildi! + Savat sakrashi -> Shaffof qora Buyurtmaga)
    if (btn) {
      animateCartButton(btn);
    } else {
      triggerCartJump();
    }
  }

  // ==========================================================================
  // 4. SAVAT (CART) MANTIQI VA BO'LIMI
  // ==========================================================================
  function changeCartQty(pid, delta) {
    triggerHaptic('light');
    if (!state.cart[pid]) return;
    state.cart[pid].qty += delta;
    if (state.cart[pid].qty <= 0) {
      delete state.cart[pid];
    }
    saveCart();
    renderCartSection();
  }

  function saveCart() {
    try {
      localStorage.setItem('demostore_cart', JSON.stringify(state.cart));
    } catch (e) {}
    updateCartBadges();
    syncAllProductButtons();
  }

  function updateCartBadges() {
    const totalCount = Object.values(state.cart).reduce((sum, item) => sum + item.qty, 0);
    if (headerCartBadgeEl) {
      headerCartBadgeEl.textContent = totalCount > 0 ? totalCount.toString() : '';
      headerCartBadgeEl.classList.toggle('hidden', totalCount === 0);
      headerCartBadgeEl.style.display = totalCount > 0 ? 'inline-flex' : 'none';
    }
    if (dockCartBadgeEl) {
      dockCartBadgeEl.textContent = totalCount > 0 ? totalCount.toString() : '';
      dockCartBadgeEl.classList.toggle('hidden', totalCount === 0);
      dockCartBadgeEl.style.display = totalCount > 0 ? 'inline-flex' : 'none';
    }
    if (statCartCountEl) {
      statCartCountEl.textContent = totalCount.toString();
    }
  }

  function renderCartSection() {
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
    const mc = document.getElementById('mainContent');
    if (mc) mc.scrollTop = 0;

    if (!cartSectionContentEl || !cartSectionEmptyEl) return;
    const items = Object.values(state.cart);
    const totalCount = items.reduce((sum, i) => sum + i.qty, 0);

    if (cartSectionSubtitleEl) {
      cartSectionSubtitleEl.textContent = `${totalCount} ta mahsulot tanlandi`;
    }

    if (items.length === 0) {
      cartSectionContentEl.classList.add('hidden');
      cartSectionEmptyEl.classList.remove('hidden');
      btnClearCartEl?.classList.add('hidden');
      return;
    }

    cartSectionEmptyEl.classList.add('hidden');
    cartSectionContentEl.classList.remove('hidden');
    btnClearCartEl?.classList.remove('hidden');

    let total = 0;
    cartSectionItemsListEl.innerHTML = items.map(item => {
      const p = item.product;
      const subtotal = p.price * item.qty;
      total += subtotal;
      const brand = p.name.toLowerCase().includes('macbook') || p.name.toLowerCase().includes('iphone') ? 'APPLE' : 'PREMIUM';

      return `
        <div class="cart-section-item" data-id="${p.id}">
          <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="cart-section-item-img" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          <div class="cart-section-item-info">
            <span class="cart-section-item-brand">${brand}</span>
            <h4 class="cart-section-item-name">${escapeHtml(getCleanCardTitle(p.name))}</h4>
            <div class="cart-section-item-price">
              ${p.currency === 'UZS' && p.price_uzs ? `
                <span class="price-current" style="font-size: 0.95rem; font-weight: 700;">${formatUzsAmount(p.price_uzs)}</span>
                <span class="cart-item-uzs-sub">(${formatUzsAmount(p.price_uzs * item.qty)})</span>
              ` : `
                ${formatPrice(p.price)}
                <span class="cart-item-uzs-sub">(${formatPriceUzs(p.price * item.qty)})</span>
              `}
            </div>
          </div>
          <div class="cart-section-item-actions">
            <button class="cart-delete-item-btn" data-id="${p.id}" aria-label="Oʻchirish">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
              </svg>
            </button>
            <div class="cart-qty-pill">
              <button class="btn-minus" data-id="${p.id}">-</button>
              <span>${item.qty}</span>
              <button class="btn-plus" data-id="${p.id}">+</button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    if (cartSubtotalPriceEl) cartSubtotalPriceEl.innerHTML = `${formatPrice(total)} <small class="cart-total-uzs">(${formatPriceUzs(total)})</small>`;
    if (cartFinalTotalPriceEl) cartFinalTotalPriceEl.innerHTML = `${formatPrice(total)} <small class="cart-total-uzs">(${formatPriceUzs(total)})</small>`;

    // Savatdagi tugmalar hodisalari
    cartSectionItemsListEl.querySelectorAll('.btn-minus').forEach(btn => {
      btn.addEventListener('click', () => changeCartQty(parseInt(btn.dataset.id, 10), -1));
    });
    cartSectionItemsListEl.querySelectorAll('.btn-plus').forEach(btn => {
      btn.addEventListener('click', () => changeCartQty(parseInt(btn.dataset.id, 10), 1));
    });
    cartSectionItemsListEl.querySelectorAll('.cart-delete-item-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const pid = parseInt(btn.dataset.id, 10);
        delete state.cart[pid];
        saveCart();
        renderCartSection();
      });
    });
  }

  // Savatni tozalash tugmasi
  btnClearCartEl?.addEventListener('click', () => {
    triggerHaptic('medium');
    state.cart = {};
    saveCart();
    renderCartSection();
    showToast('Savatingiz tozalandi');
  });

  btnStartShoppingEl?.addEventListener('click', () => {
    switchTab('catalog');
  });

  // Telegram orqali savat buyurtmasini jo'natish
  btnCheckoutSectionEl?.addEventListener('click', () => {
    triggerHaptic('heavy');
    const items = Object.values(state.cart);
    if (items.length === 0) return;

    let total = 0;
    let text = "Assalomu alaykum! Men DemoStore mini-ilovasi orqali quyidagi buyurtmani rasmiylashtirmoqchiman:\n\n";
    items.forEach((item, idx) => {
      const p = item.product;
      const subtotal = p.price * item.qty;
      total += subtotal;
      if (p.currency === 'UZS' && p.price_uzs) {
        text += `${idx + 1}. ${p.name} — ${item.qty} dona x ${formatUzsAmount(p.price_uzs)} = ${formatUzsAmount(p.price_uzs * item.qty)}\n`;
      } else {
        text += `${idx + 1}. ${p.name} — ${item.qty} dona x ${formatPrice(p.price)} = ${formatPrice(subtotal)} (${formatPriceUzs(subtotal)})\n`;
      }
    });
    text += `\nJami summa: ${formatPrice(total)} (${formatPriceUzs(total)})\n`;
    const rateVal = Math.round(state.currentUsdRate || 12850).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    text += `Joriy MB kursi: 1$ = ${rateVal} soʻm\n\nIltimos, yetkazib berish boʻyicha maʼlumot bering.`;

    const encoded = encodeURIComponent(text);
    const tgUrl = `https://t.me/eshmbetov?text=${encoded}`;
    window.open(tgUrl, '_blank');
  });

  // ==========================================================================
  // 5. SEVIMLILAR (WISHLIST) MANTIQI VA BO'LIMI
  // ==========================================================================
  function toggleWishlist(product, e) {
    if (e) e.stopPropagation();
    triggerHaptic('medium');
    const pid = product.id;
    if (state.wishlist.has(pid)) {
      state.wishlist.delete(pid);
    } else {
      state.wishlist.add(pid);
    }
    saveWishlist();

    // Yurakcha tugmasi aktiv bo'lsa pop animatsiyasi ishlaydi
    document.querySelectorAll(`.wishlist-btn[data-id="${pid}"]`).forEach(btn => {
      btn.classList.toggle('active', state.wishlist.has(pid));
    });

    if (state.currentTab === 'wishlist') {
      renderWishlistSection();
    } else {
      renderProducts();
    }
  }

  function saveWishlist() {
    try {
      localStorage.setItem('demostore_wishlist', JSON.stringify(Array.from(state.wishlist)));
    } catch (e) {}
    updateWishlistBadge();
  }

  function updateWishlistBadge() {
    const count = state.wishlist.size;
    if (dockWishBadgeEl) {
      dockWishBadgeEl.textContent = count > 0 ? count.toString() : '';
      dockWishBadgeEl.classList.toggle('hidden', count === 0);
      dockWishBadgeEl.style.display = count > 0 ? 'inline-flex' : 'none';
    }
    if (statWishCountEl) {
      statWishCountEl.textContent = count.toString();
    }
  }

  function renderWishlistSection() {
    if (!wishlistProductsGridEl || !wishlistSectionEmptyEl) return;
    const favProducts = state.products.filter(p => state.wishlist.has(p.id));

    if (wishlistSectionSubtitleEl) {
      wishlistSectionSubtitleEl.textContent = `${favProducts.length} ta saqlangan mahsulot`;
    }

    if (favProducts.length === 0) {
      wishlistProductsGridEl.innerHTML = '';
      wishlistSectionEmptyEl.classList.remove('hidden');
      return;
    }

    wishlistSectionEmptyEl.classList.add('hidden');
    let html = '';
    favProducts.forEach(p => {
      const brand = p.name.toLowerCase().includes('macbook') || p.name.toLowerCase().includes('iphone') ? 'APPLE' : 'PREMIUM';
      html += `
        <article class="product-card" data-id="${p.id}">
          <div class="card-media">
            <button class="wishlist-btn active" data-id="${p.id}" aria-label="Sevimlilar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#ef4444" stroke="#ef4444" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="product-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="card-body">
            <span class="product-brand">${brand}</span>
            <h3 class="product-title">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            ${renderProductPriceBlock(p)}
            <div class="card-actions-stack">
              ${getCartButtonHtml(p.id)}
              ${p.post_url ? `
                <button class="btn-channel-link btn-liquid" data-post-url="${p.post_url}" data-id="${p.id}" data-haptic="light">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m22 2-7 20-4-9-9-4Z"></path>
                    <path d="M22 2 11 13"></path>
                  </svg>
                  <span>Kanaldan koʻrish</span>
                </button>
              ` : '<div class="btn-channel-placeholder"></div>'}
            </div>
          </div>
        </article>
      `;
    });

    wishlistProductsGridEl.innerHTML = html;
  }

  // Wishlist grid hodisasi (Event Delegation)
  wishlistProductsGridEl?.addEventListener('click', (e) => {
    const card = e.target.closest('.product-card');
    if (!card) return;
    const pid = parseInt(card.dataset.id, 10);
    const prod = state.products.find(x => x.id === pid);
    if (!prod) return;

    const wishlistBtn = e.target.closest('.wishlist-btn');
    if (wishlistBtn) {
      e.stopPropagation();
      toggleWishlist(prod, e);
      renderWishlistSection();
      return;
    }

    const addCartBtn = e.target.closest('.btn-add-cart');
    if (addCartBtn) {
      e.stopPropagation();
      if (addCartBtn.classList.contains('btn-goto-order') || (state.cart && state.cart[pid])) {
        switchTab('cart');
        return;
      }
      handleAddToCart(prod, addCartBtn);
      return;
    }

    const channelBtn = e.target.closest('.btn-channel-link');
    if (channelBtn) {
      e.stopPropagation();
      openChannelPost(channelBtn.dataset.postUrl, pid);
      return;
    }

    openProductModal(prod);
  });

  btnBrowseProductsEl?.addEventListener('click', () => {
    switchTab('home');
  });

  // ==========================================================================
  // 6. KATALOG BO'LIMI (CATALOG SECTION)
  // ==========================================================================
  catalogCategorySliderEl?.querySelectorAll('.category-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      triggerHaptic('light');
      const catId = parseInt(pill.dataset.category, 10);
      catalogCategorySliderEl.querySelectorAll('.category-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.selectedCategory = catId;
      // Bosilgan pill ko'rinadigan joyga kelsin (smooth, markazda)
      pill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      renderCatalog();
    });
  });


  // Toifalarni aralash holda chiroyli taqsimlash (Smart Interleaving)
  function getMixedCatalogProducts(list) {
    if (!list || list.length <= 1) return list;
    const buckets = {
      1: [], // Smartfonlar (iPhone)
      2: [], // Noutbuklar (MacBook)
      4: [], // Aqlli soatlar (Apple Watch)
      3: [], // Quloqchinlar va Audio (AirPods)
      5: [], // Aksessuarlar
      other: []
    };
    list.forEach(p => {
      const c = p.category_id;
      if (buckets[c]) {
        buckets[c].push(p);
      } else {
        buckets.other.push(p);
      }
    });

    const result = [];
    const keys = [1, 2, 4, 3, 5, 'other'];
    let idx = 0;
    let hasMore = true;
    while (hasMore) {
      hasMore = false;
      for (const k of keys) {
        if (idx < buckets[k].length) {
          result.push(buckets[k][idx]);
          hasMore = true;
        }
      }
      idx++;
    }
    return result;
  }

  function renderCatalog() {
    if (!catalogProductsGridEl) return;
    let prods = state.products || [];
    if (state.selectedCategory > 0) {
      prods = prods.filter(p => isProductInCategory(p, state.selectedCategory));
    } else {
      // "Barchasi" toifasida oxirida yuklanganlar bir joyda qolib ketmasligi uchun toifalar aralash chiqariladi
      prods = getMixedCatalogProducts(prods);
    }

    // Katalogdagi maxsus USD filtri ($ Dan - $ Gacha)
    const cpfMin = state.catalogPriceFilter?.min;
    const cpfMax = state.catalogPriceFilter?.max;
    if (cpfMin !== null && cpfMin !== undefined && !isNaN(cpfMin) && cpfMin > 0) {
      prods = prods.filter(p => (p.price || 0) >= cpfMin);
    }
    if (cpfMax !== null && cpfMax !== undefined && !isNaN(cpfMax) && cpfMax > 0) {
      prods = prods.filter(p => (p.price || 0) <= cpfMax);
    }

    const catKeys = {
      0: 'cat_all',
      1: 'cat_smartphones',
      2: 'cat_laptops',
      3: 'cat_audio',
      4: 'cat_watches',
      5: 'cat_accessories'
    };
    const titleKey = catKeys[state.selectedCategory];

    if (catalogSectionTitleEl) {
      catalogSectionTitleEl.textContent = titleKey ? t(titleKey) : t('cat_all');
    }
    if (catalogResultsCountEl) {
      catalogResultsCountEl.textContent = `${prods.length} ${t('items_suffix')}`;
    }

    if (prods.length === 0) {
      catalogProductsGridEl.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px 16px; color: var(--text-sub);">
          ${t('empty_desc')}
        </div>
      `;
      return;
    }

    let html = '';
    prods.forEach(p => {
      const isFav = state.wishlist.has(p.id);
      const brand = p.name.toLowerCase().includes('macbook') || p.name.toLowerCase().includes('iphone') ? 'APPLE' : 'PREMIUM';
      html += `
        <article class="product-card" data-id="${p.id}">
          <div class="card-media">
            <button class="wishlist-btn ${isFav ? 'active' : ''}${Number(p.is_discount) === 1 ? ' has-gift' : ''}" data-id="${p.id}" aria-label="Sevimlilar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="${isFav ? '#ef4444' : 'none'}" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
            ${Number(p.is_discount) === 1 ? `
              <div class="gift-badge" title="Hafta chegirmasi">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 12 20 22 4 22 4 12"></polyline>
                  <rect x="2" y="7" width="20" height="5"></rect>
                  <line x1="12" y1="22" x2="12" y2="7"></line>
                  <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                  <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
                </svg>
              </div>
            ` : ''}
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="product-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="card-body">
            <span class="product-brand">${brand}</span>
            <h3 class="product-title">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            ${renderProductPriceBlock(p)}
            <div class="card-actions-stack">
              ${getCartButtonHtml(p.id)}
              ${p.post_url ? `
                <button class="btn-channel-link btn-liquid" data-post-url="${p.post_url}" data-id="${p.id}" data-haptic="light">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m22 2-7 20-4-9-9-4Z"></path>
                    <path d="M22 2 11 13"></path>
                  </svg>
                  <span>${t('view_in_channel')}</span>
                </button>
              ` : '<div class="btn-channel-placeholder"></div>'}
            </div>
          </div>
        </article>
      `;
    });

    catalogProductsGridEl.innerHTML = html;
  }

  // Katalog grid hodisasi (Event Delegation)
  catalogProductsGridEl?.addEventListener('click', (e) => {
    const card = e.target.closest('.product-card');
    if (!card) return;
    const pid = parseInt(card.dataset.id, 10);
    const prod = state.products.find(x => x.id === pid);
    if (!prod) return;

    const wishlistBtn = e.target.closest('.wishlist-btn');
    if (wishlistBtn) {
      e.stopPropagation();
      toggleWishlist(prod, e);
      return;
    }

    const addCartBtn = e.target.closest('.btn-add-cart');
    if (addCartBtn) {
      e.stopPropagation();
      if (addCartBtn.classList.contains('btn-goto-order') || (state.cart && state.cart[pid])) {
        switchTab('cart');
        return;
      }
      handleAddToCart(prod, addCartBtn);
      return;
    }

    const channelBtn = e.target.closest('.btn-channel-link');
    if (channelBtn) {
      e.stopPropagation();
      openChannelPost(channelBtn.dataset.postUrl, pid);
      return;
    }

    openProductModal(prod);
  });

  // ==========================================================================
  // 7. PROFIL BO'LIMI (PROFILE SECTION)
  // ==========================================================================
  function renderProfileSection() {
    const user = tg?.initDataUnsafe?.user;
    if (user) {
      if (profileUserNameEl) {
        const name = [user.first_name, user.last_name].filter(Boolean).join(' ');
        profileUserNameEl.textContent = name || 'Hurmatli mijoz';
      }
      if (profileUserHandleEl) {
        profileUserHandleEl.textContent = user.username ? `@${user.username}` : `ID: ${user.id}`;
      }
      if (profileAvatarEl) {
        if (user.photo_url) {
          profileAvatarEl.innerHTML = `<img src="${user.photo_url}" alt="Avatar" class="profile-avatar-img" />`;
        } else {
          const initials = (user.first_name ? user.first_name[0] : 'D') + (user.last_name ? user.last_name[0] : 'S');
          profileAvatarEl.textContent = initials.toUpperCase();
        }
      }
    }

    const cartCount = Object.values(state.cart).reduce((sum, i) => sum + i.qty, 0);
    if (statCartCountEl) statCartCountEl.textContent = cartCount.toString();
    if (statWishCountEl) statWishCountEl.textContent = state.wishlist.size.toString();

    const isLight = document.documentElement.classList.contains('light');
    if (currentThemeLabelEl) {
      currentThemeLabelEl.textContent = isLight ? 'Kunduzgi rejim faol' : 'Tungi rejim faol';
    }
  }

  statCartBoxEl?.addEventListener('click', () => switchTab('cart'));
  statWishBoxEl?.addEventListener('click', () => switchTab('wishlist'));

  // ==========================================================================
  // 8. MAHSULOT BATAFSIL BO'LIMI (PRODUCT DETAIL FULL VIEW)
  // ==========================================================================
  function openProductModal(prod) {
    triggerHaptic('medium');
    state.selectedProduct = prod;

    let images = [];
    if (Array.isArray(prod.gallery_images) && prod.gallery_images.length > 0) {
      images = prod.gallery_images.filter(Boolean);
    } else if (typeof prod.gallery_images === 'string') {
      try {
        const parsed = JSON.parse(prod.gallery_images);
        if (Array.isArray(parsed)) images = parsed.filter(Boolean);
      } catch (e) {
        images = [];
      }
    }
    if (images.length === 0) {
      images = [getProductImageUrl(prod)];
    } else {
      images = images.map(img => {
        if (!img) return FALLBACK_IMAGE_URL;
        if (typeof img === 'string' && !img.startsWith('/') && !img.startsWith('http')) {
          return '/api/photo/' + img;
        }
        return img;
      });
    }

    const specs = parseSpecs(prod.description);
    const installmentPlan = parseInstallmentPlan(prod.description);
    const isFav = state.wishlist.has(prod.id);

    const isUzsOnly = Boolean(prod.currency === 'UZS' && prod.price_uzs);
    if (pdWishlistBtnEl) {
      pdWishlistBtnEl.classList.toggle('active', isFav);
    }
    if (pdBottomPriceEl) {
      pdBottomPriceEl.textContent = isUzsOnly ? formatUzsAmount(prod.price_uzs) : formatPrice(prod.price);
    }
    if (pdBottomPriceUzsEl) {
      pdBottomPriceUzsEl.textContent = isUzsOnly ? '' : `≈ ${formatPriceUzs(prod.price)}`;
    }

    const cleanDesc = getCleanProductDescription(prod.description);

    let galleryHTML = `
      <div class="modal-gallery-wrap">
        <div class="modal-gallery-track" id="pdGalleryTrack">
          ${images.map((img, i) => `
            <div class="gallery-slide" data-index="${i}">
              <img src="${img}" alt="${escapeHtml(prod.name)}" data-index="${i}" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
            </div>
          `).join('')}
        </div>
        ${images.length > 1 ? `
          <div class="gallery-counter"><span id="pdGalleryCounter">1</span> / ${images.length}</div>
          <div class="gallery-dots" id="pdGalleryDots">
            ${images.map((_, i) => `<span class="dot ${i === 0 ? 'active' : ''}"></span>`).join('')}
          </div>
        ` : ''}
      </div>
    `;

    pdBodyContentEl.innerHTML = `
      ${galleryHTML}
      <div class="pd-hero-meta">
        <span class="pd-hero-brand">APPLE</span>
        <h2 class="pd-hero-title">${escapeHtml(getCleanCardTitle(prod.name))}</h2>
        <div class="pd-hero-price-stack">
          ${isUzsOnly ? `
            <div class="pd-hero-usd">${formatUzsAmount(prod.price_uzs)}</div>
          ` : `
            <div class="pd-hero-usd">${formatPrice(prod.price)}</div>
            <div class="pd-hero-uzs">≈ ${formatPriceUzs(prod.price)}</div>
          `}
        </div>
      </div>
      
      ${specs.length > 0 ? `
        <div class="specs-container">
          <div class="specs-title">Asosiy parametrlar va xususiyatlar</div>
          <div class="specs-list">
            ${specs.map(s => `
              <div class="spec-row">
                <span class="spec-key">${escapeHtml(s.key)}</span>
                <span class="spec-val">${escapeHtml(s.val)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      ` : (cleanDesc ? `
        <div class="specs-container">
          <div class="specs-title">Asosiy parametrlar va xususiyatlar</div>
          <div class="pd-description-body">
            ${cleanDesc.split('\n').map(l => l.trim() ? `<p class="pd-desc-line">${escapeHtml(l)}</p>` : `<div class="pd-desc-spacer"></div>`).join('')}
          </div>
        </div>
      ` : '')}

      ${installmentPlan ? `
        <div class="pd-installment-card">
          <div class="pd-installment-head">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="20" height="14" x="2" y="5" rx="2"></rect>
              <line x1="2" x2="22" y1="10" y2="10"></line>
            </svg>
            <span>Boʻlib toʻlash (Muddatli toʻlov)</span>
          </div>
          <div class="installment-initial">${escapeHtml(installmentPlan.initialPay)}</div>
          <div class="installment-pills">
            ${installmentPlan.plans.map(pl => `<span class="inst-pill">${escapeHtml(pl)}</span>`).join('')}
          </div>
        </div>
      ` : ''}

      ${prod.post_url ? `
        <div class="pd-channel-box">
          <button class="btn-channel-pd btn-liquid" id="pdChannelViewBtn" data-post-url="${prod.post_url}" data-haptic="light">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m22 2-7 20-4-9-9-4Z"></path>
              <path d="M22 2 11 13"></path>
            </svg>
            <span>Telegram kanaldan koʻrish</span>
          </button>
        </div>
      ` : ''}

      <div class="store-guarantee-card" style="margin: 16px 0 24px;">
        <strong class="guarantee-card-title">1 YILLIK RASMIY KAFOLAT</strong>
        <p class="guarantee-card-desc">Ushbu Apple qurilmasi yangi va qadoqlangan holda yetkazib beriladi. Toʻlov tovar qoʻlingizga yetgach amalga oshiriladi.</p>
      </div>
    `;

    // Rasm ustiga bosilganda to'liq ekranda ochish (Fullscreen Lightbox)
    document.querySelectorAll('#pdGalleryTrack .gallery-slide').forEach(slide => {
      slide.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(slide.dataset.index, 10) || 0;
        openFullscreenGallery(images, idx, prod.name);
      });
    });

    // Kanaldan ko'rish tugmasi hodisasi
    document.getElementById('pdChannelViewBtn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (prod.post_url) {
        openChannelPost(prod.post_url, prod.id);
      }
    });

    // Karusel surish hodisasini ulash
    if (images.length > 1) {
      const track = document.getElementById('pdGalleryTrack');
      const counter = document.getElementById('pdGalleryCounter');
      const dots = document.querySelectorAll('#pdGalleryDots .dot');
      let currentIndex = 0;

      track?.addEventListener('scroll', () => {
        const slideWidth = track.clientWidth;
        if (slideWidth > 0) {
          const newIdx = Math.round(track.scrollLeft / slideWidth);
          if (newIdx !== currentIndex && newIdx >= 0 && newIdx < images.length) {
            currentIndex = newIdx;
            if (counter) counter.textContent = (newIdx + 1).toString();
            dots.forEach((d, i) => d.classList.toggle('active', i === newIdx));
          }
        }
      }, { passive: true });
    }

    const inCart = Boolean(state.cart && state.cart[prod.id]);
    updatePdCartButton(inCart);

    switchTab('product-detail');

    // Mahsulot ochilganda rasm karuseli har doim 1-rasmdan (1 / N) boshlansin
    setTimeout(() => {
      const track = document.getElementById('pdGalleryTrack');
      const counter = document.getElementById('pdGalleryCounter');
      const dots = document.querySelectorAll('#pdGalleryDots .dot');
      if (track) {
        track.scrollLeft = 0;
        track.scrollTo({ left: 0, behavior: 'instant' });
      }
      if (counter) counter.textContent = '1';
      if (dots.length > 0) {
        dots.forEach((d, i) => d.classList.toggle('active', i === 0));
      }
    }, 15);
  }

  // ==========================================================================
  // TO'LIQ EKRANDA RASM KO'RISH (FULLSCREEN LIGHTBOX VIEWER)
  // ==========================================================================
  // Lightbox Zoom va Pan o'zgaruvchilari
  let fsZoomScale = 1;
  let fsPanX = 0;
  let fsPanY = 0;
  let fsInitialPinchDist = 0;
  let fsStartScale = 1;
  let fsStartPanX = 0;
  let fsStartPanY = 0;
  let fsStartFocalX = 0;
  let fsStartFocalY = 0;
  let fsLastTapTime = 0;
  let fsIsPinching = false;
  let fsIsPanning = false;

  function getActiveSlideImg() {
    if (!fsViewerTrackEl) return null;
    const width = fsViewerTrackEl.clientWidth || window.innerWidth;
    const idx = Math.round(fsViewerTrackEl.scrollLeft / width);
    const slide = fsViewerTrackEl.children[idx];
    return slide ? slide.querySelector('img') : null;
  }

  function calcPanLimits(img, scale) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let imgW = vw * 0.9;
    let imgH = vh * 0.75;
    if (img) {
      const clientW = img.clientWidth;
      const clientH = img.clientHeight;
      if (clientW > 0 && clientH > 0) {
        imgW = clientW;
        imgH = clientH;
      } else if (img.naturalWidth > 0 && img.naturalHeight > 0) {
        const maxW = vw * 0.96;
        const maxH = vh * 0.80;
        const aspect = img.naturalWidth / img.naturalHeight;
        if (maxW / aspect <= maxH) {
          imgW = maxW;
          imgH = maxW / aspect;
        } else {
          imgH = maxH;
          imgW = maxH * aspect;
        }
      }
    }

    if (scale <= 1.02) {
      return { maxX: 0, maxY: 0 };
    }

    const scaledW = imgW * scale;
    const scaledH = imgH * scale;

    // Chekkalar va burchaklarni bemalol ekranning o'rtasigacha va undan ham o'tkazib
    // surib ko'rish imkonini beruvchi saxiy chegaralar (generous pan limits):
    const baseMaxX = Math.max(0, (scaledW - vw) / 2);
    const baseMaxY = Math.max(0, (scaledH - vh) / 2);

    const maxX = Math.max(baseMaxX + vw * 0.45, scaledW / 2 + 50);
    const maxY = Math.max(baseMaxY + vh * 0.45, scaledH / 2 + 50);

    return { maxX, maxY };
  }

  function applyImgZoom(img, animated = false) {
    if (!img) return;
    if (animated) {
      img.style.transition = 'transform 0.25s cubic-bezier(0.2, 0.9, 0.3, 1)';
    } else {
      img.style.transition = 'none';
    }
    if (fsZoomScale <= 1.02) {
      fsZoomScale = 1;
      fsPanX = 0;
      fsPanY = 0;
      img.style.transform = '';
      if (fsViewerDotsEl) {
        fsViewerDotsEl.style.opacity = '1';
        fsViewerDotsEl.style.pointerEvents = '';
      }
      if (fsViewerTrackEl) {
        fsViewerTrackEl.style.overflowX = 'auto';
        fsViewerTrackEl.style.scrollSnapType = 'x mandatory';
        fsViewerTrackEl.style.touchAction = 'pan-x';
      }
    } else {
      const limits = calcPanLimits(img, fsZoomScale);

      if (!animated) {
        // Faol surish/chimchilash paytida rezinka chegarasi
        const overLimitMultiplier = 1.35;
        const hardMaxX = limits.maxX * overLimitMultiplier;
        const hardMaxY = limits.maxY * overLimitMultiplier;
        fsPanX = Math.max(-hardMaxX, Math.min(hardMaxX, fsPanX));
        fsPanY = Math.max(-hardMaxY, Math.min(hardMaxY, fsPanY));
      } else {
        // Barmoq qo'yib yuborilganda aniq chegaralarga qaytarish
        fsPanX = Math.max(-limits.maxX, Math.min(limits.maxX, fsPanX));
        fsPanY = Math.max(-limits.maxY, Math.min(limits.maxY, fsPanY));
      }

      img.style.transform = `translate3d(${fsPanX.toFixed(2)}px, ${fsPanY.toFixed(2)}px, 0) scale(${fsZoomScale.toFixed(4)})`;

      if (fsViewerDotsEl) {
        fsViewerDotsEl.style.opacity = '0';
        fsViewerDotsEl.style.pointerEvents = 'none';
      }
      if (fsViewerTrackEl) {
        fsViewerTrackEl.style.overflowX = 'hidden';
        fsViewerTrackEl.style.scrollSnapType = 'none';
        fsViewerTrackEl.style.touchAction = 'none';
      }
    }
  }

  function resetZoomState() {
    fsZoomScale = 1;
    fsPanX = 0;
    fsPanY = 0;
    fsIsPinching = false;
    fsIsPanning = false;
    fsIsMouseDown = false;
    if (fsViewerDotsEl) {
      fsViewerDotsEl.style.opacity = '1';
      fsViewerDotsEl.style.pointerEvents = '';
    }
    if (fsViewerTrackEl) {
      fsViewerTrackEl.style.overflowX = 'auto';
      fsViewerTrackEl.style.scrollSnapType = 'x mandatory';
      fsViewerTrackEl.style.touchAction = 'pan-x';
      Array.from(fsViewerTrackEl.children).forEach(slide => {
        const img = slide.querySelector('img');
        if (img) {
          img.style.transition = 'transform 0.25s cubic-bezier(0.2, 0.9, 0.3, 1)';
          img.style.transform = '';
          setTimeout(() => {
            img.style.transition = '';
          }, 260);
        }
      });
    }
  }

  function openFullscreenGallery(images, startIndex = 0, title = 'Mahsulot') {
    if (!fsViewerEl || !fsViewerTrackEl || !Array.isArray(images) || images.length === 0) return;
    triggerHaptic('medium');
    resetZoomState();

    fsViewerTrackEl.innerHTML = images.map((img, i) => `
      <div class="fs-viewer-slide" data-index="${i}">
        <img src="${img}" alt="${escapeHtml(title)}" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
      </div>
    `).join('');

    if (fsViewerDotsEl) {
      if (images.length > 1) {
        fsViewerDotsEl.innerHTML = images.map((_, i) => `<span class="dot ${i === startIndex ? 'active' : ''}"></span>`).join('');
      } else {
        fsViewerDotsEl.innerHTML = '';
      }
    }

    if (fsViewerCounterEl) {
      fsViewerCounterEl.textContent = `${startIndex + 1} / ${images.length}`;
    }

    // Holatni tozalash
    fsViewerEl.style.opacity = '';
    fsViewerEl.style.backgroundColor = '';
    fsViewerEl.style.transition = '';
    fsViewerTrackEl.style.scrollSnapType = '';
    fsViewerTrackEl.style.overflowX = '';

    fsViewerEl.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Telegram BackButton ni ko'rsatish
    updateBackButtons();

    // Boshlang'ich rasmga skroll qilish
    setTimeout(() => {
      const slideWidth = fsViewerTrackEl.clientWidth;
      if (slideWidth > 0 && startIndex > 0) {
        fsViewerTrackEl.scrollTo({ left: slideWidth * startIndex, behavior: 'instant' });
      }
    }, 20);
  }

  function closeFullscreenGallery() {
    if (!fsViewerEl) return;
    triggerHaptic('light');
    resetZoomState();
    fsViewerEl.classList.add('hidden');
    document.body.style.overflow = '';
    fsViewerEl.style.opacity = '';
    fsViewerEl.style.backgroundColor = '';
    fsViewerEl.style.transition = '';
    if (fsViewerTrackEl) {
      fsViewerTrackEl.style.scrollSnapType = '';
      fsViewerTrackEl.style.overflowX = '';
      Array.from(fsViewerTrackEl.children).forEach(slide => {
        slide.style.transition = '';
        slide.style.transform = '';
        slide.style.opacity = '';
      });
    }
    updateBackButtons();
  }

  fsViewerCloseBtnEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    closeFullscreenGallery();
  });

  // Fullscreen treki orqali surishda hisoblagich va nuqtalarni yangilash
  fsViewerTrackEl?.addEventListener('scroll', () => {
    const width = fsViewerTrackEl.clientWidth;
    if (width <= 0) return;
    const newIdx = Math.round(fsViewerTrackEl.scrollLeft / width);
    const total = fsViewerTrackEl.children.length;
    if (fsViewerCounterEl && total > 0 && newIdx >= 0 && newIdx < total) {
      fsViewerCounterEl.textContent = `${newIdx + 1} / ${total}`;
    }
    const dots = fsViewerDotsEl?.querySelectorAll('.dot');
    if (dots) {
      dots.forEach((d, i) => d.classList.toggle('active', i === newIdx));
    }
    if (fsZoomScale > 1.02) {
      resetZoomState();
    }
  }, { passive: true });

  // --------------------------------------------------------------------------
  // PASTGA TORTIB YOPISH VA GESTURES (PINCH ZOOM / PAN / SWIPE DOWN)
  // --------------------------------------------------------------------------
  let fsTouchStartX = 0;
  let fsTouchStartY = 0;
  let fsTouchStartTime = 0;
  let fsIsPullingDown = false;
  let fsDeltaY = 0;
  let fsActiveSlideEl = null;
  let fsHasMoved = false;

  fsViewerTrackEl?.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
      // 2 barmoqli chimchilash (pinch-to-zoom)
      fsIsPinching = true;
      fsIsPanning = false;
      fsIsPullingDown = false;
      fsHasMoved = true;
      const t0 = e.touches[0];
      const t1 = e.touches[1];
      fsInitialPinchDist = Math.hypot(
        t0.clientX - t1.clientX,
        t0.clientY - t1.clientY
      );
      fsStartFocalX = (t0.clientX + t1.clientX) / 2;
      fsStartFocalY = (t0.clientY + t1.clientY) / 2;
      fsStartScale = fsZoomScale;
      fsStartPanX = fsPanX;
      fsStartPanY = fsPanY;
      if (e.cancelable) e.preventDefault();
      return;
    }

    if (e.touches.length === 1) {
      const touch = e.touches[0];
      fsTouchStartX = touch.clientX;
      fsTouchStartY = touch.clientY;
      fsTouchStartTime = Date.now();
      fsIsPullingDown = false;
      fsDeltaY = 0;
      fsHasMoved = false;

      const width = fsViewerTrackEl.clientWidth || window.innerWidth;
      const currentIdx = Math.round(fsViewerTrackEl.scrollLeft / width);
      fsActiveSlideEl = fsViewerTrackEl.children[currentIdx] || null;

      // Agar rasm allaqachon kattalashtirilgan bo'lsa (scale > 1.05), uni bitta barmoq bilan pan qilish
      if (fsZoomScale > 1.05) {
        fsIsPanning = true;
        fsStartPanX = fsPanX;
        fsStartPanY = fsPanY;
      } else {
        fsIsPanning = false;
      }
    }
  }, { passive: false });

  fsViewerTrackEl?.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2 && fsIsPinching) {
      if (e.cancelable) e.preventDefault();
      const t0 = e.touches[0];
      const t1 = e.touches[1];
      const currentDist = Math.hypot(
        t0.clientX - t1.clientX,
        t0.clientY - t1.clientY
      );
      if (fsInitialPinchDist > 0) {
        const factor = currentDist / fsInitialPinchDist;
        const targetScale = Math.max(0.75, Math.min(6.0, fsStartScale * factor));
        const currFocalX = (t0.clientX + t1.clientX) / 2;
        const currFocalY = (t0.clientY + t1.clientY) / 2;
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;

        // Nuqtaga tayangan (focal point) chimchilash formulasi:
        // Barmoqlar ostidagi rasm nuqtasi harakat davomida aniq barmoqlar ostida qoladi
        fsPanX = (currFocalX - centerX) - ((fsStartFocalX - centerX - fsStartPanX) / fsStartScale) * targetScale;
        fsPanY = (currFocalY - centerY) - ((fsStartFocalY - centerY - fsStartPanY) / fsStartScale) * targetScale;
        fsZoomScale = targetScale;

        const img = getActiveSlideImg();
        applyImgZoom(img, false);
      }
      return;
    }

    if (e.touches.length === 1) {
      const touch = e.touches[0];
      const diffX = touch.clientX - fsTouchStartX;
      const diffY = touch.clientY - fsTouchStartY;

      if (Math.abs(diffX) > 6 || Math.abs(diffY) > 6) {
        fsHasMoved = true;
      }

      // 1. Agar rasm kattalashgan bo'lsa (scale > 1.05), bitta barmoq bilan erkin pan qilish
      if (fsZoomScale > 1.05) {
        if (e.cancelable) e.preventDefault();
        fsPanX = fsStartPanX + diffX;
        fsPanY = fsStartPanY + diffY;
        const img = getActiveSlideImg();
        applyImgZoom(img, false);
        return;
      }

      // 2. Normal holatda (scale 1.0): agar gorizontal surilayotgan bo'lsa, slayd almashtirish
      if (!fsIsPullingDown && Math.abs(diffX) > 12 && Math.abs(diffX) > Math.abs(diffY)) {
        return;
      }

      // Pastga tortish harakati boshlanishi (faqat scale 1.0 paytida)
      if (!fsIsPullingDown) {
        if (diffY > 8 && diffY > Math.abs(diffX) * 1.15) {
          fsIsPullingDown = true;
          fsViewerTrackEl.style.scrollSnapType = 'none';
        }
      }

      if (fsIsPullingDown && diffY > 0) {
        fsDeltaY = diffY;
        if (e.cancelable) e.preventDefault();

        // Telegram / iOS uslubidagi silliq dinamik fizika
        const scale = Math.max(0.72, 1 - (fsDeltaY / 1200));
        const bgOpacity = Math.max(0.18, 0.95 - (fsDeltaY / 450) * 0.78);

        if (fsActiveSlideEl) {
          fsActiveSlideEl.style.transition = 'none';
          fsActiveSlideEl.style.transform = `translate3d(0, ${fsDeltaY}px, 0) scale(${scale})`;
        }
        if (fsViewerEl) {
          fsViewerEl.style.backgroundColor = `rgba(0, 0, 0, ${bgOpacity})`;
        }
      }
    }
  }, { passive: false });

  function finishFsPullDown(e) {
    // Agar 2 barmoqdan bittasi ko'tarilib, bittasi hali ekranda qolgan bo'lsa -> silliq pan qilishga o'tish
    if (fsIsPinching && e && e.touches && e.touches.length === 1) {
      fsIsPinching = false;
      if (fsZoomScale > 1.05) {
        fsIsPanning = true;
        const remainingTouch = e.touches[0];
        fsTouchStartX = remainingTouch.clientX;
        fsTouchStartY = remainingTouch.clientY;
        fsStartPanX = fsPanX;
        fsStartPanY = fsPanY;
      }
      return;
    }

    if (fsIsPinching) {
      fsIsPinching = false;
      const img = getActiveSlideImg();
      if (fsZoomScale < 1.05) {
        resetZoomState();
      } else {
        if (fsZoomScale > 5.5) fsZoomScale = 5.5;
        applyImgZoom(img, true);
      }
      return;
    }

    if (fsIsPanning) {
      fsIsPanning = false;
      const img = getActiveSlideImg();
      if (fsZoomScale < 1.05) {
        resetZoomState();
      } else {
        applyImgZoom(img, true);
      }
      return;
    }

    if (!fsIsPullingDown) return;
    fsIsPullingDown = false;
    fsViewerTrackEl.style.scrollSnapType = '';

    const elapsed = Date.now() - fsTouchStartTime;
    const velocity = fsDeltaY / Math.max(1, elapsed);

    // Agar 75px dan ko'proq pastga tortilgan bo'lsa yoki siltash tezligi yuqori bo'lsa -> yopamiz
    if (fsDeltaY > 75 || (fsDeltaY > 35 && velocity > 0.38)) {
      if (fsActiveSlideEl) {
        fsActiveSlideEl.style.transition = 'transform 0.22s cubic-bezier(0.2, 0.9, 0.3, 1), opacity 0.22s ease';
        fsActiveSlideEl.style.transform = `translate3d(0, ${window.innerHeight}px, 0) scale(0.6)`;
        fsActiveSlideEl.style.opacity = '0';
      }
      if (fsViewerEl) {
        fsViewerEl.style.transition = 'background-color 0.22s ease, opacity 0.22s ease';
        fsViewerEl.style.opacity = '0';
      }

      setTimeout(() => {
        closeFullscreenGallery();
      }, 220);
    } else {
      // Yopishga yetmadi -> silliq o'z joyiga qaytarish (bounce-back)
      if (fsActiveSlideEl) {
        fsActiveSlideEl.style.transition = 'transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1)';
        fsActiveSlideEl.style.transform = '';
      }
      if (fsViewerEl) {
        fsViewerEl.style.transition = 'background-color 0.2s ease';
        fsViewerEl.style.backgroundColor = '';
      }

      setTimeout(() => {
        if (fsActiveSlideEl) fsActiveSlideEl.style.transition = '';
        if (fsViewerEl) fsViewerEl.style.transition = '';
      }, 210);
    }
  }

  fsViewerTrackEl?.addEventListener('touchend', (e) => {
    // Agar chimchilash paytida hali bitta barmoq ekranda bo'lsa:
    if (fsIsPinching && e.touches && e.touches.length === 1) {
      finishFsPullDown(e);
      return;
    }

    // Double tap tekshiruvi (surilmasdan bitta barmog'i bilan 320ms ichida 2 marta bosganda)
    if (e.changedTouches && e.changedTouches.length === 1 && !fsHasMoved && !fsIsPinching) {
      const now = Date.now();
      const touch = e.changedTouches[0];
      const targetImg = e.target.closest('.fs-viewer-slide img') || (e.target.closest('.fs-viewer-slide')?.querySelector('img')) || getActiveSlideImg();
      if (targetImg && (now - fsLastTapTime < 320)) {
        e.preventDefault();
        triggerHaptic('light');
        if (fsZoomScale > 1.1) {
          resetZoomState();
        } else {
          const centerX = window.innerWidth / 2;
          const centerY = window.innerHeight / 2;
          const targetScale = 2.6;
          fsZoomScale = targetScale;
          // Bosilgan nuqtaga qaratib kattalashtirish (focal zoom):
          fsPanX = -(touch.clientX - centerX) * (targetScale - 1);
          fsPanY = -(touch.clientY - centerY) * (targetScale - 1);
          applyImgZoom(targetImg, true);
        }
        fsLastTapTime = 0;
        return;
      }
      fsLastTapTime = now;
    }

    finishFsPullDown(e);
  }, { passive: false });

  fsViewerTrackEl?.addEventListener('touchcancel', finishFsPullDown, { passive: true });

  // Double click (desktop / MacBook sichqoncha bilan ikki marta bosganda bosilgan joyga yaqinlashtirish)
  fsViewerTrackEl?.addEventListener('dblclick', (e) => {
    const targetImg = e.target.closest('.fs-viewer-slide img') || (e.target.closest('.fs-viewer-slide')?.querySelector('img')) || getActiveSlideImg();
    if (!targetImg) return;
    e.preventDefault();
    triggerHaptic('light');
    if (fsZoomScale > 1.1) {
      resetZoomState();
    } else {
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      const targetScale = 2.6;
      fsZoomScale = targetScale;
      fsPanX = -(e.clientX - centerX) * (targetScale - 1);
      fsPanY = -(e.clientY - centerY) * (targetScale - 1);
      applyImgZoom(targetImg, true);
    }
  });

  // MacBook trackpad pinch (e.ctrlKey) yoki sichqoncha g'ildiragi bilan surish
  fsViewerTrackEl?.addEventListener('wheel', (e) => {
    // 1. MacBook trackpad chimchilash (pinch zoom - brauzerda e.ctrlKey=true beradi)
    if (e.ctrlKey) {
      e.preventDefault();
      const delta = -e.deltaY * 0.015;
      const prevScale = fsZoomScale;
      const newScale = Math.max(1, Math.min(6.0, fsZoomScale + delta));
      if (newScale <= 1.02) {
        resetZoomState();
        return;
      }
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      const focalX = e.clientX;
      const focalY = e.clientY;
      fsPanX = (focalX - centerX) - ((focalX - centerX - fsPanX) / prevScale) * newScale;
      fsPanY = (focalY - centerY) - ((focalY - centerY - fsPanY) / prevScale) * newScale;
      fsZoomScale = newScale;
      const img = getActiveSlideImg();
      applyImgZoom(img, false);
      return;
    }

    // 2. Agar rasm kattalashgan bo'lsa, trekpadda ikki barmoq bilan erkin pan qilish
    if (fsZoomScale > 1.05) {
      e.preventDefault();
      fsPanX -= e.deltaX * 1.0;
      fsPanY -= e.deltaY * 1.0;
      const img = getActiveSlideImg();
      applyImgZoom(img, false);
      return;
    }

    // 3. Normal 1.0x o'lchamda pastga tez surilganda yopish
    if (e.deltaY > 55 && Math.abs(e.deltaY) > Math.abs(e.deltaX) * 1.4) {
      closeFullscreenGallery();
    }
  }, { passive: false });

  // Sichqoncha bilan erkin sudrash (Desktop mouse drag panning)
  let fsIsMouseDown = false;
  let fsMouseStartX = 0;
  let fsMouseStartY = 0;

  fsViewerTrackEl?.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    if (fsZoomScale > 1.05) {
      fsIsMouseDown = true;
      fsMouseStartX = e.clientX;
      fsMouseStartY = e.clientY;
      fsStartPanX = fsPanX;
      fsStartPanY = fsPanY;
      fsHasMoved = false;
      e.preventDefault();
    }
  });

  window.addEventListener('mousemove', (e) => {
    if (!fsIsMouseDown || fsZoomScale <= 1.05) return;
    const diffX = e.clientX - fsMouseStartX;
    const diffY = e.clientY - fsMouseStartY;
    if (Math.abs(diffX) > 4 || Math.abs(diffY) > 4) {
      fsHasMoved = true;
    }
    fsPanX = fsStartPanX + diffX;
    fsPanY = fsStartPanY + diffY;
    const img = getActiveSlideImg();
    applyImgZoom(img, false);
  });

  window.addEventListener('mouseup', () => {
    if (fsIsMouseDown) {
      fsIsMouseDown = false;
      const img = getActiveSlideImg();
      applyImgZoom(img, true);
    }
  });

  // Rasm atrofidagi bo'sh qora fonga (backdrop) bosilganda yopish
  fsViewerTrackEl?.addEventListener('click', (e) => {
    if (e.target.tagName !== 'IMG' && !fsHasMoved) {
      if (fsZoomScale > 1.1) {
        resetZoomState();
      } else {
        closeFullscreenGallery();
      }
    }
  });

  pdWishlistBtnEl?.addEventListener('click', () => {
    if (state.selectedProduct) {
      toggleWishlist(state.selectedProduct);
      const isFav = state.wishlist.has(state.selectedProduct.id);
      pdWishlistBtnEl.classList.toggle('active', isFav);
    }
  });

  pdAddToCartBtnEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (state.selectedProduct) {
      const pid = state.selectedProduct.id;
      if (pdAddToCartBtnEl.classList.contains('btn-goto-order') || (state.cart && state.cart[pid])) {
        switchTab('cart');
        return;
      }
      handleAddToCart(state.selectedProduct, pdAddToCartBtnEl);
    }
  });

  pdBackBtnEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    goBack();
  });

  pdChannelIconBtnEl?.addEventListener('click', () => {
    if (state.selectedProduct?.post_url) {
      openChannelPost(state.selectedProduct.post_url, state.selectedProduct.id);
    }
  });

  // ==========================================================================
  // 9. MAHSULOTLARNI YUKLASH (API) & MEMOIZED RENDER
  // ==========================================================================
  async function loadProducts(silent = false) {
    if (!silent && state.products.length === 0) {
      state.isLoading = true;
      renderSkeleton();
    }

    try {
      const params = new URLSearchParams();
      if (state.selectedCategory > 0) {
        params.append('category_id', state.selectedCategory);
      }
      if (state.selectedSort && state.selectedSort !== 'default') {
        params.append('sort', state.selectedSort);
      }
      if (state.searchQuery.trim()) {
        params.append('search', state.searchQuery.trim());
      }
      const { minUsd, maxUsd } = getActivePriceFilterUsd();
      if (minUsd !== null && minUsd > 0) {
        params.append('min_price', minUsd);
      }
      if (maxUsd !== null && maxUsd > 0) {
        params.append('max_price', maxUsd);
      }

      const res = await apiFetch(`/api/products?${params.toString()}`);
      if (!res.ok) throw new Error('Mahsulotlar yuklanmadi');
      const data = await res.json();
      if (Array.isArray(data)) {
        state.products = data;
        if (data[0] && data[0].current_usd_rate) {
          state.currentUsdRate = data[0].current_usd_rate;
          localStorage.setItem('demostore_cached_usd_rate', String(state.currentUsdRate));
          localStorage.setItem('demostore_cached_usd_rate_time', String(Date.now()));
          updateLiveUsdBadge(data[0].current_usd_rate);
        }
      } else if (data && data.products) {
        state.products = data.products;
        if (data.current_usd_rate) {
          state.currentUsdRate = data.current_usd_rate;
          localStorage.setItem('demostore_cached_usd_rate', String(state.currentUsdRate));
          localStorage.setItem('demostore_cached_usd_rate_time', String(Date.now()));
          updateLiveUsdBadge(data.current_usd_rate);
        }
      }

      // Keshga saqlash (Keyingi ochilishda 0ms da yuklash uchun, faqat to'liq ro'yxat)
      if (!state.searchQuery.trim() && state.selectedCategory === 0 && (!state.selectedSort || state.selectedSort === 'default') && minUsd === null && maxUsd === null) {
        try {
          localStorage.setItem('demostore_cached_products', JSON.stringify(state.products));
          localStorage.setItem('demostore_cached_usd_rate', String(state.currentUsdRate));
          localStorage.setItem('demostore_cached_usd_rate_time', String(Date.now()));
        } catch (e) {}
      }

      renderProducts();
      renderDiscountsSlider();
    } catch (err) {
      console.error('Mahsulotlar yuklashda xatolik:', err);
      if (!silent && state.products.length === 0) {
        state.products = [];
        renderProducts();
        renderDiscountsSlider();
      }
    } finally {
      state.isLoading = false;
    }
  }

  function renderSkeleton() {
    if (!productsGridEl) return;
    emptyStateEl?.classList.add('hidden');
    if (resultsCountEl) resultsCountEl.textContent = '...';

    productsGridEl.innerHTML = `
      <div class="skeleton-card"><div class="skeleton-img"></div><div class="skeleton-body"><div class="skeleton-line skeleton-title"></div><div class="skeleton-line skeleton-price"></div><div class="skeleton-line skeleton-btn"></div></div></div>
      <div class="skeleton-card"><div class="skeleton-img"></div><div class="skeleton-body"><div class="skeleton-line skeleton-title"></div><div class="skeleton-line skeleton-price"></div><div class="skeleton-line skeleton-btn"></div></div></div>
    `;
  }

  // Zero-Flicker Memoized Bosh Sahifa Gridi
  let lastRenderedSignature = '';
  function renderProducts(force = false) {
    if (!productsGridEl) return;
    const { minUsd, maxUsd } = getActivePriceFilterUsd();
    const hasPriceFilter = minUsd !== null || maxUsd !== null;
    const isSearching = Boolean(state.searchQuery && state.searchQuery.trim().length > 0);
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.toggle('hidden', isSearching || hasPriceFilter);
    }
    if (sectionTitleEl) {
      if (isSearching) {
        sectionTitleEl.textContent = t('search_results');
      } else if (hasPriceFilter) {
        sectionTitleEl.textContent = t('filter_price_title');
      } else {
        sectionTitleEl.textContent = t('popular_products');
      }
    }
    let products = state.products || [];
    if (minUsd !== null) {
      products = products.filter(p => p.price >= minUsd);
    }
    if (maxUsd !== null) {
      products = products.filter(p => p.price <= maxUsd);
    }
    if (!isSearching && (!state.selectedSort || state.selectedSort === 'default')) {
      // Bosh sahifada ham oxirida yuklanganlar bir joyda qolib ketmasligi uchun toifalar aralash holda ko'rsatiladi
      products = getMixedCatalogProducts(products);
    }

    if (!products || products.length === 0) {
      lastRenderedSignature = 'empty_home_' + (hasPriceFilter ? 'f' : '');
      productsGridEl.innerHTML = '';
      emptyStateEl?.classList.remove('hidden');
      if (resultsCountEl) resultsCountEl.textContent = `0 ${t('items_suffix')}`;
      return;
    }

    emptyStateEl?.classList.add('hidden');
    if (resultsCountEl) resultsCountEl.textContent = `${products.length} ${t('items_suffix')}`;

    const signature = 'home_' + (hasPriceFilter ? 'f_' : '') + products.map(p => `${p.id}:${p.price}:${state.wishlist.has(p.id)}`).join(',');
    if (!force && signature === lastRenderedSignature) {
      return;
    }
    lastRenderedSignature = signature;

    let html = '';
    products.forEach(p => {
      const isFav = state.wishlist.has(p.id);
      const brand = p.name.toLowerCase().includes('macbook') || p.name.toLowerCase().includes('iphone') ? 'APPLE' : 'PREMIUM';

      html += `
        <article class="product-card" data-id="${p.id}">
          <div class="card-media">
            <button class="wishlist-btn ${isFav ? 'active' : ''}" data-id="${p.id}" aria-label="Sevimlilar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="${isFav ? '#ef4444' : 'none'}" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
            ${Number(p.is_discount) === 1 ? `
              <div class="gift-badge" title="Hafta chegirmasi">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 12 20 22 4 22 4 12"></polyline>
                  <rect x="2" y="7" width="20" height="5"></rect>
                  <line x1="12" y1="22" x2="12" y2="7"></line>
                  <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                  <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
                </svg>
              </div>
            ` : ''}
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="product-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="card-body">
            <span class="product-brand">${brand}</span>
            <h3 class="product-title">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            ${renderProductPriceBlock(p)}
            <div class="card-actions-stack">
              ${getCartButtonHtml(p.id)}
              ${p.post_url ? `
                <button class="btn-channel-link btn-liquid" data-post-url="${p.post_url}" data-id="${p.id}" data-haptic="light">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m22 2-7 20-4-9-9-4Z"></path>
                    <path d="M22 2 11 13"></path>
                  </svg>
                  <span>${t('view_in_channel')}</span>
                </button>
              ` : '<div class="btn-channel-placeholder"></div>'}
            </div>
          </div>
        </article>
      `;
    });

    productsGridEl.innerHTML = html;
  }

  // Bosh sahifa grid hodisasi (Event Delegation)
  productsGridEl?.addEventListener('click', (e) => {
    const card = e.target.closest('.product-card');
    if (!card) return;
    const pid = parseInt(card.dataset.id, 10);
    const prod = state.products.find(x => x.id === pid);
    if (!prod) return;

    const wishlistBtn = e.target.closest('.wishlist-btn');
    if (wishlistBtn) {
      e.stopPropagation();
      toggleWishlist(prod, e);
      return;
    }

    const addCartBtn = e.target.closest('.btn-add-cart');
    if (addCartBtn) {
      e.stopPropagation();
      if (addCartBtn.classList.contains('btn-goto-order') || (state.cart && state.cart[pid])) {
        switchTab('cart');
        return;
      }
      handleAddToCart(prod, addCartBtn);
      return;
    }

    const channelBtn = e.target.closest('.btn-channel-link');
    if (channelBtn) {
      e.stopPropagation();
      openChannelPost(channelBtn.dataset.postUrl, pid);
      return;
    }

    openProductModal(prod);
  });

  // ==========================================================================
  // 10. HODISALAR VA TUGMALARNI ULASH
  // ==========================================================================
  // Pastki Dock hodisalari
  dockItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const tab = item.dataset.tab;
      if (!tab) return;
      triggerHaptic('light');

      if (tab === 'home') {
        switchTab('home');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      switchTab(tab);
    });
  });

  // Header elementlari
  logoBtnEl?.addEventListener('click', (e) => {
    e.preventDefault();
    triggerHaptic('light');
    const wrap = logoBtnEl.querySelector('.blur-text-wrap');
    if (wrap) {
      wrap.classList.add('replaying');
      void wrap.offsetWidth;
      wrap.classList.remove('replaying');
    }
    switchTab('home');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  btnHeaderCartEl?.addEventListener('click', (e) => {
    e.preventDefault();
    triggerHaptic('light');
    switchTab('cart');
  });


  // Doimiy Oq / Kunduzgi Rejim
  function initTheme() {
    document.documentElement.classList.add('light');
    const splashScreen = document.getElementById('splash-screen');
    if (!splashScreen || splashScreen.classList.contains('curtain-open') || splashScreen.style.display === 'none') {
      try {
        if (tg?.setHeaderColor) tg.setHeaderColor('#ffffff');
        if (tg?.setBackgroundColor) tg.setBackgroundColor('#ffffff');
      } catch (e) {}
    }
  }

  // ==========================================================================
  // NARX VA VALYUTA BO'YICHA QIDIRUV VA FILTR (USD & SO'M)
  // ==========================================================================
  function formatNumberSpace(n) {
    if (n === null || n === undefined || isNaN(n)) return '0';
    return Math.round(Number(n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function getActivePriceFilterUsd() {
    const { currency, min, max } = state.priceFilter || {};
    const hasMin = min !== null && min !== undefined && min !== '' && !isNaN(min);
    const hasMax = max !== null && max !== undefined && max !== '' && !isNaN(max);
    if (!hasMin && !hasMax) {
      return { minUsd: null, maxUsd: null };
    }
    const rate = state.currentUsdRate || 12850;
    const numMin = hasMin ? Number(min) : null;
    const numMax = hasMax ? Number(max) : null;
    if (currency === 'UZS') {
      return {
        minUsd: numMin !== null ? Math.max(1, Math.round(numMin / rate)) : null,
        maxUsd: numMax !== null ? Math.max(1, Math.round(numMax / rate)) : null
      };
    }
    return {
      minUsd: numMin,
      maxUsd: numMax
    };
  }

  function renderFilterQuickChips() {
    if (!filterQuickChipsEl) return;
    const curr = state.priceFilter.currency || 'USD';
    const chipsUsd = [
      { label: '< $500', min: null, max: 500 },
      { label: '$500 - $1 000', min: 500, max: 1000 },
      { label: '$1 000 - $1 500', min: 1000, max: 1500 },
      { label: '> $1 500', min: 1500, max: null },
      { label: t('price_range_all') || 'Barchasi', min: null, max: null }
    ];
    const chipsUzs = [
      { label: '< 6 mln', min: null, max: 6000000 },
      { label: '6 - 12 mln', min: 6000000, max: 12000000 },
      { label: '12 - 20 mln', min: 12000000, max: 20000000 },
      { label: '> 20 mln', min: 20000000, max: null },
      { label: t('price_range_all') || 'Barchasi', min: null, max: null }
    ];
    const list = curr === 'UZS' ? chipsUzs : chipsUsd;

    const curMin = filterPriceMinEl?.value ? Number(filterPriceMinEl.value) : null;
    const curMax = filterPriceMaxEl?.value ? Number(filterPriceMaxEl.value) : null;

    let html = '';
    list.forEach(c => {
      const isExactMatch = (c.min === curMin && c.max === curMax);
      const isAllMatch = (c.min === null && c.max === null && curMin === null && curMax === null);
      const isActive = isExactMatch || isAllMatch;
      html += `
        <button type="button" class="filter-quick-chip ${isActive ? 'active' : ''}" 
                data-min="${c.min !== null ? c.min : ''}" 
                data-max="${c.max !== null ? c.max : ''}">
          ${c.label}
        </button>
      `;
    });
    filterQuickChipsEl.innerHTML = html;

    filterQuickChipsEl.querySelectorAll('.filter-quick-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        triggerHaptic('light');
        const minAttr = btn.dataset.min;
        const maxAttr = btn.dataset.max;
        if (filterPriceMinEl) filterPriceMinEl.value = minAttr !== '' ? minAttr : '';
        if (filterPriceMaxEl) filterPriceMaxEl.value = maxAttr !== '' ? maxAttr : '';
        filterQuickChipsEl.querySelectorAll('.filter-quick-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        updateFilterPriceHint();
      });
    });
  }

  function updateFilterCurrencyUI(newCurr, convertValues = false) {
    const oldCurr = state.priceFilter.currency || 'USD';
    state.priceFilter.currency = newCurr;

    if (filterCurrencySwitcherEl) {
      filterCurrencySwitcherEl.querySelectorAll('.curr-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.currency === newCurr);
      });
    }

    const rate = state.currentUsdRate || 12850;
    if (pricePrefixMinEl) pricePrefixMinEl.textContent = newCurr === 'USD' ? '$' : 'soʻm';
    if (pricePrefixMaxEl) pricePrefixMaxEl.textContent = newCurr === 'USD' ? '$' : 'soʻm';

    if (filterPriceMinEl) {
      filterPriceMinEl.placeholder = newCurr === 'USD' ? '500' : '6 000 000';
    }
    if (filterPriceMaxEl) {
      filterPriceMaxEl.placeholder = newCurr === 'USD' ? '1 500' : '15 000 000';
    }

    if (convertValues && oldCurr !== newCurr) {
      const curMin = filterPriceMinEl?.value ? Number(filterPriceMinEl.value) : null;
      const curMax = filterPriceMaxEl?.value ? Number(filterPriceMaxEl.value) : null;
      if (newCurr === 'UZS') {
        if (curMin && filterPriceMinEl) filterPriceMinEl.value = Math.round(curMin * rate);
        if (curMax && filterPriceMaxEl) filterPriceMaxEl.value = Math.round(curMax * rate);
      } else {
        if (curMin && filterPriceMinEl) filterPriceMinEl.value = Math.round(curMin / rate);
        if (curMax && filterPriceMaxEl) filterPriceMaxEl.value = Math.round(curMax / rate);
      }
    }

    renderFilterQuickChips();
    updateFilterPriceHint();
  }

  function updateFilterPriceHint() {
    if (!filterPriceHintEl) return;
    const curr = state.priceFilter.currency || 'USD';
    const rate = state.currentUsdRate || 12850;
    const minVal = filterPriceMinEl?.value ? Number(filterPriceMinEl.value) : null;
    const maxVal = filterPriceMaxEl?.value ? Number(filterPriceMaxEl.value) : null;

    if (!minVal && !maxVal) {
      filterPriceHintEl.classList.add('hidden');
      filterPriceHintEl.innerHTML = '';
      return;
    }

    filterPriceHintEl.classList.remove('hidden');
    if (curr === 'USD') {
      const minUzs = minVal ? `${formatNumberSpace(minVal * rate)} soʻm` : '0';
      const maxUzs = maxVal ? `${formatNumberSpace(maxVal * rate)} soʻm` : '∞';
      filterPriceHintEl.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        <span>≈ <strong>${minUzs} — ${maxUzs}</strong> (MB kursi: 1$ = ${formatNumberSpace(rate)} soʻm)</span>
      `;
    } else {
      const minUsd = minVal ? `$${formatNumberSpace(minVal / rate)}` : '$0';
      const maxUsd = maxVal ? `$${formatNumberSpace(maxVal / rate)}` : '∞';
      filterPriceHintEl.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        <span>≈ <strong>${minUsd} — ${maxUsd}</strong> (MB kursi: 1$ = ${formatNumberSpace(rate)} soʻm)</span>
      `;
    }
  }

  function updateActiveFilterBadges() {
    const { minUsd, maxUsd } = getActivePriceFilterUsd();
    const isFilterActive = minUsd !== null || maxUsd !== null;

    btnOpenFilterEl?.classList.toggle('has-filter', isFilterActive);

    if (!isFilterActive) {
      activeFilterBarEl?.classList.add('hidden');
      catalogActiveFilterBarEl?.classList.add('hidden');
      return;
    }

    const { currency, min, max } = state.priceFilter;
    let label = '';
    if (currency === 'UZS') {
      const sMin = min ? formatNumberSpace(min) : '0';
      const sMax = max ? formatNumberSpace(max) : '∞';
      label = `${sMin} — ${sMax} soʻm`;
    } else {
      const sMin = min ? `$${formatNumberSpace(min)}` : '$0';
      const sMax = max ? `$${formatNumberSpace(max)}` : '∞';
      label = `${sMin} — ${sMax}`;
    }

    if (activeFilterTextEl) activeFilterTextEl.textContent = label;
    if (catalogActiveFilterTextEl) catalogActiveFilterTextEl.textContent = label;
    activeFilterBarEl?.classList.remove('hidden');
    catalogActiveFilterBarEl?.classList.remove('hidden');
  }

  function clearPriceFilter() {
    triggerHaptic('light');
    state.priceFilter = {
      currency: 'USD',
      min: null,
      max: null
    };
    if (filterPriceMinEl) filterPriceMinEl.value = '';
    if (filterPriceMaxEl) filterPriceMaxEl.value = '';
    updateFilterCurrencyUI('USD', false);
    updateActiveFilterBadges();
    loadProducts();
  }

  // Drawers (Menyu & Filtr)
  function openLeftMenu() {
    triggerHaptic('light');
    closeAllDrawers();
    leftDrawerEl?.classList.add('active');
    backdropEl?.classList.add('active');
  }

  function openFilter() {
    triggerHaptic('light');
    closeAllDrawers();
    updateFilterCurrencyUI(state.priceFilter.currency || 'USD', false);
    if (filterPriceMinEl) filterPriceMinEl.value = state.priceFilter.min !== null && state.priceFilter.min !== undefined ? state.priceFilter.min : '';
    if (filterPriceMaxEl) filterPriceMaxEl.value = state.priceFilter.max !== null && state.priceFilter.max !== undefined ? state.priceFilter.max : '';
    updateFilterPriceHint();
    const sortRadio = bottomFilterEl?.querySelector(`input[name="sort"][value="${state.selectedSort}"]`);
    if (sortRadio) sortRadio.checked = true;
    bottomFilterEl?.classList.add('active');
    backdropEl?.classList.add('active');
  }

  function closeAllDrawers() {
    leftDrawerEl?.classList.remove('active');
    bottomFilterEl?.classList.remove('active');
    backdropEl?.classList.remove('active');
  }

  btnOpenMenuEl?.addEventListener('click', openLeftMenu);
  btnCloseMenuEl?.addEventListener('click', closeAllDrawers);
  btnOpenFilterEl?.addEventListener('click', openFilter);
  btnCloseFilterEl?.addEventListener('click', closeAllDrawers);
  backdropEl?.addEventListener('click', closeAllDrawers);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllDrawers();
  });

  // Qidiruv
  let debounceTimer = null;
  searchInputEl?.addEventListener('input', (e) => {
    const val = e.target.value;
    state.searchQuery = val;
    const isSearching = Boolean(val && val.trim().length > 0);
    clearSearchBtnEl?.classList.toggle('hidden', !isSearching);

    // Qidiruv boshlanishi bilanoq Hafta chegirmalarini darhol yashirish
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.toggle('hidden', isSearching);
    }
    if (sectionTitleEl) {
      sectionTitleEl.textContent = isSearching ? t('search_results') : t('popular_products');
    }

    if (state.currentTab !== 'home' && state.currentTab !== 'catalog') {
      switchTab('home');
    }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      loadProducts();
    }, 320);
  });

  clearSearchBtnEl?.addEventListener('click', () => {
    triggerHaptic('light');
    if (searchInputEl) searchInputEl.value = '';
    state.searchQuery = '';
    clearSearchBtnEl?.classList.add('hidden');
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.remove('hidden');
    }
    if (sectionTitleEl) {
      sectionTitleEl.textContent = t('popular_products');
    }
    loadProducts();
    searchInputEl?.blur();
  });

  // ==========================================================================
  // MOBIL KLAVIATURA VA PASTKI DOCK BOSHQARUVI (Anti-Jumping & Auto-Dismiss)
  // ==========================================================================
  let dockRestoreTimer = null;

  function hideDockForKeyboard() {
    clearTimeout(dockRestoreTimer);
    document.body.classList.add('search-focused', 'keyboard-open');
    if (mobileDockEl) {
      mobileDockEl.classList.add('dock-hidden-keyboard');
    }
  }

  function showDockAfterKeyboard() {
    document.body.classList.remove('search-focused');
    clearTimeout(dockRestoreTimer);
    dockRestoreTimer = setTimeout(() => {
      // Faqatgina qidiruv yoki boshqa input faol bo'lmaganda dock qaytariladi
      if (document.activeElement !== searchInputEl && !isKeyboardOpenByViewport()) {
        document.body.classList.remove('keyboard-open');
        if (mobileDockEl) {
          mobileDockEl.classList.remove('dock-hidden-keyboard');
        }
      }
    }, 140);
  }

  function isKeyboardOpenByViewport() {
    if (window.visualViewport) {
      return (window.innerHeight - window.visualViewport.height) > 120;
    }
    return false;
  }

  // Qidiruv maydoniga bosilishi bilanoq pastki dock tugmasi sakrab chiqmasligi uchun darhol yashiriladi
  searchInputEl?.addEventListener('focus', hideDockForKeyboard);
  searchInputEl?.addEventListener('touchstart', hideDockForKeyboard, { passive: true });
  searchInputEl?.addEventListener('pointerdown', hideDockForKeyboard, { passive: true });
  searchInputEl?.addEventListener('blur', showDockAfterKeyboard);

  // Enter / Go / Search tugmasi bosilganda ham klaviaturani silliq yopish
  searchInputEl?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      searchInputEl.blur();
    }
  });

  // Visual Viewport kuzatuvchisi (iOS Safari / Android Chrome / Telegram WebApp klaviatura o'lchamini kuzatish)
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', () => {
      if (isKeyboardOpenByViewport()) {
        hideDockForKeyboard();
      } else {
        if (document.activeElement !== searchInputEl) {
          showDockAfterKeyboard();
        }
      }
    });
  }

  // Qidiruv yozilgandan so'ng pastga yoki boshqa tarafga scroll qilinganda klaviaturani yo'q qilish
  let searchTouchStartY = 0;
  let searchTouchStartX = 0;
  let searchIsTouching = false;

  document.addEventListener('touchstart', (e) => {
    if (e.touches && e.touches.length > 0) {
      searchTouchStartY = e.touches[0].clientY;
      searchTouchStartX = e.touches[0].clientX;
      searchIsTouching = true;
    }
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (!searchIsTouching || !e.touches || e.touches.length === 0) return;
    if (document.activeElement !== searchInputEl) return;

    const currentY = e.touches[0].clientY;
    const currentX = e.touches[0].clientX;
    const diffY = searchTouchStartY - currentY; // diffY > 0 foydalanuvchi barmoqni tepaga surib pastga scrol qilganda
    const diffX = Math.abs(currentX - searchTouchStartX);

    // Qidiruv maydonining o'zida matn kursori surilmayotgan bo'lsa
    const isDirectInput = (e.target === searchInputEl || searchInputEl?.contains(e.target));
    const threshold = isDirectInput ? 28 : 6;

    // Pastga (yoki yuqoriga) scrol harakati sezilganda klaviatura darhol yopiladi
    if (Math.abs(diffY) > threshold && Math.abs(diffY) > diffX) {
      searchInputEl.blur();
    }
  }, { passive: true });

  document.addEventListener('touchend', () => {
    searchIsTouching = false;
  }, { passive: true });

  // Native scroll hodisasi (sahifa yoki asosiy kontent harakatlanganda)
  let lastScrollY = window.scrollY || document.documentElement.scrollTop || 0;
  const onPageScroll = () => {
    if (document.activeElement === searchInputEl) {
      const currentScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      if (Math.abs(currentScrollY - lastScrollY) > 5) {
        searchInputEl.blur();
      }
      lastScrollY = currentScrollY;
    } else {
      lastScrollY = window.scrollY || document.documentElement.scrollTop || 0;
    }
  };

  window.addEventListener('scroll', onPageScroll, { passive: true });
  document.addEventListener('scroll', onPageScroll, { passive: true });
  document.getElementById('mainContent')?.addEventListener('scroll', () => {
    if (document.activeElement === searchInputEl) {
      searchInputEl.blur();
    }
  }, { passive: true });

  // Qidiruv ochiq paytda boshqa joyga (masalan fon yoki mahsulot kartasiga) teginilganda klaviaturani yopish
  document.addEventListener('click', (e) => {
    if (document.activeElement === searchInputEl) {
      if (e.target !== searchInputEl && !clearSearchBtnEl?.contains(e.target)) {
        searchInputEl.blur();
      }
    }
  });

  resetFiltersBtnEl?.addEventListener('click', () => {
    triggerHaptic('medium');
    state.selectedCategory = 0;
    state.selectedSort = 'default';
    state.searchQuery = '';
    state.searchCurrencyMode = 'USD';
    state.priceFilter = { currency: 'USD', min: null, max: null };
    if (filterPriceMinEl) filterPriceMinEl.value = '';
    if (filterPriceMaxEl) filterPriceMaxEl.value = '';
    updateActiveFilterBadges();
    if (searchInputEl) {
      searchInputEl.value = '';
      searchInputEl.placeholder = t('search_placeholder');
    }
    clearSearchBtnEl?.classList.add('hidden');
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.remove('hidden');
    }
    if (sectionTitleEl) {
      sectionTitleEl.textContent = t('popular_products');
    }
    catalogCategorySliderEl?.querySelectorAll('.category-pill').forEach(p => {
      p.classList.toggle('active', p.dataset.category === '0');
    });
    loadProducts();
  });

  // Saralash va Narx bo'yicha filtr (Apply / Reset)
  btnApplyFilterEl?.addEventListener('click', () => {
    triggerHaptic('medium');
    const checked = bottomFilterEl?.querySelector('input[name="sort"]:checked');
    if (checked) {
      state.selectedSort = checked.value;
    }
    const minVal = filterPriceMinEl?.value ? parseFloat(filterPriceMinEl.value) : null;
    const maxVal = filterPriceMaxEl?.value ? parseFloat(filterPriceMaxEl.value) : null;
    state.priceFilter.min = minVal && minVal > 0 ? minVal : null;
    state.priceFilter.max = maxVal && maxVal > 0 ? maxVal : null;

    updateActiveFilterBadges();
    closeAllDrawers();
    loadProducts();
  });

  btnResetFilterEl?.addEventListener('click', () => {
    triggerHaptic('medium');
    state.selectedSort = 'default';
    const defRadio = bottomFilterEl?.querySelector('input[name="sort"][value="default"]');
    if (defRadio) defRadio.checked = true;
    clearPriceFilter();
    closeAllDrawers();
  });

  btnRemoveActiveFilterEl?.addEventListener('click', () => {
    clearPriceFilter();
  });

  btnRemoveCatalogActiveFilterEl?.addEventListener('click', () => {
    clearPriceFilter();
  });

  filterCurrencySwitcherEl?.querySelectorAll('.curr-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetCurr = btn.dataset.currency;
      if (!targetCurr || targetCurr === state.priceFilter.currency) return;
      triggerHaptic('light');
      updateFilterCurrencyUI(targetCurr, true);
    });
  });

  filterPriceMinEl?.addEventListener('input', updateFilterPriceHint);
  filterPriceMaxEl?.addEventListener('input', updateFilterPriceHint);

  // Chap Yon Menyu (Sidebar) linklari
  leftDrawerEl?.querySelectorAll('.nav-link-row').forEach(link => {
    link.addEventListener('click', (e) => {
      const action = link.dataset.action;
      if (!action) return;
      e.preventDefault();
      closeAllDrawers();

      if (action === 'all') {
        switchTab('home');
      } else if (action === 'cat-1') {
        switchTab('catalog', 1);
      } else if (action === 'cat-2') {
        switchTab('catalog', 2);
      } else if (action === 'cat-3') {
        switchTab('catalog', 3);
      } else if (action === 'wishlist') {
        switchTab('wishlist');
      } else if (action === 'cart') {
        switchTab('cart');
      } else if (action === 'contact') {
        switchTab('profile');
      }
    });
  });

  // Toast
  let toastTimer = null;
  function showToast(msg) {
    if (!toastEl || !toastMsgEl) return;
    toastMsgEl.textContent = msg;
    toastEl.classList.remove('hidden');
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove('show');
      toastEl.classList.add('hidden');
    }, 2200);
  }

  // Til almashtirish hodisalari
  btnLangSwitchEl?.addEventListener('click', () => {
    triggerHaptic('light');
    const langs = ['uz', 'ru', 'en'];
    const currentIdx = langs.indexOf(state.lang);
    const nextLang = langs[(currentIdx + 1) % langs.length];
    applyLanguage(nextLang);
  });

  document.querySelectorAll('.drawer-lang-selector .lang-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      triggerHaptic('light');
      applyLanguage(chip.dataset.lang);
    });
  });

  document.querySelectorAll('.profile-lang-chips .profile-lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      triggerHaptic('light');
      applyLanguage(btn.dataset.lang);
    });
  });

  // Hafta chegirmalari navigatsiyasi (Katalogga o'tish)
  dealsTitleGroupEl?.addEventListener('click', () => {
    switchTab('catalog');
  });

  btnDiscountsSeeAllEl?.addEventListener('click', () => {
    switchTab('catalog');
  });

  // ==========================================================================
  // PARDA (CURTAIN REVEAL) INTRO ANIMATSIYASI
  // ==========================================================================
  function initSplashScreen() {
    const splashScreen = document.getElementById('splash-screen');
    const splashSkipBtn = document.getElementById('splashSkipBtn');
    if (!splashScreen) return;

    if (sessionStorage.getItem('demostore_intro_shown') === 'true' || splashScreen.classList.contains('curtain-open')) {
      splashScreen.style.display = 'none';
      return;
    }

    let isDismissed = false;
    function openCurtains() {
      if (isDismissed) return;
      isDismissed = true;

      triggerHaptic('light');

      if (typeof window.dismissIntroCurtains === 'function') {
        window.dismissIntroCurtains();
      } else {
        splashScreen.classList.add('curtain-open');
        splashScreen.style.pointerEvents = 'none';
        setTimeout(() => {
          splashScreen.style.display = 'none';
        }, 1100);
      }
    }

    splashSkipBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      openCurtains();
    });

    splashScreen.addEventListener('click', openCurtains);

    // 2.4 soniya davomida Apple 3D logo va BlurText to'liq ko'rinib, pardalar silliq ochiladi
    setTimeout(openCurtains, 2400);
  }

  // Katalogda narx bo'yicha qidirish ($ Dan - $ Gacha)
  function setupCatalogPriceFilter() {
    const minInput = document.getElementById('catalogPriceMin');
    const maxInput = document.getElementById('catalogPriceMax');
    const resetBtn = document.getElementById('btnCatalogResetPrice');

    function onPriceChange() {
      const minVal = minInput?.value ? parseFloat(minInput.value) : null;
      const maxVal = maxInput?.value ? parseFloat(maxInput.value) : null;
      state.catalogPriceFilter = {
        min: minVal && minVal > 0 ? minVal : null,
        max: maxVal && maxVal > 0 ? maxVal : null
      };
      const hasVal = Boolean(state.catalogPriceFilter.min || state.catalogPriceFilter.max);
      resetBtn?.classList.toggle('hidden', !hasVal);
      renderCatalog();
    }

    minInput?.addEventListener('input', onPriceChange);
    maxInput?.addEventListener('input', onPriceChange);

    resetBtn?.addEventListener('click', () => {
      triggerHaptic('light');
      if (minInput) minInput.value = '';
      if (maxInput) maxInput.value = '';
      state.catalogPriceFilter = { min: null, max: null };
      resetBtn.classList.add('hidden');
      renderCatalog();
    });
  }

  // ==========================================================================
  // ADMIN HUQUQINI TEKSHIRISH
  // ==========================================================================
  async function checkAdminAccess() {
    try {
      const res = await apiFetch('/api/admin/check');
      if (res && res.ok) {
        const data = await res.json();
        if (data && data.is_admin) {
          const btn = document.getElementById('btnHeaderAdmin');
          const navAdmin = document.getElementById('navLinkAdmin');
          btn?.classList.remove('hidden');
          navAdmin?.classList.remove('hidden');

          const token = data.admin_token || '';
          const adminUrl = token ? `/admin?token=${encodeURIComponent(token)}` : '/admin';

          if (btn) {
            btn.href = adminUrl;
            btn.addEventListener('click', (e) => {
              e.preventDefault();
              window.location.href = adminUrl;
            });
          }

          if (navAdmin) {
            navAdmin.href = adminUrl;
            navAdmin.addEventListener('click', (e) => {
              e.preventDefault();
              window.location.href = adminUrl;
            });
          }
        }
      }
    } catch (e) {
      // Admin emas yoki aloqa xatosi
    }
  }

  // ==========================================================================
  // INITSIALIZATSIYA
  // ==========================================================================
  function boot() {
    initTheme();
    updateSafeArea();
    updateHeaderHeight();
    applyLanguage(state.lang);
    updateWishlistBadge();
    updateCartBadges();
    setupCatalogPriceFilter();
    updateFilterCurrencyUI('USD', false);
    updateActiveFilterBadges();
    checkAdminAccess();

    // 1. Agar keshda mahsulotlar bo'lsa — darhol 0ms da chizish!
    const hasCache = Boolean(state.products && state.products.length > 0);
    if (hasCache) {
      updateLiveUsdBadge(state.currentUsdRate);
      renderProducts();
      renderDiscountsSlider();
    }

    // 2. Pardani ochish (foydalanuvchi kutib qolmasligi uchun)
    initSplashScreen();

    // 3. Yangi ma'lumotlarni fonda sokin yangilash (kesh bo'lsa, silent = true)
    loadProducts(hasCache);
    fetchLiveCurrencyRate();

    // 60 soniyalik sokin fon yangilanishi
    setInterval(() => {
      if (!state.isLoading && !state.searchQuery.trim() && state.currentTab === 'home') {
        loadProducts(true);
      }
    }, 60000);

    // Har 10 daqiqada valyuta kursini sokin yangilab turish (10-15 daqiqalik yengil kesh)
    setInterval(() => {
      fetchLiveCurrencyRate();
    }, 10 * 60 * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
