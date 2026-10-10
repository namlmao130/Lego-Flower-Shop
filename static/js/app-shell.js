// =======================================================
// HỆ THỐNG HỘP THOẠI XÁC NHẬN SANG TRỌNG (WINDOW.APPCONFIRM)
// =======================================================
window.appConfirm = function (options) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('appConfirmModal');
        if (!overlay) {
            const msg = typeof options === 'string' ? options : (options && options.message ? options.message : '');
            resolve(window.confirm(msg));
            return;
        }

        const titleEl = document.getElementById('appConfirmTitle');
        const msgEl = document.getElementById('appConfirmMessage');
        const iconWrap = document.getElementById('appConfirmIconWrap');
        const okBtn = document.getElementById('appConfirmOkBtn');
        const cancelBtn = document.getElementById('appConfirmCancelBtn');

        const opts = typeof options === 'string' ? { message: options } : (options || {});
        const title = opts.title || 'Xác nhận';
        const message = opts.message || 'Bạn có chắc chắn muốn thực hiện hành động này?';
        const confirmText = opts.confirmText || 'Xác nhận';
        const cancelText = opts.cancelText || 'Hủy';
        const type = opts.type || 'warning';

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        if (okBtn) okBtn.textContent = confirmText;
        if (cancelBtn) cancelBtn.textContent = cancelText;

        if (iconWrap && okBtn) {
            if (type === 'danger') {
                iconWrap.className = 'app-confirm-icon-wrap icon-danger';
                okBtn.className = 'app-confirm-btn app-confirm-btn-danger';
                iconWrap.innerHTML = `
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>`;
            } else if (type === 'info') {
                iconWrap.className = 'app-confirm-icon-wrap icon-info';
                okBtn.className = 'app-confirm-btn app-confirm-btn-ok';
                iconWrap.innerHTML = `
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>`;
            } else {
                iconWrap.className = 'app-confirm-icon-wrap icon-warning';
                okBtn.className = 'app-confirm-btn app-confirm-btn-ok';
                iconWrap.innerHTML = `
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>`;
            }
        }

        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        setTimeout(() => okBtn && okBtn.focus(), 80);

        function cleanup(result) {
            overlay.classList.remove('open');
            overlay.setAttribute('aria-hidden', 'true');
            if (okBtn) okBtn.removeEventListener('click', onOk);
            if (cancelBtn) cancelBtn.removeEventListener('click', onCancel);
            overlay.removeEventListener('click', onOverlayClick);
            document.removeEventListener('keydown', onKeyDown);
            resolve(result);
        }

        function onOk(e) { e.preventDefault(); cleanup(true); }
        function onCancel(e) { e.preventDefault(); cleanup(false); }
        function onOverlayClick(e) {
            if (e.target === overlay) cleanup(false);
        }
        function onKeyDown(e) {
            if (e.key === 'Escape') cleanup(false);
        }

        if (okBtn) okBtn.addEventListener('click', onOk);
        if (cancelBtn) cancelBtn.addEventListener('click', onCancel);
        overlay.addEventListener('click', onOverlayClick);
        document.addEventListener('keydown', onKeyDown);
    });
};

// Bắt sự kiện submit tự động cho mọi form có data-confirm
document.addEventListener('submit', async function (e) {
    const form = e.target;
    const confirmMsg = form.getAttribute('data-confirm');
    if (confirmMsg && !form.dataset.confirmed) {
        e.preventDefault();
        const ok = await window.appConfirm({
            title: form.getAttribute('data-confirm-title') || 'Xác nhận',
            message: confirmMsg,
            confirmText: form.getAttribute('data-confirm-ok') || 'Đồng ý',
            cancelText: form.getAttribute('data-confirm-cancel') || 'Hủy',
            type: form.getAttribute('data-confirm-type') || 'warning'
        });
        if (ok) {
            form.dataset.confirmed = 'true';
            form.submit();
        }
    }
});

// -------------------------------------------------------
// ENGINE VẼ CÁNH HOA BAY (CANVAS)
// -------------------------------------------------------
const canvas = document.getElementById('petalCanvas');
const ctx = canvas.getContext('2d');
let width = canvas.width = window.innerWidth;
let height = canvas.height = window.innerHeight;

window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
});

