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

  // Narxni joriy jonli dollar kursi bo'yicha so'mda chiqarish
  function formatPriceUzs(amountUsd) {
    if (!amountUsd) return '0 soʻm';
    const rate = state?.currentUsdRate || 12850;
    const uzs = Math.round(amountUsd * rate);
    return uzs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' soʻm';
  }

  // Sarlavhadagi jonli kurs belgisini (badge) yangilash (foydalanuvchi talabiga ko'ra o'chirildi)
  function updateLiveUsdBadge(rate) {
    const el = document.getElementById('liveUsdBadge');
    if (el) el.style.display = 'none';
  }

  // Markaziy Bank kursini API orqali olish
  async function fetchLiveCurrencyRate() {
    try {
      const res = await fetch('/api/currency');
      if (res.ok) {
        const data = await res.json();
        if (data && data.rate) {
          state.currentUsdRate = data.rate;
          updateLiveUsdBadge(data.rate);
          // Agar mahsulotlar allaqachon yuklangan bo'lsa, narxlarni qayta render qilish
          if (state.products && state.products.length > 0) {
            if (typeof renderProducts === 'function') renderProducts(true);
            if (typeof renderCatalogProducts === 'function') renderCatalogProducts();
            if (typeof renderDiscountsSlider === 'function') renderDiscountsSlider();
            if (typeof renderCartSection === 'function') renderCartSection();
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
      const cleanVal = stripAllEmojis(val);
      if (!cleanVal) return;
      const cleanKey = stripAllEmojis(key);
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
      if (raw.includes('📦') || lower.includes('box') || lower.includes('karobka')) {
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

      // 8. Kafolat
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
        const val = stripAllEmojis(raw.replace(/^(?:protsessor|chip)[:\s]*/i, '').replace(/^[^\w\d]+/, ''));
        if (val) {
          addSpec('Protsessor', val);
          return;
        }
      }

      // 11. Ekran
      if (lower.includes('ekran') || lower.includes('display')) {
        const val = stripAllEmojis(raw.replace(/^(?:ekran|display)[:\s]*/i, '').replace(/^[^\w\d]+/, ''));
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

  // Toifa bo'yicha qat'iy va xatosiz filtrlash (Noutbuklar hech qachon smartfonga kirmaydi)
  function isProductInCategory(p, catId) {
    if (!catId || catId === 0) return true;
    const name = (p.name || '').toLowerCase();
    const catName = (p.category_name || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();

    // 1. SMARTFONLAR (Smartphones)
    if (catId === 1) {
      if (name.includes('macbook') || name.includes('surface') || name.includes('asus') || name.includes('laptop') || name.includes('noutbuk')) {
        return false;
      }
      if (p.category_id === 1) return true;
      if (catName.includes('smartfon') || name.includes('iphone') || name.includes('samsung') || name.includes('galaxy') || name.includes('redmi') || desc.includes('iphone')) {
        return true;
      }
      return false;
    }

    // 2. NOUTBUKLAR (Laptops)
    if (catId === 2) {
      if (name.includes('iphone') || name.includes('smartfon') || name.includes('redmi') || name.includes('galaxy')) {
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
      return p.category_id === 3 || catName.includes('audio') || name.includes('airpods') || name.includes('quloqchin') || name.includes('naushnik');
    }

    // 4. AQLLI SOATLAR
    if (catId === 4) {
      return p.category_id === 4 || catName.includes('soat') || name.includes('watch');
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
      add_to_cart: "Sotib olish",
      buy_now: "Sotib olish",
      go_to_order: "Buyurtmaga",
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
      add_to_cart: "Купить",
      buy_now: "Купить",
      go_to_order: "К заказу",
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
      add_to_cart: "Buy Now",
      buy_now: "Buy Now",
      go_to_order: "To Order",
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
    if (inCart) {
      pdAddToCartBtnEl.classList.add('btn-goto-order');
      pdAddToCartBtnEl.innerHTML = `
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span id="pdBtnText">${t('go_to_order')}</span>
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
      const pid = parseInt(btn.dataset.id, 10);
      const inCart = Boolean(state.cart && state.cart[pid]);
      if (inCart) {
        btn.classList.add('btn-goto-order');
        btn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          <span>${t('go_to_order')}</span>
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
      const pid = parseInt(btn.dataset.id, 10);
      const inCart = Boolean(state.cart && state.cart[pid]);
      if (inCart) {
        btn.classList.add('btn-goto-order');
        btn.innerHTML = `
          <span class="deal-cart-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </span>
          <span>${t('go_to_order')}</span>
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

    if (state.selectedProduct && pdAddToCartBtnEl) {
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

    // Dastlabki 8 ta mahsulotni haftalik chegirmalarga olamiz
    const discountItems = state.products.slice(0, 8);
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
              <div class="deal-current-price">
                ${formatPrice(p.price)}
                <span class="deal-price-uzs">≈ ${formatPriceUzs(p.price)}</span>
              </div>
              <div class="deal-old-price-row">
                <span class="deal-old-price">${formatPrice(oldPrice)}</span>
                <span class="deal-drop-tag">-${rate}%</span>
              </div>
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
    // Faqat mahsulot batafsil sahifasida Telegram BackButton ko'rsatiladi.
    // Asosiy bo'limlarda (Home, Catalog, Cart, Wishlist, Profile) Telegramning o'zini native "X" (Yopish) tugmasi turadi!
    if (tg?.BackButton) {
      try {
        if (state.currentTab === 'product-detail') {
          tg.BackButton.show();
        } else {
          tg.BackButton.hide();
        }
      } catch (e) {}
    }
  }

  function goBack() {
    triggerHaptic('light');

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

    // 3. Agar foydalanuvchi Bosh sahifada (home) bo'lmasa, Bosh sahifaga qaytish (1 qadam)
    if (state.currentTab !== 'home') {
      switchTab('home', null, false);
      return;
    }

    // 4. Agar allaqachon Bosh sahifada (home) turib chiqish qilinsa -> Telegram mini ilovani yopish!
    if (tg?.close) {
      try {
        tg.close();
      } catch (e) {}
    }
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
        pill.classList.toggle('active', parseInt(pill.dataset.category, 10) === state.selectedCategory);
      });
      renderCatalog();
    } else if (tabKey === 'cart') {
      renderCartSection();
    } else if (tabKey === 'wishlist') {
      renderWishlistSection();
    } else if (tabKey === 'profile') {
      renderProfileSection();
    }

    // Skroll holatini boshqarish
    if (restoreScroll) {
      const targetY = state.savedScroll[tabKey] || 0;
      setTimeout(() => {
        window.scrollTo({ top: targetY, behavior: 'instant' });
      }, 15);
    } else if (tabKey === 'product-detail') {
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }

  // Telegram native BackButton
  if (tg?.BackButton) {
    try {
      tg.BackButton.onClick(goBack);
    } catch (e) {}
  }

  // Brauzer / Android apparat tugmasi / iOS Safari popstate
  window.addEventListener('popstate', (e) => {
    // Agar foydalanuvchi mahsulot batafsil oynasida bo'lsa va orqaga sursa:
    if (state.currentTab === 'product-detail') {
      const returnTab = (state.previousTab && state.previousTab !== 'product-detail') ? state.previousTab : 'home';
      switchTab(returnTab, null, false, true);
    } else {
      goBack();
    }
  });

  // Klaviatura Escape tugmasi
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      goBack();
    }
  });

  // ==========================================================================
  // IPHONE SWIPE-TO-BACK GESTURE (Chap chetdan o'ngga surish orqali orqaga qaytish)
  // ==========================================================================
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;
  let isEdgeSwipeGesture = false;

  window.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1) return;
    const touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    isEdgeSwipeGesture = false;

    // Barmoq ekranning chap chekkasida (<= 75px) boshlansa:
    if (touchStartX <= 75) {
      isEdgeSwipeGesture = true;
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (!isEdgeSwipeGesture) return;
    const touch = e.touches[0];
    const diffX = touch.clientX - touchStartX;
    const diffY = Math.abs(touch.clientY - touchStartY);

    // Agar vertikal skroll ustun bo'lsa (diffY > 25 va diffY > diffX), jestni bekor qilamiz
    if (diffY > 25 && diffY > diffX) {
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

    // Gorizontal o'ngga surish: kamida 40px o'ngga surilsa va 700ms ichida bo'lsa
    if (diffX >= 40 && diffX > diffY * 1.05 && elapsed < 700) {
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

  // 2. Savatga qo'shish tugmasining "Buyurtmaga" holatiga jonli o'tish animatsiyasi
  function animateCartButton(btn) {
    if (!btn) return;
    btn.dataset.animating = 'true';
    btn.classList.add('btn-goto-order');

    // Tugma ichini darhol "Buyurtmaga" matni va belgilari bilan to'ldirish
    if (btn.classList.contains('pd-add-btn')) {
      btn.innerHTML = `
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span id="pdBtnText">${t('go_to_order')}</span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      `;
    } else if (btn.classList.contains('deal-cart-btn')) {
      btn.innerHTML = `
        <span class="deal-cart-icon">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </span>
        <span>${t('go_to_order')}</span>
      `;
    } else {
      btn.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
        <span>${t('go_to_order')}</span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
      `;
    }

    // Mayin tactile bosilish va elastik sakrash (Apple Spring bounce)
    btn.style.transform = 'scale(0.95)';
    btn.style.transition = 'transform 0.08s cubic-bezier(0.2, 0, 0, 1)';

    setTimeout(() => {
      btn.style.transform = 'scale(1.04)';
      btn.style.transition = 'transform 0.22s cubic-bezier(0.25, 1.4, 0.5, 1)';
      setTimeout(() => {
        btn.style.transform = '';
        btn.style.transition = '';
        btn.dataset.animating = 'false';
      }, 180);
    }, 60);

    triggerHaptic('success');
  }

  // 3. Telegram kanaldagi postni ochish funksiyasi
  function openChannelPost(postUrl, productId) {
    if (!postUrl) return;
    triggerHaptic('light');

    // Bazada statistika (views_count) ni oshirish
    if (productId) {
      try {
        fetch(`/api/products/${productId}/click`, { method: 'POST' }).catch(() => {});
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

    // A) Tugmani "Buyurtmaga" holatiga jonlantirish
    if (btn) animateCartButton(btn);

    // B) Bosilishi bilan bir vaqtda savat va nishon darhol elastik sakraydi (uchuvchi rasmsiz)
    triggerCartJump();
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
              ${formatPrice(p.price)}
              <span class="cart-item-uzs-sub">(${formatPriceUzs(p.price * item.qty)})</span>
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
      text += `${idx + 1}. ${p.name} — ${item.qty} dona x ${formatPrice(p.price)} = ${formatPrice(subtotal)} (${formatPriceUzs(subtotal)})\n`;
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
            <div class="price-wrap">
              <span class="price-current">${formatPrice(p.price)}</span>
              <span class="price-uzs">≈ ${formatPriceUzs(p.price)}</span>
            </div>
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
              ` : ''}
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
      renderCatalog();
    });
  });

  function renderCatalog() {
    if (!catalogProductsGridEl) return;
    let prods = state.products;
    if (state.selectedCategory > 0) {
      prods = prods.filter(p => isProductInCategory(p, state.selectedCategory));
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
            <button class="wishlist-btn ${isFav ? 'active' : ''}" data-id="${p.id}" aria-label="Sevimlilar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="${isFav ? '#ef4444' : 'none'}" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
              </svg>
            </button>
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="product-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="card-body">
            <span class="product-brand">${brand}</span>
            <h3 class="product-title">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            <div class="price-wrap">
              <span class="price-current">${formatPrice(p.price)}</span>
              <span class="price-uzs">≈ ${formatPriceUzs(p.price)}</span>
            </div>
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
              ` : ''}
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

    if (pdWishlistBtnEl) {
      pdWishlistBtnEl.classList.toggle('active', isFav);
    }
    if (pdBottomPriceEl) {
      pdBottomPriceEl.textContent = formatPrice(prod.price);
    }
    if (pdBottomPriceUzsEl) {
      pdBottomPriceUzsEl.textContent = `≈ ${formatPriceUzs(prod.price)}`;
    }

    let galleryHTML = `
      <div class="modal-gallery-wrap">
        <div class="modal-gallery-track" id="pdGalleryTrack">
          ${images.map((img, i) => `
            <div class="gallery-slide" data-index="${i}">
              <img src="${img}" alt="${escapeHtml(prod.name)}" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
            </div>
          `).join('')}
        </div>
        ${images.length > 1 ? `
          <div class="gallery-counter"><span id="pdGalleryCounter">1</span> / ${images.length}</div>
          <button class="gallery-arrow arrow-prev" id="pdGalleryPrevBtn" aria-label="Oldingi rasm">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m15 18-6-6 6-6"></path></svg>
          </button>
          <button class="gallery-arrow arrow-next" id="pdGalleryNextBtn" aria-label="Keyingi rasm">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m9 18 6-6-6-6"></path></svg>
          </button>
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
          <div class="pd-hero-usd">${formatPrice(prod.price)}</div>
          <div class="pd-hero-uzs">≈ ${formatPriceUzs(prod.price)}</div>
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
      ` : (prod.description ? `
        <div class="specs-container">
          <div class="specs-title">Mahsulot haqida maʼlumot</div>
          <p style="font-size: 0.85rem; color: var(--text-sub); line-height: 1.5; white-space: pre-line;">${escapeHtml(prod.description)}</p>
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

    // Kanaldan ko'rish tugmasi hodisasi
    document.getElementById('pdChannelViewBtn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (prod.post_url) {
        openChannelPost(prod.post_url, prod.id);
      }
    });

    // Karusel hodisalarini ulash
    if (images.length > 1) {
      const track = document.getElementById('pdGalleryTrack');
      const prevBtn = document.getElementById('pdGalleryPrevBtn');
      const nextBtn = document.getElementById('pdGalleryNextBtn');
      const counter = document.getElementById('pdGalleryCounter');
      const dots = document.querySelectorAll('#pdGalleryDots .dot');
      let currentIndex = 0;

      function updateSlide(idx) {
        if (idx < 0) idx = images.length - 1;
        if (idx >= images.length) idx = 0;
        currentIndex = idx;
        const slideWidth = track.clientWidth;
        track.scrollTo({ left: slideWidth * idx, behavior: 'smooth' });
        if (counter) counter.textContent = (idx + 1).toString();
        dots.forEach((d, i) => d.classList.toggle('active', i === idx));
      }

      prevBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        triggerHaptic('light');
        updateSlide(currentIndex - 1);
      });

      nextBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        triggerHaptic('light');
        updateSlide(currentIndex + 1);
      });

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
      });
    }

    const inCart = Boolean(state.cart && state.cart[prod.id]);
    updatePdCartButton(inCart);

    switchTab('product-detail');
  }

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

      const res = await fetch(`/api/products?${params.toString()}`);
      if (!res.ok) throw new Error('Mahsulotlar yuklanmadi');
      const data = await res.json();
      if (Array.isArray(data)) {
        state.products = data;
        if (data[0] && data[0].current_usd_rate) {
          state.currentUsdRate = data[0].current_usd_rate;
          updateLiveUsdBadge(data[0].current_usd_rate);
        }
      } else if (data && data.products) {
        state.products = data.products;
        if (data.current_usd_rate) {
          state.currentUsdRate = data.current_usd_rate;
          updateLiveUsdBadge(data.current_usd_rate);
        }
      }

      // Keshga saqlash (Keyingi ochilishda 0ms da yuklash uchun)
      if (!state.searchQuery.trim() && state.selectedCategory === 0 && (!state.selectedSort || state.selectedSort === 'default')) {
        try {
          localStorage.setItem('demostore_cached_products', JSON.stringify(state.products));
          localStorage.setItem('demostore_cached_usd_rate', String(state.currentUsdRate));
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
    const isSearching = Boolean(state.searchQuery && state.searchQuery.trim().length > 0);
    if (discountsSliderSectionEl) {
      discountsSliderSectionEl.classList.toggle('hidden', isSearching);
    }
    if (sectionTitleEl) {
      sectionTitleEl.textContent = isSearching ? t('search_results') : t('popular_products');
    }
    const products = state.products;

    if (!products || products.length === 0) {
      lastRenderedSignature = 'empty_home';
      productsGridEl.innerHTML = '';
      emptyStateEl?.classList.remove('hidden');
      if (resultsCountEl) resultsCountEl.textContent = `0 ${t('items_suffix')}`;
      return;
    }

    emptyStateEl?.classList.add('hidden');
    if (resultsCountEl) resultsCountEl.textContent = `${products.length} ${t('items_suffix')}`;

    const signature = 'home_' + products.map(p => `${p.id}:${p.price}:${state.wishlist.has(p.id)}`).join(',');
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
            <img src="${getProductImageUrl(p)}" alt="${escapeHtml(p.name)}" class="product-img" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='${FALLBACK_IMAGE_URL}';" />
          </div>
          <div class="card-body">
            <span class="product-brand">${brand}</span>
            <h3 class="product-title">${escapeHtml(getCleanCardTitle(p.name))}</h3>
            <div class="price-wrap">
              <span class="price-current">${formatPrice(p.price)}</span>
              <span class="price-uzs">≈ ${formatPriceUzs(p.price)}</span>
            </div>
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
              ` : ''}
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
    if (searchInputEl) searchInputEl.value = '';
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

  // Saralash (Sort)
  btnApplyFilterEl?.addEventListener('click', () => {
    triggerHaptic('medium');
    const checked = bottomFilterEl?.querySelector('input[name="sort"]:checked');
    if (checked) {
      state.selectedSort = checked.value;
    }
    closeAllDrawers();
    loadProducts();
  });

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
        }, 850);
      }
    }

    splashSkipBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      openCurtains();
    });

    splashScreen.addEventListener('click', openCurtains);

    // 1.2 soniya davomida Apple 3D logo ajoyib ko'rinib, pardalar ikki tarafga silliq ochiladi
    setTimeout(openCurtains, 1200);
  }

  // Interaktiv tugmalar (Liquid Glass, Bounce, Ripple, 3D, Loading) hodisalari
  function setupInteractiveButtonsDemo() {
    const btnLiquid = document.getElementById('btnLiquidDemo');
    const btnBounce = document.getElementById('btnBounceDemo');
    const btnRipple = document.getElementById('btnRippleDemo');
    const btn3d = document.getElementById('btn3dDemo');
    const btnLoading = document.getElementById('mySubmitBtn');

    btnLiquid?.addEventListener('click', () => {
      showToast('💎 Liquid Glass: Shaffof shisha va oquvchi nur effekti!');
    });

    btnBounce?.addEventListener('click', () => {
      showToast('⚡ Spring Bounce: Yumshoq elastik sakrash!');
    });

    btnRipple?.addEventListener('click', () => {
      showToast('🌊 Ripple Wave: Suv to‘lqini effekti!');
    });

    btn3d?.addEventListener('click', () => {
      showToast('🎮 3D Tactile: Duolingo chuqur bosilish effekti!');
    });

    btnLoading?.addEventListener('click', () => {
      if (window.MiniApp && typeof window.MiniApp.showLoading === 'function') {
        window.MiniApp.showLoading(btnLoading);
        setTimeout(() => {
          window.MiniApp.hideLoading(btnLoading);
          window.MiniApp.haptic('success');
          showToast('✅ Yuklanish muvaffaqiyatli yakunlandi!');
        }, 1400);
      }
    });
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
    setupInteractiveButtonsDemo();

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

    // 60 soniyalik sokin fon yangilanishi
    setInterval(() => {
      if (!state.isLoading && !state.searchQuery.trim() && state.currentTab === 'home') {
        loadProducts(true);
      }
    }, 60000);

    // Har 30 daqiqada valyuta kursini sokin yangilab turish
    setInterval(() => {
      fetchLiveCurrencyRate();
    }, 30 * 60 * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
