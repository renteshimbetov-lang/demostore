// DemoStore Admin Mini App — Pure White Apple Design & Zero Emojis
(function () {
  'use strict';

  const tg = window.Telegram?.WebApp;
  let currentAdminUser = null;
  let allProducts = [];
  let allCategories = [];
  let currentUsdRate = 12850;
  let activeStatusFilter = 'all';
  let activeCategoryFilter = 'all';
  let activeOrderFilter = 'all';

  // 1. Telegram WebApp Initsializatsiyasi & Safe Area O'lchovlari (Tepadagi ustma-ust tushishni to'liq yo'qotish)
  document.documentElement.classList.add('light');
  document.documentElement.style.colorScheme = 'light';
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (typeof tg.requestFullscreen === 'function') {
        tg.requestFullscreen();
      }
      if (typeof tg.disableVerticalSwipes === 'function') {
        tg.disableVerticalSwipes();
      }
      if (typeof tg.setHeaderColor === 'function') {
        tg.setHeaderColor('#ffffff');
      }
      if (typeof tg.setBackgroundColor === 'function') {
        tg.setBackgroundColor('#ffffff');
      }
      if (typeof tg.setBottomBarColor === 'function') {
        tg.setBottomBarColor('#ffffff');
      }
    } catch (e) {
      console.warn('Telegram init ogohlantirish:', e);
    }
  }

  function updateSafeArea() {
    try {
      const isTg = Boolean(window.Telegram?.WebApp?.initData || window.Telegram?.WebApp?.platform);
      const contentTop = Number(tg?.contentSafeAreaInset?.top) || 0;
      const safeTop = Number(tg?.safeAreaInset?.top) || 0;
      const isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

      let finalTop = 16;
      if (contentTop >= 60) {
        finalTop = contentTop + 6;
      } else if (safeTop > 0) {
        finalTop = safeTop + 44;
      } else if (isTg && isMobileDevice) {
        finalTop = 90;
      } else if (isTg) {
        finalTop = 20;
      }

      document.documentElement.style.setProperty('--admin-safe-top', `${finalTop}px`);

      const contentBottom = Number(tg?.contentSafeAreaInset?.bottom) || 0;
      const safeBottom = Number(tg?.safeAreaInset?.bottom) || 0;
      let finalBottom = Math.max(contentBottom, safeBottom, 18);
      document.documentElement.style.setProperty('--admin-safe-bottom', `${finalBottom}px`);
    } catch (e) {}
  }
  updateSafeArea();
  tg?.onEvent?.('safeAreaChanged', updateSafeArea);
  tg?.onEvent?.('contentSafeAreaChanged', updateSafeArea);
  tg?.onEvent?.('fullscreenChanged', updateSafeArea);
  tg?.onEvent?.('viewportChanged', updateSafeArea);
  window.addEventListener('resize', updateSafeArea);

  function triggerHaptic(type = 'light') {
    try {
      if (tg?.HapticFeedback) {
        if (type === 'selection') tg.HapticFeedback.selectionChanged();
        else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
        else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
        else tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {}
  }

  // 2. API So'rov Yordamchisi (InitData va Brauzer Admin Token bilan)
  let adminToken = '';
  try {
    const urlParams = new URLSearchParams(window.location.search);
    adminToken = urlParams.get('token') || urlParams.get('admin_token') || localStorage.getItem('admin_token') || '';
    if (adminToken) {
      localStorage.setItem('admin_token', adminToken);
    }
  } catch (e) {}

  async function apiFetch(url, options = {}) {
    const opts = { ...options };
    const headers = { ...(opts.headers || {}) };
    const initData = tg?.initData || '';
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }
    const token = adminToken || localStorage.getItem('admin_token') || '';
    if (token) {
      headers['X-Admin-Token'] = token;
    }
    opts.headers = headers;
    return fetch(url, opts);
  }

  // Toast Bildirishnoma
  let toastTimer = null;
  function showToast(msg, isSuccess = true) {
    const toast = document.getElementById('adminToast');
    const toastMsg = document.getElementById('adminToastMsg');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = msg;
    toast.classList.remove('hidden');
    triggerHaptic(isSuccess ? 'success' : 'error');

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.add('hidden');
    }, 2500);
  }

  function formatPrice(num) {
    return Number(num || 0).toLocaleString('uz-UZ') + " so'm";
  }

  function formatUsd(num) {
    return '$' + Number(num || 0).toLocaleString('en-US');
  }

  // 3. Tab Navigatsiyasi
  function initTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const targetTab = item.getAttribute('data-tab');
        switchTab(targetTab);
      });
    });

    const btnViewAllOrders = document.getElementById('btnViewAllOrders');
    if (btnViewAllOrders) {
      btnViewAllOrders.addEventListener('click', () => switchTab('tabOrders'));
    }

    const btnQuickAddProduct = document.getElementById('btnQuickAddProduct');
    if (btnQuickAddProduct) {
      btnQuickAddProduct.addEventListener('click', () => {
        switchTab('tabProducts');
        openProductModal();
      });
    }

    const btnQuickSyncChannel = document.getElementById('btnQuickSyncChannel');
    if (btnQuickSyncChannel) {
      btnQuickSyncChannel.addEventListener('click', runChannelSync);
    }

    const btnQuickChannelPost = document.getElementById('btnQuickChannelPost');
    if (btnQuickChannelPost) {
      btnQuickChannelPost.addEventListener('click', () => switchTab('tabChannel'));
    }
  }

  function switchTab(tabId) {
    triggerHaptic('selection');
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    const activePane = document.getElementById(tabId);
    if (activePane) {
      activePane.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });

      if (tabId === 'tabProducts' && allProducts.length === 0) {
        loadAdminProducts();
      } else if (tabId === 'tabOrders') {
        loadAdminOrders();
      } else if (tabId === 'tabDashboard') {
        loadDashboardData();
      }
    }
  }

  // 4. Admin Tekshiruvi
  async function checkAdminAuth() {
    try {
      const res = await apiFetch('/api/admin/check');
      if (!res.ok) {
        document.getElementById('unauthorizedScreen')?.classList.remove('hidden');
        document.getElementById('adminContent')?.classList.add('hidden');
        document.getElementById('adminBottomNav')?.classList.add('hidden');
        return false;
      }
      document.getElementById('unauthorizedScreen')?.classList.add('hidden');
      document.getElementById('adminContent')?.classList.remove('hidden');
      document.getElementById('adminBottomNav')?.classList.remove('hidden');

      const data = await res.json();
      currentAdminUser = data.user;
      if (data.admin_token) {
        adminToken = data.admin_token;
        try {
          localStorage.setItem('admin_token', data.admin_token);
        } catch (e) {}
      }
      
      const adminNameEl = document.getElementById('adminGreeting');
      if (adminNameEl && currentAdminUser) {
        adminNameEl.textContent = currentAdminUser.first_name || 'Admin';
      }
      return true;
    } catch (e) {
      console.error('Admin tekshiruvida xatolik:', e);
      document.getElementById('unauthorizedScreen')?.classList.remove('hidden');
      document.getElementById('adminContent')?.classList.add('hidden');
      document.getElementById('adminBottomNav')?.classList.add('hidden');
      return false;
    }
  }

  // 5. Dashboard Ma'lumotlarini Yuklash
  async function loadDashboardData() {
    try {
      const res = await apiFetch('/api/admin/dashboard');
      if (!res.ok) return;
      const data = await res.json();

      currentUsdRate = data.current_usd_rate || 12850;
      document.getElementById('dashRateValue').textContent = `1$ = ${Number(currentUsdRate).toLocaleString('uz-UZ')} so'm`;

      const stats = data.stats || {};
      document.getElementById('statRevenue').textContent = formatPrice(stats.total_revenue);
      document.getElementById('statTodayRevenue').textContent = `Bugun: ${formatPrice(stats.today_revenue)}`;
      
      document.getElementById('statOrders').textContent = `${stats.orders_count || 0} ta`;
      document.getElementById('statTodayOrders').textContent = `Bugun: ${stats.today_orders || 0} ta yangi`;

      document.getElementById('statProducts').textContent = `${stats.products_count || 0} ta`;
      document.getElementById('statDiscounts').textContent = `Chegirmalar: ${stats.discount_count || 0} ta`;

      document.getElementById('statUsers').textContent = `${stats.users_count || 0} nafar`;

      if (data.channel) {
        document.getElementById('channelUsernameText').textContent = data.channel.username ? `@${data.channel.username}` : 'Noma\'lum';
        document.getElementById('channelIdText').textContent = data.channel.id || '-';
        const linkBtn = document.getElementById('channelLinkBtn');
        if (linkBtn && data.channel.url) {
          linkBtn.href = data.channel.url;
        }
      }

      renderTopProducts(data.top_products || []);
      renderRecentOrders(data.recent_orders || []);
    } catch (e) {
      console.error('Dashboard yuklashda xatolik:', e);
    }
  }

  function renderTopProducts(products) {
    const container = document.getElementById('topProductsList');
    if (!container) return;

    if (!products || products.length === 0) {
      container.innerHTML = '<div class="loading-spinner">Hozircha ko\'rishlar mavjud emas.</div>';
      return;
    }

    container.innerHTML = products.map((p, idx) => `
      <div class="top-item">
        <div class="top-item-left">
          <span class="top-rank rank-${idx + 1}">${idx + 1}</span>
          <span class="top-name">${p.name}</span>
        </div>
        <div class="top-views">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
          <span>${p.views_count || 0}</span>
        </div>
      </div>
    `).join('');
  }

  function renderRecentOrders(orders) {
    const container = document.getElementById('recentOrdersList');
    if (!container) return;

    if (!orders || orders.length === 0) {
      container.innerHTML = '<div class="loading-spinner">Hozircha buyurtmalar yo\'q.</div>';
      return;
    }

    container.innerHTML = orders.slice(0, 5).map(o => `
      <div class="top-item">
        <div class="top-item-left">
          <span class="status-badge badge-active">${o.status}</span>
          <span class="top-name">#${o.id} • ${o.full_name || 'Mijoz'}</span>
        </div>
        <span class="stat-num" style="font-size: 13px;">${formatPrice(o.total_amount)}</span>
      </div>
    `).join('');
  }

  // 6. Mahsulotlarni Boshqarish (Products Tab)
  async function loadAdminProducts() {
    const container = document.getElementById('adminProductsContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading-spinner">Mahsulotlar yuklanmoqda...</div>';

    try {
      const search = document.getElementById('adminSearchInput')?.value.trim() || '';
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (activeStatusFilter !== 'all') params.append('status', activeStatusFilter);
      if (activeCategoryFilter !== 'all') params.append('category_id', activeCategoryFilter);

      const res = await apiFetch(`/api/admin/products?${params.toString()}`);
      if (!res.ok) throw new Error('Yuklab bo\'lmadi');
      const data = await res.json();

      allProducts = data.products || [];
      allCategories = data.categories || [];
      currentUsdRate = data.current_usd_rate || currentUsdRate;
      const totalInactive = data.inactive_count !== undefined ? data.inactive_count : (allProducts || []).filter(p => Number(p.is_active) === 0).length;

      // Nofaol pill tagini dinamik ko'rsatish
      const inactivePill = document.querySelector('.filter-pill[data-status="inactive"]');
      if (inactivePill) {
        inactivePill.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
          <span>Nofaol ${totalInactive > 0 ? `(${totalInactive})` : ''}</span>
        `;
      }

      renderCategoryPills(allCategories);
      renderAdminProducts(allProducts, totalInactive);
      populateCategorySelect(allCategories);
    } catch (e) {
      container.innerHTML = `<div class="loading-spinner" style="color:var(--admin-danger);">Xatolik yuz berdi: ${e.message}</div>`;
    }
  }

  // Kategoriya SVG belgisi tanlash
  function getCategorySvg(iconName, catName) {
    const lower = (catName || '').toLowerCase();
    if (iconName === 'smartphone' || lower.includes('smart') || lower.includes('phone') || lower.includes('telefon')) {
      return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>`;
    }
    if (iconName === 'laptop' || lower.includes('noutbuk') || lower.includes('mac') || lower.includes('laptop')) {
      return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><rect width="18" height="12" x="3" y="4" rx="2"/><path d="M2 20h20"/></svg>`;
    }
    if (iconName === 'headphones' || lower.includes('quloqchin') || lower.includes('audio') || lower.includes('airpod')) {
      return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/></svg>`;
    }
    if (iconName === 'watch' || lower.includes('soat') || lower.includes('watch')) {
      return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><circle cx="12" cy="12" r="7"/><polyline points="12 9 12 12 13.5 13.5"/><path d="M16.51 17.35l-.85 3.22a2 2 0 0 1-1.93 1.43H10.27a2 2 0 0 1-1.93-1.43l-.85-3.22"/><path d="M7.49 6.65l.85-3.22A2 2 0 0 1 10.27 2h3.46a2 2 0 0 1 1.93 1.43l.85 3.22"/></svg>`;
    }
    if (iconName === 'plug' || lower.includes('aksessuar') || lower.includes('quvvat') || lower.includes('kabel')) {
      return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a6 6 0 0 1-12 0V8z"/></svg>`;
    }
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/></svg>`;
  }

  // Dinamik Kategoriya chiplari (Barchasi, Smartfonlar, Noutbuklar...)
  function renderCategoryPills(categories) {
    const bar = document.getElementById('adminCategoryPillsBar');
    if (!bar) return;

    let html = `
      <button class="cat-pill btn-bounce ${activeCategoryFilter === 'all' ? 'active' : ''}" data-cat-id="all">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>
        <span>Barchasi</span>
      </button>
    `;

    categories.forEach(c => {
      const isSel = String(activeCategoryFilter) === String(c.id);
      const iconSvg = getCategorySvg(c.icon, c.name);
      html += `
        <button class="cat-pill btn-bounce ${isSel ? 'active' : ''}" data-cat-id="${c.id}">
          ${iconSvg}
          <span>${c.name}</span>
        </button>
      `;
    });

    bar.innerHTML = html;

    bar.querySelectorAll('.cat-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        triggerHaptic('light');
        activeCategoryFilter = btn.getAttribute('data-cat-id');
        bar.querySelectorAll('.cat-pill').forEach(b => b.classList.toggle('active', b === btn));
        loadAdminProducts();
      });
    });
  }

  function renderAdminProducts(products, inactiveCount = 0) {
    const container = document.getElementById('adminProductsContainer');
    if (!container) return;

    // Nofaollar soni va Barchasini faollashtirish panelini boshqarish
    const inactiveBar = document.getElementById('adminInactiveActionBar');
    const inactiveCountLabel = document.getElementById('inactiveCountLabel');
    if (inactiveBar) {
      if (inactiveCount > 0 && (activeStatusFilter === 'inactive' || activeStatusFilter === 'all')) {
        inactiveBar.classList.remove('hidden');
        if (inactiveCountLabel) {
          inactiveCountLabel.textContent = `${inactiveCount} ta nofaol tovar mavjud`;
        }
      } else {
        inactiveBar.classList.add('hidden');
      }
    }

    if (!products || products.length === 0) {
      container.innerHTML = '<div class="loading-spinner">Mos keluvchi mahsulotlar topilmadi.</div>';
      return;
    }

    container.innerHTML = products.map(p => {
      const isDiscount = p.is_discount === 1;
      const isActive = p.is_active === 1;
      const isUzs = p.currency === 'UZS';
      const priceFormatted = isUzs ? formatPrice(p.price_uzs || p.price) : formatUsd(p.price);
      const subPrice = isUzs ? '' : formatPrice(p.price_uzs || (p.price * currentUsdRate));

      return `
        <div class="admin-prod-card" data-id="${p.id}" onclick="window.AdminApp.toggleCardActions(this, event)">
          <div class="admin-prod-top">
            <img class="admin-prod-img" src="${p.image_url}" alt="${p.name}" loading="lazy" onerror="this.src='/static/apple_3d_logo.png'" />
            <div class="admin-prod-info">
              <span class="admin-prod-name">${p.name}</span>
              <span class="admin-prod-price">${priceFormatted}</span>
              ${subPrice ? `<span class="admin-prod-uzs">≈ ${subPrice}</span>` : ''}
              <div class="admin-prod-badges">
                <span class="status-badge ${isActive ? 'badge-active' : 'badge-inactive'}">
                  ${isActive ? `
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>Faol</span>
                  ` : `
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    <span>Nofaol</span>
                  `}
                </span>
                ${isDiscount ? `
                  <span class="status-badge badge-discount">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
                    <span>Chegirma</span>
                  </span>
                ` : ''}
                <span class="status-badge badge-views">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  <span>${p.views_count || 0}</span>
                </span>
                ${p.category_name ? `<span class="badge-mini">${p.category_name}</span>` : ''}
              </div>
            </div>
            <div class="admin-prod-expand-btn" title="Amallar menyusini ochish">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </div>
          </div>
          <div class="admin-prod-actions" onclick="event.stopPropagation()">
            <button class="btn-action btn-bounce ${isDiscount ? 'active-discount' : ''}" onclick="event.stopPropagation(); window.AdminApp.toggleDiscount(${p.id})">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
              <span>${isDiscount ? 'Aksiyada' : 'Aksiya'}</span>
            </button>
            <button class="btn-action btn-bounce ${isActive ? 'active-status' : ''}" onclick="event.stopPropagation(); window.AdminApp.toggleActive(${p.id})">
              ${isActive ? `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
                <span>Yashirish</span>
              ` : `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                <span>Faol</span>
              `}
            </button>
            <button class="btn-action btn-bounce" onclick="event.stopPropagation(); window.AdminApp.editProduct(${p.id})">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
              <span>Tahrir</span>
            </button>
            <button class="btn-action btn-bounce btn-del" onclick="event.stopPropagation(); window.AdminApp.deleteProduct(${p.id})">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              <span>O'chirish</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  function populateCategorySelect(categories) {
    const select = document.getElementById('formProductCategory');
    if (!select) return;
    select.innerHTML = '<option value="">(Kategoriyasiz)</option>' + categories.map(c => `
      <option value="${c.id}">${c.name}</option>
    `).join('');
  }

  // Mahsulot Modali
  function openProductModal(product = null) {
    const modal = document.getElementById('productModal');
    const title = document.getElementById('modalProductTitle');
    const form = document.getElementById('productForm');
    if (!modal || !form) return;

    form.reset();
    if (product) {
      title.textContent = 'Mahsulotni tahrirlash #' + product.id;
      document.getElementById('formProductId').value = product.id;
      document.getElementById('formProductName').value = product.name || '';
      document.getElementById('formProductPrice').value = product.price || '';
      document.getElementById('formProductCurrency').value = product.currency || 'USD';
      document.getElementById('formProductCategory').value = product.category_id || '';
      document.getElementById('formProductImage').value = product.image_url || '';
      document.getElementById('formProductDesc').value = product.description || '';
      document.getElementById('formProductActive').checked = product.is_active === 1;
      document.getElementById('formProductDiscount').checked = product.is_discount === 1;
    } else {
      title.textContent = 'Yangi mahsulot qo\'shish';
      document.getElementById('formProductId').value = '';
      document.getElementById('formProductActive').checked = true;
      document.getElementById('formProductDiscount').checked = false;
    }

    modal.classList.remove('hidden');
    triggerHaptic('selection');
  }

  function closeProductModal() {
    const modal = document.getElementById('productModal');
    if (modal) modal.classList.add('hidden');
  }

  // 7. Buyurtmalarni Boshqarish (Orders Tab)
  async function loadAdminOrders() {
    const container = document.getElementById('adminOrdersContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading-spinner">Buyurtmalar yuklanmoqda...</div>';

    try {
      const params = new URLSearchParams();
      if (activeOrderFilter !== 'all') params.append('status', activeOrderFilter);

      const res = await apiFetch(`/api/admin/orders?${params.toString()}`);
      if (!res.ok) throw new Error('Yuklab bo\'lmadi');
      const data = await res.json();
      renderAdminOrders(data.orders || []);
    } catch (e) {
      container.innerHTML = `<div class="loading-spinner" style="color:var(--admin-danger);">Xatolik: ${e.message}</div>`;
    }
  }

  function renderAdminOrders(orders) {
    const container = document.getElementById('adminOrdersContainer');
    if (!container) return;

    if (!orders || orders.length === 0) {
      container.innerHTML = '<div class="loading-spinner">Mos keluvchi buyurtmalar topilmadi.</div>';
      return;
    }

    const statuses = ['Yangi', 'Qabul qilindi', 'Yetkazilmoqda', 'Yetkazildi', 'Bekor qilindi'];

    container.innerHTML = orders.map(o => {
      const itemsHtml = (o.items || []).map(i => `
        <div class="order-item-line">
          <span>${i.product_name} × ${i.quantity}</span>
          <span style="font-weight:600;">${formatPrice(i.price * i.quantity)}</span>
        </div>
      `).join('');

      const cleanPhone = (o.phone || '').replace(/[^0-9+]/g, '');

      return `
        <div class="admin-order-card" data-order-id="${o.id}">
          <div class="order-header-row">
            <span class="order-id">Buyurtma #${o.id}</span>
            <span class="order-time">${o.created_at ? new Date(o.created_at).toLocaleDateString('uz-UZ', { hour: '2-digit', minute: '2-digit' }) : ''}</span>
          </div>

          <div class="order-customer">
            <div class="customer-row">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span class="customer-name">${o.full_name || 'Ismsiz'}</span>
            </div>
            ${cleanPhone ? `
              <div class="customer-row">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                <a href="tel:${cleanPhone}" class="customer-phone">${o.phone}</a>
              </div>
            ` : ''}
            <div class="customer-row">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
              <span class="customer-address">${o.address || 'Manzil ko\'rsatilmagan'}</span>
            </div>
            <div class="customer-row">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
              <span class="customer-address">${o.payment_method || 'Naqd to\'lov'}</span>
            </div>
          </div>

          <div class="order-items-box">
            ${itemsHtml}
            <div class="order-total-line">
              <span>Jami:</span>
              <span>${formatPrice(o.total_amount)}</span>
            </div>
          </div>

          <div class="order-status-selector">
            <span style="font-size:12px;font-weight:600;color:var(--admin-text-sub);">Status:</span>
            <select onchange="window.AdminApp.changeOrderStatus(${o.id}, this.value)">
              ${statuses.map(s => `<option value="${s}" ${o.status === s ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
          </div>
        </div>
      `;
    }).join('');
  }

  // 8. Kanal Sinxronizatsiyasi
  async function runChannelSync() {
    const btn = document.getElementById('btnRunSyncChannel') || document.getElementById('btnQuickSyncChannel');
    const resultBox = document.getElementById('syncResultBox');
    if (btn) btn.disabled = true;
    showToast('Kanal tekshirilmoqda...', true);

    try {
      const res = await apiFetch('/api/admin/sync-channel', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Xatolik');

      showToast(`Sinxronlandi: ${data.deactivated_count || 0} ta post to'g'rilandi`, true);
      if (resultBox) {
        resultBox.textContent = `Natija: ${data.checked_posts_count} ta post tekshirildi, ${data.deactivated_count} ta o'chirilgan post do'kondan yashirildi.`;
        resultBox.classList.remove('hidden');
      }
      loadDashboardData();
    } catch (e) {
      showToast('Sinxronlashda xatolik: ' + e.message, false);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // 9. Hodisalar (Events)
  function initEvents() {
    document.getElementById('btnRefreshAll')?.addEventListener('click', () => {
      triggerHaptic('light');
      const icon = document.getElementById('btnRefreshAll');
      icon?.classList.add('spinning');
      loadDashboardData().finally(() => {
        setTimeout(() => icon?.classList.remove('spinning'), 500);
      });
      showToast('Ma\'lumotlar yangilandi', true);
    });

    document.getElementById('btnStoreLink')?.addEventListener('click', (e) => {
      e.preventDefault();
      triggerHaptic('light');
      window.location.href = '/?app=store';
    });

    document.getElementById('btnRefreshCurrency')?.addEventListener('click', async () => {
      triggerHaptic('light');
      const btn = document.getElementById('btnRefreshCurrency');
      if (btn) btn.disabled = true;
      try {
        const res = await apiFetch('/api/currency');
        if (res.ok) {
          const data = await res.json();
          currentUsdRate = data.rate || currentUsdRate;
          document.getElementById('dashRateValue').textContent = `1$ = ${Number(currentUsdRate).toLocaleString('uz-UZ')} so'm`;
          showToast(`USD kursi yangilandi: 1$ = ${formatPrice(currentUsdRate)}`, true);
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    const searchInput = document.getElementById('adminSearchInput');
    const clearBtn = document.getElementById('adminSearchClear');
    let searchTimer = null;
    searchInput?.addEventListener('input', () => {
      clearBtn?.classList.toggle('hidden', !searchInput.value);
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        loadAdminProducts();
      }, 350);
    });
    clearBtn?.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      clearBtn.classList.add('hidden');
      loadAdminProducts();
    });

    // Status filtrlari
    document.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        triggerHaptic('light');
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeStatusFilter = pill.getAttribute('data-status');
        loadAdminProducts();
      });
    });

    // Buyurtma filtrlari
    document.querySelectorAll('.order-filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        triggerHaptic('light');
        document.querySelectorAll('.order-filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeOrderFilter = pill.getAttribute('data-status');
        loadAdminOrders();
      });
    });

    // Mahsulot Modali
    document.getElementById('btnAddProductModal')?.addEventListener('click', () => {
      openProductModal();
    });
    document.getElementById('btnCloseProductModal')?.addEventListener('click', closeProductModal);
    document.getElementById('btnCancelProductModal')?.addEventListener('click', closeProductModal);

    // Mahsulot Saqlash Formasi
    document.getElementById('productForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('btnSaveProductModal');
      if (saveBtn) saveBtn.disabled = true;

      const pId = document.getElementById('formProductId').value;
      const payload = {
        name: document.getElementById('formProductName').value.trim(),
        price: parseInt(document.getElementById('formProductPrice').value, 10),
        currency: document.getElementById('formProductCurrency').value,
        category_id: document.getElementById('formProductCategory').value || null,
        image_url: document.getElementById('formProductImage').value.trim(),
        description: document.getElementById('formProductDesc').value.trim(),
        is_active: document.getElementById('formProductActive').checked ? 1 : 0,
        is_discount: document.getElementById('formProductDiscount').checked ? 1 : 0
      };

      try {
        const url = pId ? `/api/admin/products/${pId}` : '/api/admin/products';
        const method = pId ? 'PUT' : 'POST';
        const res = await apiFetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.error || 'Saqlashda xatolik');
        }

        showToast(pId ? 'Mahsulot yangilandi' : 'Yangi mahsulot qo\'shildi', true);
        closeProductModal();
        loadAdminProducts();
        loadDashboardData();
      } catch (err) {
        showToast('Xatolik: ' + err.message, false);
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    });

    // Kanalga Post Chiqarish Formasi
    document.getElementById('channelPostForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('btnSubmitChannelPost');
      if (submitBtn) submitBtn.disabled = true;

      const payload = {
        name: document.getElementById('postName').value.trim(),
        price: parseInt(document.getElementById('postPrice').value, 10),
        currency: document.getElementById('postCurrency').value,
        image_url: document.getElementById('postImageUrl').value.trim(),
        description: document.getElementById('postDesc').value.trim(),
        is_discount: document.getElementById('postIsDiscount').checked
      };

      try {
        const res = await apiFetch('/api/admin/publish-channel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Telegram xatosi');

        showToast('Post kanalga muvaffaqiyatli chiqarildi!', true);
        document.getElementById('channelPostForm').reset();
        loadDashboardData();
      } catch (err) {
        showToast('Post chiqarishda xatolik: ' + err.message, false);
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    document.getElementById('btnRunSyncChannel')?.addEventListener('click', runChannelSync);
  }

  // Window orqali chaqiriladigan global amallar
  window.AdminApp = {
    async toggleActive(productId) {
      triggerHaptic('light');
      try {
        const res = await apiFetch(`/api/admin/products/${productId}/toggle-active`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(data.is_active ? 'Mahsulot faollashtirildi' : 'Mahsulot yashirildi', true);
          loadAdminProducts();
          loadDashboardData();
        }
      } catch (e) {
        showToast('Xatolik yuz berdi', false);
      }
    },

    async toggleDiscount(productId) {
      triggerHaptic('light');
      try {
        const res = await apiFetch(`/api/admin/products/${productId}/toggle-discount`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(data.is_discount ? 'Hafta chegirmasiga qo\'shildi' : 'Chegirmadan olib tashlandi', true);
          loadAdminProducts();
          loadDashboardData();
        }
      } catch (e) {
        showToast('Xatolik yuz berdi', false);
      }
    },

    editProduct(productId) {
      const prod = allProducts.find(p => p.id === productId);
      if (prod) {
        openProductModal(prod);
      }
    },

    async deleteProduct(productId) {
      triggerHaptic('warning');
      if (!confirm('Haqiqatan ham ushbu mahsulotni o\'chirmoqchimisiz?')) return;

      try {
        const res = await apiFetch(`/api/admin/products/${productId}`, { method: 'DELETE' });
        if (res.ok) {
          showToast('Mahsulot o\'chirildi', true);
          loadAdminProducts();
          loadDashboardData();
        }
      } catch (e) {
        showToast('O\'chirishda xatolik', false);
      }
    },

    async changeOrderStatus(orderId, newStatus) {
      triggerHaptic('selection');
      try {
        const res = await apiFetch(`/api/admin/orders/${orderId}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus })
        });
        if (res.ok) {
          showToast(`Buyurtma #${orderId} holati o'zgartirildi: ${newStatus}`, true);
          loadDashboardData();
        }
      } catch (e) {
        showToast('Statusni o\'zgartirib bo\'lmadi', false);
      }
    },

    toggleCardActions(cardEl, event) {
      if (event) {
        if (event.target.closest('button') || event.target.closest('input') || event.target.closest('.admin-prod-actions')) {
          return;
        }
      }
      const wasOpen = cardEl.classList.contains('actions-open');
      document.querySelectorAll('.admin-prod-card.actions-open').forEach(c => {
        if (c !== cardEl) c.classList.remove('actions-open');
      });
      if (wasOpen) {
        cardEl.classList.remove('actions-open');
      } else {
        cardEl.classList.add('actions-open');
        triggerHaptic('light');
      }
    },

    async handleLogin(event) {
      if (event) event.preventDefault();
      const input = document.getElementById('adminLoginInput');
      const errorEl = document.getElementById('loginErrorMsg');
      const val = input ? input.value.trim() : '';
      if (!val) return;
      if (errorEl) errorEl.style.display = 'none';

      try {
        const res = await fetch('/api/admin/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credential: val })
        });
        const data = await res.json();
        if (res.ok && data.ok && data.admin_token) {
          adminToken = data.admin_token;
          try {
            localStorage.setItem('admin_token', data.admin_token);
          } catch (e) {}
          document.getElementById('unauthorizedScreen')?.classList.add('hidden');
          document.getElementById('adminContent')?.classList.remove('hidden');
          document.getElementById('adminBottomNav')?.classList.remove('hidden');
          currentAdminUser = data.user;
          const adminNameEl = document.getElementById('adminGreeting');
          if (adminNameEl && currentAdminUser) {
            adminNameEl.textContent = currentAdminUser.first_name || 'Admin';
          }
          showToast('Xush kelibsiz, Admin!', true);
          loadDashboardData();
        } else {
          if (errorEl) {
            errorEl.textContent = data.error || 'Admin ID yoki parol noto\'g\'ri';
            errorEl.style.display = 'block';
          }
        }
      } catch (err) {
        if (errorEl) {
          errorEl.textContent = 'Server bilan aloqa uzildi';
          errorEl.style.display = 'block';
        }
      }
    },

    activateAllInactive() {
      triggerHaptic('medium');
      const inactiveCount = (allProducts || []).filter(p => Number(p.is_active) === 0).length;
      const count = inactiveCount > 0 ? inactiveCount : 'barcha';
      const label = document.getElementById('confirmActivateAllText');
      if (label) {
        label.textContent = `Haqiqatan ham ${count} ta nofaol tovarlarni bittada faol (do'konda ko'rinadigan) qilmoqchimisiz?`;
      }
      document.getElementById('modalConfirmActivateAll')?.classList.remove('hidden');
    },

    closeActivateAllModal() {
      document.getElementById('modalConfirmActivateAll')?.classList.add('hidden');
    },

    async executeActivateAll() {
      const btn = document.getElementById('btnConfirmActivateAllSubmit');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Faollashtirilmoqda...';
      }
      try {
        const res = await apiFetch('/api/admin/products/activate-all', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          showToast(data.message || 'Barcha nofaol tovarlar muvaffaqiyatli faollashtirildi!', true);
          window.AdminApp.closeActivateAllModal();
          // Barcha tovarlar faollashtirilgach, avtomatik "Barchasi" filtriga o'tkazamiz
          activeStatusFilter = 'all';
          document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
          document.querySelector('.filter-pill[data-status="all"]')?.classList.add('active');
          await loadAdminProducts();
          await loadDashboardData();
        } else {
          showToast(data.error || 'Xatolik yuz berdi', false);
        }
      } catch (e) {
        showToast('Server bilan aloqa uzildi', false);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Ha, faollashtir';
        }
      }
    }
  };

  // Dasturni yuklash
  async function init() {
    initTabs();
    initEvents();

    const isAuthorized = await checkAdminAuth();
    if (isAuthorized) {
      loadDashboardData();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