class Petal {
    constructor(originX, originY, speedMult = 1) {
        this.x = originX ?? (Math.random() * 60);
        this.y = originY ?? (Math.random() * height);
        this.size = Math.random() * 10 + 9;
        this.vx = (Math.random() * 2.8 + 1.2) * speedMult;
        this.vy = (Math.random() * 1.6 + 0.6) * speedMult;
        this.angle = Math.random() * Math.PI * 2;
        this.angularSpeed = (Math.random() - 0.5) * 0.04;
        this.flip = Math.random() * Math.PI;
        this.flipSpeed = Math.random() * 0.03 + 0.02;
        this.opacity = Math.random() * 0.4 + 0.6;
        this.decay = Math.random() * 0.003 + 0.002;
        const shades = ['#f472b6', '#fbcfe8', '#fda4af', '#f43f5e', '#ffffff', '#fed7aa', '#ec4899'];
        this.color = shades[Math.floor(Math.random() * shades.length)];
    }
    update() {
        this.x += this.vx + Math.sin(this.angle) * 0.8;
        this.y += this.vy + Math.cos(this.flip) * 0.5;
        this.angle += this.angularSpeed;
        this.flip += this.flipSpeed;
        this.opacity -= this.decay;
    }
    draw(ctx) {
        if (this.opacity <= 0) return;
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);
        ctx.scale(1, Math.sin(this.flip));
        ctx.globalAlpha = Math.max(0, this.opacity);
        ctx.beginPath();
        ctx.moveTo(0, -this.size * 0.6);
        ctx.bezierCurveTo(this.size * 0.8, -this.size * 0.8, this.size * 0.9, this.size * 0.4, 0, this.size * 0.9);
        ctx.bezierCurveTo(-this.size * 0.9, this.size * 0.4, -this.size * 0.8, -this.size * 0.8, 0, -this.size * 0.6);
        const grad = ctx.createLinearGradient(-this.size, -this.size, this.size, this.size);
        grad.addColorStop(0, this.color);
        grad.addColorStop(0.7, '#881337');
        grad.addColorStop(1, '#4c0519');
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.restore();
    }
}

const petals = [];
const isMobileScreen = window.innerWidth < 768;
const maxPetals = isMobileScreen ? 28 : 46;

function spawnPetal(x, y, speed = 1) {
    if (document.hidden) return;
    if (petals.length < maxPetals) petals.push(new Petal(x, y, speed));
}

function burstPetals(count = 35, originX = 60, originY = null) {
    const actualCount = isMobileScreen ? Math.min(count, 16) : count;
    for (let i = 0; i < actualCount; i++) {
        const y = originY !== null ? originY + (Math.random() - 0.5) * 100 : Math.random() * height;
        petals.push(new Petal(originX, y, 1.8));
    }
}

let animFrameId = null;
function render() {
    if (document.hidden) {
        animFrameId = null;
        return;
    }
    ctx.clearRect(0, 0, width, height);
    for (let i = petals.length - 1; i >= 0; i--) {
        const p = petals[i];
        p.update();
        p.draw(ctx);
        if (p.opacity <= 0 || p.x > width + 50 || p.y > height + 50) petals.splice(i, 1);
    }
    animFrameId = requestAnimationFrame(render);
}
render();

document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !animFrameId) {
        animFrameId = requestAnimationFrame(render);
    }
});

// -------------------------------------------------------
// LOGIC KÉO THẢ & TRƯỢT TOOLBAR
// -------------------------------------------------------
const toolbar = document.getElementById('roseToolbar');
const dragHandle = document.getElementById('dragHandle');
const toggleBtn = document.getElementById('toggleBtn');
const toolbarBackdrop = document.getElementById('toolbarBackdrop');

let isOpen = false;
let isDragging = false;
let hasDragged = false;
let suppressNextOutsideClick = false;
let startX = 0;
let lastRoseBurstAt = 0;
const roseBurstCooldown = 3000;
const getMinX = () => (window.innerWidth < 768 ? -295 : -270);
let minX = getMinX();
const maxX = 0;
let currentX = minX;

function updateToolbarPos(x, smooth = false) {
    toolbar.style.transition = smooth ? 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)' : 'none';
    toolbar.style.transform = `translateX(${x}px)`;
    if (Math.random() < 0.35) spawnPetal(270 + x, Math.random() * height);
}

function tryRoseBurst(count, x, y) {
    const now = Date.now();
    if (now - lastRoseBurstAt < roseBurstCooldown) return false;

    lastRoseBurstAt = now;
    burstPetals(count, x, y);
    return true;
}

