// DemoStore Admin Mini App Logic
(function () {
  'use strict';

  const tg = window.Telegram?.WebApp;
  let currentAdminUser = null;
  let allProducts = [];
  let allCategories = [];
  let currentUsdRate = 12850;
  let activeStatusFilter = 'all';
  let activeOrderFilter = 'all';

  // 1. Telegram WebApp Initsializatsiyasi
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
        tg.setBackgroundColor('#f8fafc');
      }
    } catch (e) {
      console.warn('Telegram init ogohlantirish:', e);
    }
  }

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

  // 2. API So'rov Yordamchisi (InitData bilan)
  async function apiFetch(url, options = {}) {
    const opts = { ...options };
    const headers = { ...(opts.headers || {}) };
    const initData = tg?.initData || '';
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
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

      // Tabga qarab ma'lumotlarni yuklash
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
        document.getElementById('unauthorizedScreen').classList.remove('hidden');
        document.getElementById('adminContent').classList.add('hidden');
        document.getElementById('adminBottomNav').classList.add('hidden');
        return false;
      }
      const data = await res.json();
      currentAdminUser = data.user;
      
      const adminNameEl = document.getElementById('adminGreeting');
      if (adminNameEl && currentAdminUser) {
        adminNameEl.textContent = currentAdminUser.first_name || 'Admin';
      }
      return true;
    } catch (e) {
      console.error('Admin tekshiruvida xatolik:', e);
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

      // Statistika kartochkalari
      const stats = data.stats || {};
      document.getElementById('statRevenue').textContent = formatPrice(stats.total_revenue);
      document.getElementById('statTodayRevenue').textContent = `Bugun: ${formatPrice(stats.today_revenue)}`;
      
      document.getElementById('statOrders').textContent = `${stats.orders_count || 0} ta`;
      document.getElementById('statTodayOrders').textContent = `Bugun: ${stats.today_orders || 0} ta yangi`;

      document.getElementById('statProducts').textContent = `${stats.products_count || 0} ta`;
      document.getElementById('statDiscounts').textContent = `Chegirmalar: ${stats.discount_count || 0} ta`;

      document.getElementById('statUsers').textContent = `${stats.users_count || 0} nafar`;

      // Kanal ma'lumotlari
      if (data.channel) {
        document.getElementById('channelUsernameText').textContent = data.channel.username ? `@${data.channel.username}` : 'Noma\'lum';
        document.getElementById('channelIdText').textContent = data.channel.id || '-';
        const linkBtn = document.getElementById('channelLinkBtn');
        if (linkBtn && data.channel.url) {
          linkBtn.href = data.channel.url;
        }
      }

      // Top tovarlar ro'yxati
      renderTopProducts(data.top_products || []);

      // So'nggi buyurtmalar
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
          <span>👁 ${p.views_count || 0} ta</span>
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

      const res = await apiFetch(`/api/admin/products?${params.toString()}`);
      if (!res.ok) throw new Error('Yuklab bo\'lmadi');
      const data = await res.json();

      allProducts = data.products || [];
      allCategories = data.categories || [];
      currentUsdRate = data.current_usd_rate || currentUsdRate;

      renderAdminProducts(allProducts);
      populateCategorySelect(allCategories);
    } catch (e) {
      container.innerHTML = `<div class="loading-spinner" style="color:var(--admin-danger);">Xatolik yuz berdi: ${e.message}</div>`;
    }
  }

  function renderAdminProducts(products) {
    const container = document.getElementById('adminProductsContainer');
    if (!container) return;

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
        <div class="admin-prod-card" data-id="${p.id}">
          <div class="admin-prod-top">
            <img class="admin-prod-img" src="${p.image_url}" alt="${p.name}" loading="lazy" onerror="this.src='/static/apple_3d_logo.png'" />
            <div class="admin-prod-info">
              <span class="admin-prod-name">${p.name}</span>
              <span class="admin-prod-price">${priceFormatted}</span>
              ${subPrice ? `<span class="admin-prod-uzs">≈ ${subPrice}</span>` : ''}
              <div class="admin-prod-badges">
                <span class="status-badge ${isActive ? 'badge-active' : 'badge-inactive'}">${isActive ? '🟢 Faol' : '⚪️ Nofaol'}</span>
                ${isDiscount ? '<span class="status-badge badge-discount">🔥 Chegirma</span>' : ''}
                <span class="status-badge badge-views">👁 ${p.views_count || 0}</span>
                ${p.category_name ? `<span class="badge-mini">${p.category_name}</span>` : ''}
              </div>
            </div>
          </div>
          <div class="admin-prod-actions">
            <button class="btn-action ${isDiscount ? 'active-discount' : ''}" onclick="window.AdminApp.toggleDiscount(${p.id})">
              ${isDiscount ? '🔥 Chegirmada' : '🏷 Aksiya qilish'}
            </button>
            <button class="btn-action ${isActive ? 'active-status' : ''}" onclick="window.AdminApp.toggleActive(${p.id})">
              ${isActive ? '👁 Yashirish' : '🟢 Faollashtirish'}
            </button>
            <button class="btn-action" onclick="window.AdminApp.editProduct(${p.id})">
              ✏️ Tahrirlash
            </button>
            <button class="btn-action btn-del" onclick="window.AdminApp.deleteProduct(${p.id})">
              🗑 O'chirish
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
            <span class="customer-name">👤 ${o.full_name || 'Ismsiz'}</span>
            ${cleanPhone ? `<a href="tel:${cleanPhone}" class="customer-phone">📞 ${o.phone}</a>` : ''}
            <span class="customer-address">📍 Manzil: ${o.address || 'Kiritilmagan'}</span>
            <span class="customer-address">💳 To'lov usuli: ${o.payment_method || 'Naqd'}</span>
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
      if (res.ok) {
        const count = data.deleted_count || 0;
        const msg = count > 0 
          ? `Sinxronlash yakunlandi: ${count} ta o'chirilgan post do'kondan yashirildi.` 
          : "Barcha kanal postlari faol, hech qanday o'chirilgan post topilmadi.";
        showToast(msg, true);
        if (resultBox) {
          resultBox.textContent = `✅ ${msg}`;
          resultBox.classList.remove('hidden');
        }
        loadDashboardData();
        if (allProducts.length > 0) loadAdminProducts();
      } else {
        showToast('Sinxronlashda xatolik', false);
      }
    } catch (e) {
      showToast('Aloqa xatosi: ' + e.message, false);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // 9. Global Handlerlar (Window Object)
  window.AdminApp = {
    async toggleActive(id) {
      triggerHaptic('light');
      try {
        const res = await apiFetch(`/api/admin/products/${id}/toggle-active`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(data.is_active ? 'Mahsulot faollashtirildi' : 'Mahsulot yashirildi', true);
          loadAdminProducts();
        }
      } catch (e) {
        showToast('Xatolik: ' + e.message, false);
      }
    },

    async toggleDiscount(id) {
      triggerHaptic('light');
      try {
        const res = await apiFetch(`/api/admin/products/${id}/toggle-discount`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(data.is_discount ? '🔥 Chegirmaga qo\'shildi' : 'Chegirmadan chiqarildi', true);
          loadAdminProducts();
        }
      } catch (e) {
        showToast('Xatolik: ' + e.message, false);
      }
    },

    editProduct(id) {
      const p = allProducts.find(item => item.id === id);
      if (p) openProductModal(p);
    },

    async deleteProduct(id) {
      if (!confirm(`Haqiqatan ham ushbu mahsulotni o'chirmoqchimisiz? (#${id})`)) return;
      triggerHaptic('medium');
      try {
        const res = await apiFetch(`/api/admin/products/${id}`, { method: 'DELETE' });
        if (res.ok) {
          showToast('Mahsulot muvaffaqiyatli o\'chirildi', true);
          loadAdminProducts();
        }
      } catch (e) {
        showToast('O\'chirishda xatolik: ' + e.message, false);
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
          showToast(`Buyurtma #${orderId} statusi "${newStatus}" ga o'zgartirildi`, true);
          loadDashboardData();
        } else {
          showToast('Statusni o\'zgartirib bo\'lmadi', false);
        }
      } catch (e) {
        showToast('Xatolik: ' + e.message, false);
      }
    }
  };

  // 10. DOM Hodisalari
  document.addEventListener('DOMContentLoaded', async () => {
    initTabs();

    // Refresh barchasi
    document.getElementById('btnRefreshAll')?.addEventListener('click', () => {
      triggerHaptic('medium');
      loadDashboardData();
      if (document.getElementById('tabProducts').classList.contains('active')) loadAdminProducts();
      if (document.getElementById('tabOrders').classList.contains('active')) loadAdminOrders();
      showToast('Ma\'lumotlar yangilandi', true);
    });

    // Jonli kursni yangilash
    document.getElementById('btnRefreshCurrency')?.addEventListener('click', async () => {
      triggerHaptic('light');
      showToast('Markaziy Bankdan kurs yangilanmoqda...', true);
      try {
        const res = await apiFetch('/api/currency?force=1');
        if (res.ok) {
          const data = await res.json();
          currentUsdRate = data.rate;
          document.getElementById('dashRateValue').textContent = `1$ = ${Number(data.rate).toLocaleString('uz-UZ')} so'm`;
          showToast('Kurs yangilandi: 1$ = ' + data.formatted, true);
        }
      } catch (e) {}
    });

    // Mahsulot filter pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        triggerHaptic('selection');
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeStatusFilter = pill.getAttribute('data-status');
        loadAdminProducts();
      });
    });

    // Buyurtma filter pills
    document.querySelectorAll('.order-filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        triggerHaptic('selection');
        document.querySelectorAll('.order-filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeOrderFilter = pill.getAttribute('data-status');
        loadAdminOrders();
      });
    });

    // Qidiruv
    const searchInput = document.getElementById('adminSearchInput');
    const searchClear = document.getElementById('adminSearchClear');
    let searchDebounce = null;
    searchInput?.addEventListener('input', () => {
      searchClear?.classList.toggle('hidden', !searchInput.value);
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(loadAdminProducts, 350);
    });
    searchClear?.addEventListener('click', () => {
      searchInput.value = '';
      searchClear.classList.add('hidden');
      loadAdminProducts();
    });

    // Modal hodisalari
    document.getElementById('btnAddProductModal')?.addEventListener('click', () => openProductModal());
    document.getElementById('btnCloseProductModal')?.addEventListener('click', closeProductModal);
    document.getElementById('btnCancelProductModal')?.addEventListener('click', closeProductModal);

    // Mahsulot formasi submit
    document.getElementById('productForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('formProductId').value;
      const currency = document.getElementById('formProductCurrency').value;
      const rawPrice = parseInt(document.getElementById('formProductPrice').value, 10);
      
      const payload = {
        name: document.getElementById('formProductName').value.trim(),
        price: rawPrice,
        currency: currency,
        price_uzs: currency === 'UZS' ? rawPrice : Math.round(rawPrice * currentUsdRate),
        category_id: document.getElementById('formProductCategory').value || null,
        image_url: document.getElementById('formProductImage').value.trim(),
        description: document.getElementById('formProductDesc').value.trim(),
        is_active: document.getElementById('formProductActive').checked ? 1 : 0,
        is_discount: document.getElementById('formProductDiscount').checked ? 1 : 0
      };

      try {
        let res;
        if (id) {
          res = await apiFetch(`/api/admin/products/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          res = await apiFetch('/api/admin/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }

        if (res.ok) {
          closeProductModal();
          showToast(id ? 'Mahsulot muvaffaqiyatli saqlandi' : 'Yangi mahsulot yaratildi', true);
          loadAdminProducts();
          loadDashboardData();
        } else {
          const err = await res.json();
          showToast('Xatolik: ' + (err.error || 'Saqlab bo\'lmadi'), false);
        }
      } catch (err) {
        showToast('Tarmoq xatosi: ' + err.message, false);
      }
    });

    // Kanalga chiqarish formasi
    document.getElementById('channelPostForm')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('btnSubmitChannelPost');
      if (btn) btn.disabled = true;
      showToast('Kanalga yuborilmoqda...', true);

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
        if (res.ok) {
          showToast('🚀 Post kanalga muvaffaqiyatli chiqarildi!', true);
          document.getElementById('channelPostForm').reset();
          loadDashboardData();
        } else {
          showToast('Xatolik: ' + (data.error || 'Kanalga chiqarib bo\'lmadi'), false);
        }
      } catch (err) {
        showToast('Xatolik: ' + err.message, false);
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    // Kanal sinxronlash tugmasi
    document.getElementById('btnRunSyncChannel')?.addEventListener('click', runChannelSync);

    // Admin autentifikatsiyasini tekshirib dasturni boshlash
    const isOk = await checkAdminAuth();
    if (isOk) {
      loadDashboardData();
    }
  });

})();