function toggle(openState) {
    isOpen = openState;
    minX = getMinX();
    currentX = isOpen ? maxX : minX;
    updateToolbarPos(currentX, true);
    toggleBtn.textContent = isOpen ? '✕' : '☰';

    if (toolbarBackdrop) {
        if (isOpen) toolbarBackdrop.classList.add('active');
        else toolbarBackdrop.classList.remove('active');
    }

    if (isOpen) {
        tryRoseBurst(30, 270);
        const navEl = document.querySelector('.shop-navbar');
        if (navEl) navEl.classList.remove('nav-scrolled-hidden');
    }
    if (dragHandle) {
        const icon = dragHandle.querySelector('.drag-tab-icon');
        if (icon) icon.textContent = isOpen ? '‹' : '›';
    }
}

toggleBtn.addEventListener('click', () => toggle(!isOpen));

if (dragHandle) {
    dragHandle.addEventListener('click', () => {
        if (!hasDragged) toggle(!isOpen);
    });
}

// Kéo thả
function dragStart(e) {
    if (e.button !== undefined && e.button !== 0) return;
    isDragging = true;
    hasDragged = false;
    startX = e.clientX;
    dragHandle.setPointerCapture?.(e.pointerId);
    toolbar.style.transition = 'none';
    document.body.style.userSelect = 'none'; // Chặn bôi xanh text khi kéo
    e.preventDefault();
}
function dragMove(e) {
    if (!isDragging) return;
    const clientX = e.clientX;
    const delta = clientX - startX;
    if (Math.abs(delta) > 3) hasDragged = true;
    let newX = (isOpen ? maxX : minX) + delta;
    if (newX < minX) newX = minX;
    if (newX > maxX + 10) newX = maxX + 10;
    currentX = newX;
    updateToolbarPos(newX, false);
    e.preventDefault();
}
function dragEnd(e) {
    if (!isDragging) return;
    isDragging = false;
    document.body.style.userSelect = ''; // Khôi phục bôi text bình thường
    if (dragHandle.hasPointerCapture?.(e.pointerId)) {
        dragHandle.releasePointerCapture(e.pointerId);
    }
    if (hasDragged) {
        // Pointerup có thể tạo click ở vị trí thả chuột bên ngoài sidebar.
        // Bỏ qua click đó để không kích hoạt logic tự đóng.
        suppressNextOutsideClick = true;
        setTimeout(() => { suppressNextOutsideClick = false; }, 300);
    }
    toggle(currentX > minX + 80);
}

dragHandle.addEventListener('pointerdown', dragStart);
dragHandle.addEventListener('pointermove', dragMove);
dragHandle.addEventListener('pointerup', dragEnd);
dragHandle.addEventListener('pointercancel', dragEnd);

// Bấm ra ngoài toolbar thì tự đóng
document.addEventListener('click', (e) => {
    if (!isOpen) return;
    if (suppressNextOutsideClick) return;
    if (!toolbar.contains(e.target) && e.target !== toggleBtn) {
        toggle(false);
    }
});

if (toolbarBackdrop) {
    toolbarBackdrop.addEventListener('click', () => toggle(false));
}

// Nhả cánh hoa tự động (nhịp độ tối ưu theo thiết bị để máy mát và mượt mà)
const petalSpawnDelay = isMobileScreen ? 700 : 450;
setInterval(() => {
    if (Math.random() < 0.45) spawnPetal(isOpen ? 270 : 50, Math.random() * height);
}, petalSpawnDelay);

window.addEventListener('resize', () => {
    minX = getMinX();
    if (!isOpen) {
        currentX = minX;
        updateToolbarPos(currentX, false);
    }
});
updateToolbarPos(minX, false);



// =======================================================
// ĐIỀU KHIỂN ẨN / HIỆN KHUNG ĐẦU TRANG KHI CUỘN TRANG
// (Lướt xuống -> Thu lên trên | Lướt lên -> Trượt xuống)
// =======================================================
(function () {
    const navEl = document.querySelector('.shop-navbar');
    if (!navEl) return;

    let lastScrollY = Math.max(0, window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0);
    let isNavHidden = false;
    let navScrollTicking = false;
    const SCROLL_DELTA = 4;
    const SCROLL_MIN_OFFSET = 35;

    function setNavbarVisibility(hidden) {
        if (hidden && !isNavHidden) {
            navEl.classList.add('nav-scrolled-hidden');
            navEl.style.transform = 'translateY(-100%)';
            navEl.style.boxShadow = 'none';
            navEl.style.pointerEvents = 'none';
            isNavHidden = true;

            // Đóng menu tài khoản nếu đang mở để tránh bị kẹt
            const openUserMenu = document.querySelector('.user-popover-menu.show');
            if (openUserMenu) {
                openUserMenu.classList.remove('show');
                const userBtn = document.getElementById('userMenuBtn');
                if (userBtn && window.bootstrap && window.bootstrap.Dropdown) {
                    const bsDrop = window.bootstrap.Dropdown.getInstance(userBtn);
                    if (bsDrop) bsDrop.hide();
                }
            }
        } else if (!hidden && isNavHidden) {
            navEl.classList.remove('nav-scrolled-hidden');
            navEl.style.transform = 'translateY(0)';
            navEl.style.boxShadow = '';
            navEl.style.pointerEvents = '';
            isNavHidden = false;
        }
    }

    function handleNavbarScroll() {
        const currentScrollY = Math.max(0, window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0);

        // Nếu menu hoa hồng bên trái đang mở thì giữ nguyên để tiện thao tác
        if (typeof isOpen !== 'undefined' && isOpen) {
            setNavbarVisibility(false);
            lastScrollY = currentScrollY;
            return;
        }

        // Sát đỉnh trang (<= 20px) luôn hiển thị thanh điều hướng
        if (currentScrollY <= 20) {
            setNavbarVisibility(false);
            lastScrollY = currentScrollY;
            return;
        }

        // Chặn hiệu ứng nảy rubber-band ở đáy trang
        const maxScroll = (document.documentElement.scrollHeight || document.body.scrollHeight) - window.innerHeight;
        if (maxScroll > 0 && currentScrollY >= maxScroll - 15) {
            lastScrollY = currentScrollY;
            return;
        }

        const diff = currentScrollY - lastScrollY;

        // Bỏ qua chuyển động vi mô
        if (Math.abs(diff) < SCROLL_DELTA) {
            return;
        }

        if (diff > 0 && currentScrollY > SCROLL_MIN_OFFSET) {
            // LƯỚT XUỐNG: Thu lên trên
            setNavbarVisibility(true);
        } else if (diff < 0) {
            // LƯỚT LÊN: Trượt xuống dưới
            setNavbarVisibility(false);
        }

        lastScrollY = currentScrollY;
    }

    window.addEventListener('scroll', () => {
        if (!navScrollTicking) {
            window.requestAnimationFrame(() => {
                handleNavbarScroll();
                navScrollTicking = false;
            });
            navScrollTicking = true;
        }
    }, { passive: true });
})();

// Nút tròn nổi cuộn lên đầu trang (Back to top) với requestAnimationFrame throttling
const backToTopBtn = document.getElementById('backToTopBtn');
if (backToTopBtn) {
    let scrollTicking = false;
    window.addEventListener('scroll', () => {
        if (!scrollTicking) {
            window.requestAnimationFrame(() => {
                if (window.scrollY > 280) {
                    backToTopBtn.classList.add('visible');
                } else {
                    backToTopBtn.classList.remove('visible');
                }
                scrollTicking = false;
            });
            scrollTicking = true;
        }
    }, { passive: true });

    backToTopBtn.addEventListener('click', () => {
        const navEl = document.querySelector('.shop-navbar');
        if (navEl) navEl.classList.remove('nav-scrolled-hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// Xử lý đóng mở menu avatar cá nhân an toàn (dự phòng khi offline CDN)
const userMenuBtn = document.getElementById('userMenuBtn');
const userMenu = document.querySelector('.user-popover-menu');
if (userMenuBtn && userMenu) {
    userMenuBtn.addEventListener('click', (e) => {
        if (typeof bootstrap === 'undefined') {
            e.stopPropagation();
            userMenu.classList.toggle('show');
        }
    });
    document.addEventListener('click', (e) => {
        if (typeof bootstrap === 'undefined' && !userMenu.contains(e.target) && !userMenuBtn.contains(e.target)) {
            userMenu.classList.remove('show');
        }
    });
}

// =======================================================
// BỘ ĐIỀU KHIỂN CHAT VỚI SHOP (FLOATING LIVE CHAT)
// =======================================================
(function () {
    const chatToggleBtn = document.getElementById('chatToggleBtn');
    const chatWindow = document.getElementById('chatWindow');
    const closeChatBtn = document.getElementById('closeChatBtn');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatSendBtn = document.getElementById('chatSendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const chatSuggestions = document.getElementById('chatSuggestions');
    const chatScrollBottomBtn = document.getElementById('chatScrollBottomBtn');
    const chatFloatingToast = document.getElementById('chatFloatingToast');
    const chatNetworkStatus = document.getElementById('chatNetworkStatus');
    const chatIconOpen = chatToggleBtn ? chatToggleBtn.querySelector('.chat-icon-open') : null;
    const chatIconClose = chatToggleBtn ? chatToggleBtn.querySelector('.chat-icon-close') : null;

    if (!chatToggleBtn || !chatWindow || !chatMessages) return;

    const STORAGE_PREFIX = 'lego_flower_chat_history_';
    const STATE_KEY = 'lego_flower_chat_open';
    const customerUnreadBadge = document.getElementById('chatCustomerUnreadBadge');

    let isOpen = false;
    let unreadAdminCount = 0;
    let lastLoadedMsgId = 0;
    let toastTimer = null;

    // Âm thanh thông báo tin nhắn từ shop (Web Audio API)
    function playCustomerChime() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
            osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.08); // E5
            osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.16); // G5
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        } catch (e) {}
    }

    // Bong bóng nổi xem trước tin nhắn khi chat đang đóng
    function showFloatingToast(text) {
        if (!chatFloatingToast || isOpen) return;
        const toastMsg = document.getElementById('chatToastText');
        if (toastMsg) toastMsg.textContent = text;
        chatFloatingToast.classList.remove('d-none');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            chatFloatingToast.classList.add('d-none');
        }, 6500);
    }

    if (chatFloatingToast) {
        chatFloatingToast.addEventListener('click', (e) => {
            if (e.target.closest('#chatToastCloseBtn')) {
                e.stopPropagation();
                chatFloatingToast.classList.add('d-none');
                if (toastTimer) clearTimeout(toastTimer);
                return;
            }
            chatFloatingToast.classList.add('d-none');
            if (toastTimer) clearTimeout(toastTimer);
            toggleChat(true);
        });
    }

    // Nút cuộn nhanh xuống cuối khi đọc tin cũ
    if (chatScrollBottomBtn) {
        chatMessages.addEventListener('scroll', () => {
            const distanceToBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
            if (distanceToBottom > 120) {
                chatScrollBottomBtn.classList.remove('d-none');
            } else {
                chatScrollBottomBtn.classList.add('d-none');
            }
        });
        chatScrollBottomBtn.addEventListener('click', () => {
            chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        });
    }

    // Kích hoạt nút gửi khi có nội dung
    if (chatInput && chatSendBtn) {
        chatInput.addEventListener('input', () => {
            chatSendBtn.disabled = !chatInput.value.trim();
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 96) + 'px';
        });
    }

    // ID hội thoại được ràng buộc với session đã ký ở server.
    const chatSessionId = chatWidget.dataset.chatSessionId;

    const STORAGE_KEY = STORAGE_PREFIX + chatSessionId;

    function toggleChat(state) {
        isOpen = (state !== undefined) ? state : !isOpen;
        if (isOpen) {
            chatWindow.classList.add('open');
            chatWindow.setAttribute('aria-hidden', 'false');
            if (chatIconOpen) chatIconOpen.classList.add('d-none');
            if (chatIconClose) chatIconClose.classList.remove('d-none');
            if (chatFloatingToast) chatFloatingToast.classList.add('d-none');
            if (toastTimer) clearTimeout(toastTimer);
            sessionStorage.setItem(STATE_KEY, '1');
            unreadAdminCount = 0;
            if (customerUnreadBadge) customerUnreadBadge.classList.add('d-none');
            setTimeout(() => chatInput && chatInput.focus(), 250);
            scrollChatToBottom();
        } else {
            chatWindow.classList.remove('open');
            chatWindow.setAttribute('aria-hidden', 'true');
            if (chatIconOpen) chatIconOpen.classList.remove('d-none');
            if (chatIconClose) chatIconClose.classList.add('d-none');
            sessionStorage.setItem(STATE_KEY, '0');
            chatToggleBtn.focus();
        }
    }

    chatToggleBtn.addEventListener('click', () => toggleChat());
    if (closeChatBtn) closeChatBtn.addEventListener('click', () => toggleChat(false));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && isOpen) toggleChat(false);
    });

    function scrollChatToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function getCurrentTimeStr() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    }

    function updateDeliveryState(msgDiv, state) {
        if (!msgDiv) return;
        const check = msgDiv.querySelector('.chat-check');
        if (!check) return;
        const labels = {
            pending: 'Đang gửi…',
            sent: 'Đã gửi ✓',
            read: 'Đã xem ✓✓',
            failed: 'Không gửi được'
        };
        check.className = `chat-check chat-delivery-${state}`;
        check.textContent = labels[state] || labels.sent;
    }

    function markCustomerMessagesRead(readThroughId) {
        if (!readThroughId) return;
        chatMessages.querySelectorAll('.chat-msg-user[data-message-id]').forEach(el => {
            if (Number(el.dataset.messageId) <= readThroughId) updateDeliveryState(el, 'read');
        });
    }

    function renderMessageElement(text, isUser = false, timeStr = null, showTime = true,
        isGrouped = false, messageId = null, isRead = false, deliveryState = 'sent') {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-msg ${isUser ? 'chat-msg-user' : 'chat-msg-bot'}${isGrouped ? ' chat-msg-grouped' : ''}`;
        if (messageId) msgDiv.dataset.messageId = messageId;

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = text;
        msgDiv.appendChild(bubble);

        if (showTime) {
            const time = document.createElement('span');
            time.className = 'chat-time';
            const timeText = timeStr || getCurrentTimeStr();
            time.appendChild(document.createTextNode(timeText));
            if (isUser) {
                time.appendChild(document.createTextNode(' · '));
                const delivery = document.createElement('span');
                delivery.className = 'chat-check';
                time.appendChild(delivery);
            }
            msgDiv.appendChild(time);
        }

        chatMessages.appendChild(msgDiv);
        if (isUser) updateDeliveryState(msgDiv, isRead ? 'read' : deliveryState);
        return msgDiv;
    }

    function appendLiveMessage(text, isUser = false, customTime = null, messageId = null,
        isRead = false, deliveryState = 'sent') {
        const currentTime = customTime || getCurrentTimeStr();
        const targetSenderClass = isUser ? 'chat-msg-user' : 'chat-msg-bot';

        // Tìm tin nhắn gần nhất hiện có (bỏ qua typing indicator hoặc suggestions)
        const allMsgElements = chatMessages.querySelectorAll('.chat-msg:not(.chat-typing)');
        const prevMsgElement = allMsgElements.length > 0 ? allMsgElements[allMsgElements.length - 1] : null;

        if (prevMsgElement && prevMsgElement.classList.contains(targetSenderClass)) {
            // Cùng một người gửi tin liền mạch: ẩn timestamp của tin nhắn trước và thu gọn khoảng cách
            const prevTimeEl = prevMsgElement.querySelector('.chat-time');
            if (prevTimeEl) {
                if (prevTimeEl.textContent === currentTime) {
                    prevTimeEl.remove();
                    prevMsgElement.classList.add('chat-msg-grouped');
                }
            }
        }

        const element = renderMessageElement(
            text, isUser, currentTime, true, false, messageId, isRead, deliveryState
        );
        saveMessageToHistory(text, isUser, currentTime);
        scrollChatToBottom();
        return element;
    }

    function saveMessageToHistory(text, isUser, timeStr) {
        try {
            let history = [];
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) history = parsed;
            }
            history.push({
                sender: isUser ? 'user' : 'bot',
                text: text,
                time: timeStr || getCurrentTimeStr()
            });
            localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
        } catch (e) { }
    }

    // Gửi tin nhắn lên máy chủ (để Admin nhận được)
    async function sendToServer(text, messageElement) {
        updateDeliveryState(messageElement, 'pending');
        if (chatNetworkStatus) chatNetworkStatus.classList.add('d-none');
        try {
            const res = await fetch('/api/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Không thể gửi tin nhắn.');
            if (data.message && data.message.id) {
                lastLoadedMsgId = Math.max(lastLoadedMsgId, data.message.id);
                messageElement.dataset.messageId = data.message.id;
            }
            updateDeliveryState(messageElement, 'sent');
            return true;
        } catch (err) {
            updateDeliveryState(messageElement, 'failed');
            if (chatNetworkStatus) {
                chatNetworkStatus.textContent = 'Tin nhắn chưa được gửi. Kiểm tra kết nối rồi thử lại.';
                chatNetworkStatus.classList.remove('d-none');
            }
            const check = messageElement.querySelector('.chat-check');
            if (check) {
                check.textContent = '';
                const retry = document.createElement('button');
                retry.type = 'button';
                retry.className = 'chat-retry-btn';
                retry.textContent = 'Gửi lại';
                retry.addEventListener('click', () => sendToServer(text, messageElement), { once: true });
                check.appendChild(retry);
            }
            return false;
        }
    }

    // Kiểm tra tin nhắn mới từ Admin - Adaptive backoff polling:
    // Khi chat đang hoạt động (vừa gửi/nhận tin): poll nhanh mỗi 3.5s
    // Khi không có tin mới: poll ngày càng chậm lại (tối đa 18s) để tiết kiệm requests
    let _pollTimer = null;
    let _pollDelay = 3500;
    let _pollIdleCount = 0;
    const POLL_MIN = 3500;
    const POLL_MAX = 18000;

    function schedulePoll() {
        if (_pollTimer) clearTimeout(_pollTimer);
        _pollTimer = setTimeout(adaptivePoll, _pollDelay);
    }

    async function adaptivePoll() {
        try {
            const res = await fetch(`/api/chat/messages?after_id=${lastLoadedMsgId}`);
            if (!res.ok) { schedulePoll(); return; }
            const data = await res.json();
            const msgs = data.messages || [];
            markCustomerMessagesRead(data.customer_read_through_id || 0);
            if (msgs.length > 0) {
                _pollIdleCount = 0;
                _pollDelay = POLL_MIN;
                let hasNewAdminMsg = false;
                let lastAdminText = '';
                msgs.forEach(msg => {
                    lastLoadedMsgId = Math.max(lastLoadedMsgId, msg.id);
                    if (msg.sender_type === 'admin') {
                        appendLiveMessage(msg.message, false, msg.time_str, msg.id, msg.is_read);
                        hasNewAdminMsg = true;
                        lastAdminText = msg.message;
                        if (!isOpen) {
                            unreadAdminCount++;
                            if (customerUnreadBadge) {
                                customerUnreadBadge.textContent = unreadAdminCount;
                                customerUnreadBadge.classList.remove('d-none');
                            }
                        }
                    }
                });
                if (hasNewAdminMsg) {
                    playCustomerChime();
                    if (!isOpen && lastAdminText) {
                        showFloatingToast(lastAdminText);
                    }
                }
            } else {
                _pollIdleCount++;
                // Tăng dần thời gian chờ sau mỗi lần idle, tối đa POLL_MAX
                _pollDelay = Math.min(_pollDelay * 1.25, POLL_MAX);
            }
        } catch (e) {
            _pollDelay = Math.min(_pollDelay * 1.5, POLL_MAX);
        }
        schedulePoll();
    }

    function pollAdminMessages() { adaptivePoll(); }

    async function loadChatHistory() {
        // Ưu tiên tải tin nhắn từ server trước
        try {
            const res = await fetch('/api/chat/messages');
            if (res.ok) {
                const data = await res.json();
                const msgs = data.messages || [];
                if (msgs.length > 0) {
                    chatMessages.innerHTML = '';
                    msgs.forEach((item, index) => {
                        lastLoadedMsgId = Math.max(lastLoadedMsgId, item.id);
                        const next = msgs[index + 1];
                        const isConsecutive = next && (next.sender_type === item.sender_type) && (next.time_str === item.time_str);
                        renderMessageElement(
                            item.message, item.sender_type === 'customer', item.time_str,
                            !isConsecutive, isConsecutive, item.id, item.is_read
                        );
                    });
                    markCustomerMessagesRead(data.customer_read_through_id || 0);
                    if (chatSuggestions) chatSuggestions.style.display = 'none';
                    scrollChatToBottom();
                    return;
                }
            }
        } catch (e) { }

        // Nếu server chưa có (phiên mới), đọc từ localStorage
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const history = JSON.parse(raw);
                if (Array.isArray(history) && history.length > 0) {
                    chatMessages.innerHTML = '';
                    history.forEach((item, index) => {
                        const next = history[index + 1];
                        const isConsecutiveWithNext = next && (next.sender === item.sender) && (next.time === item.time);
                        renderMessageElement(item.text, item.sender === 'user', item.time, !isConsecutiveWithNext, isConsecutiveWithNext);
                    });
                    if (history.length > 1) {
                        if (chatSuggestions) chatSuggestions.style.display = 'none';
                    } else {
                        if (chatSuggestions) {
                            chatSuggestions.style.display = 'flex';
                            chatMessages.appendChild(chatSuggestions);
                        }
                    }
                    scrollChatToBottom();
                    return;
                }
            }
        } catch (e) { }

        resetToWelcome();
    }

    function resetToWelcome() {
        const welcomeText = 'Xin chào bạn! Hãy để lại câu hỏi, shop sẽ phản hồi ngay trong cuộc trò chuyện này.';
        const timeStr = getCurrentTimeStr();
        chatMessages.innerHTML = '';
        renderMessageElement(welcomeText, false, timeStr, true, false);
        localStorage.setItem(STORAGE_KEY, JSON.stringify([{
            sender: 'bot',
            text: welcomeText,
            time: timeStr
        }]));
        if (chatSuggestions) {
            chatSuggestions.style.display = 'flex';
            chatMessages.appendChild(chatSuggestions);
        }
        scrollChatToBottom();
    }

    // Nút làm mới / đồng bộ cuộc trò chuyện (giữ nguyên cuộc trò chuyện, không tách phiên bên admin)
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', async function (e) {
            e.stopPropagation();
            const svgIcon = clearChatBtn.querySelector('svg');
            if (svgIcon) svgIcon.classList.add('chat-icon-spin');
            clearChatBtn.disabled = true;

            try {
                // Đồng bộ lại lịch sử tin nhắn mới nhất từ server
                await loadChatHistory();
                scrollChatToBottom();
            } catch (err) {
                console.error('Lỗi khi làm mới đoạn chat:', err);
            } finally {
                setTimeout(() => {
                    if (svgIcon) svgIcon.classList.remove('chat-icon-spin');
                    clearChatBtn.disabled = false;
                }, 400);
            }
        });
    }

    function handleSend(userText, isQuickChip = false) {
        if (!userText || !userText.trim()) return;
        const text = userText.trim();

        const pendingMessage = appendLiveMessage(
            text, true, null, null, false, 'pending'
        );
        if (chatInput) {
            chatInput.value = '';
            chatInput.style.height = 'auto';
            if (chatSendBtn) chatSendBtn.disabled = true;
        }

        sendToServer(text, pendingMessage);

        if (chatSuggestions) chatSuggestions.style.display = 'none';
    }

    if (chatForm) {
        chatForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (chatInput) handleSend(chatInput.value, false);
        });
    }

    if (chatInput) {
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend(chatInput.value, false);
            }
        });
    }

    // Gợi ý câu hỏi nhanh
    if (chatSuggestions) {
        chatSuggestions.querySelectorAll('.chat-chip').forEach(chip => {
            chip.addEventListener('click', function () {
                const msg = this.getAttribute('data-msg');
                if (msg) handleSend(msg, true);
            });
        });
    }

    // Khởi tạo lịch sử chat & kích hoạt kiểm tra tin nhắn mới từ Admin
    loadChatHistory();
    schedulePoll();

    // Khôi phục trạng thái mở chat từ sessionStorage nếu trước đó đang mở
    if (sessionStorage.getItem(STATE_KEY) === '1') {
        toggleChat(true);
    }
})();


// Global Cart Toast Trigger
window.showCartToast = function (data) {
    if (!data) return;
    const toastEl = document.getElementById('cartToast');
    const toastTitle = document.getElementById('cartToastTitle');
    const toastPrice = document.getElementById('cartToastPrice');
    const toastImg = document.getElementById('cartToastImg');
    const navBadge = document.getElementById('navCartBadge');

    if (toastTitle) toastTitle.textContent = data.product_name || 'Đã thêm sản phẩm';
    if (toastPrice) toastPrice.textContent = data.product_price_str || '';
    if (toastImg) {
        const imgSrc = data.thumbnail || data.product_image;
        if (imgSrc) {
            toastImg.src = imgSrc;
            toastImg.style.display = 'block';
        } else {
            toastImg.style.display = 'none';
        }
    }
    if (navBadge && data.cart_count !== undefined) {
        navBadge.textContent = data.cart_count;
        if (data.cart_count > 0) navBadge.classList.remove('d-none');
        else navBadge.classList.add('d-none');
    }

    if (toastEl && window.bootstrap && window.bootstrap.Toast) {
        const bsToast = window.bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 4500 });
        bsToast.show();
    }
};
