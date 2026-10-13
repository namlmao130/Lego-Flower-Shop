/* Shared image selection and rendering for customer and admin chat. */
window.ChatImages = (() => {
    const maxBytes = 5 * 1024 * 1024;
    let viewer;

    function openViewer(url, trigger) {
        if (!viewer) {
            const dialog = document.createElement('dialog');
            dialog.className = 'chat-image-viewer';
            dialog.setAttribute('aria-label', 'Xem ảnh chat phóng to');
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'chat-image-viewer-close';
            close.textContent = '×';
            close.setAttribute('aria-label', 'Đóng ảnh phóng to');
            const image = document.createElement('img');
            image.alt = 'Ảnh chat phóng to';
            const status = document.createElement('p');
            status.className = 'chat-image-viewer-status';
            status.setAttribute('role', 'status');
            image.addEventListener('load', () => { status.textContent = ''; });
            image.addEventListener('error', () => {
                status.textContent = 'Không tải được ảnh. Hãy đóng và mở lại để thử lại.';
            });
            close.addEventListener('click', () => dialog.close());
            dialog.addEventListener('click', event => {
                if (event.target === dialog) dialog.close();
            });
            dialog.addEventListener('keydown', event => {
                // Escape closes only the photo, leaving the chat open underneath.
                if (event.key === 'Escape') event.stopPropagation();
            });
            dialog.addEventListener('close', () => {
                document.body.classList.remove('chat-image-viewer-open');
                image.removeAttribute('src');
                if (viewer.trigger?.isConnected) viewer.trigger.focus({ preventScroll: true });
            });
            dialog.append(close, image, status);
            document.body.append(dialog);
            viewer = { dialog, image, status, close, trigger: null };
        }
        viewer.trigger = trigger;
        viewer.status.textContent = 'Đang tải ảnh…';
        viewer.image.src = url;
        viewer.dialog.showModal();
        document.body.classList.add('chat-image-viewer-open');
        viewer.close.focus({ preventScroll: true });
    }

    function picker(form, onChange, onError) {
        const input = form.querySelector('[data-chat-image-input]');
        const button = form.querySelector('[data-chat-image-button]');
        const preview = document.createElement('div');
        preview.className = 'chat-image-preview';
        preview.hidden = true;
        const image = document.createElement('img');
        image.alt = 'Ảnh chuẩn bị gửi';
        const name = document.createElement('span');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = '×';
        remove.setAttribute('aria-label', 'Bỏ ảnh đã chọn');
        preview.append(image, name, remove);
        form.before(preview);
        let file = null;
        let previewUrl = null;

        function clear() {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = null;
            file = null;
            input.value = '';
            image.removeAttribute('src');
            preview.hidden = true;
            onChange();
        }

        button.addEventListener('click', () => input.click());
        remove.addEventListener('click', clear);
        input.addEventListener('change', () => {
            const selected = input.files[0];
            clear();
            if (!selected) return;
            if (!selected.size) {
                onError('Không đọc được ảnh hoặc tệp rỗng. Vui lòng chọn lại ảnh.');
                return;
            }
            if (selected.size > maxBytes) {
                onError('Ảnh tối đa 5 MB. Vui lòng chọn ảnh nhỏ hơn.');
                return;
            }
            if (!/\.(jpe?g|png|webp|gif)$/i.test(selected.name)) {
                onError('Vui lòng chọn ảnh JPG, PNG, WEBP hoặc GIF.');
                return;
            }
            file = selected;
            previewUrl = URL.createObjectURL(file);
            image.src = previewUrl;
            name.textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
            preview.hidden = false;
            onError('');
            onChange();
        });
        return {
            get file() { return file; },
            clear,
            setDisabled(disabled) {
                input.disabled = disabled;
                button.disabled = disabled;
                remove.disabled = disabled;
            }
        };
    }

    function render(container, url) {
        const previous = container.querySelector('.chat-image-link');
        if (previous) {
            const previousUrl = previous.querySelector('img')?.getAttribute('src');
            if (previousUrl?.startsWith('blob:')) URL.revokeObjectURL(previousUrl);
            previous.remove();
        }
        if (!url) return;
        // Only accept our private endpoint or a preview generated in this browser.
        if (!/^\/api\/chat\/images\/\d+$/.test(url) && !url.startsWith('blob:')) return;
        const link = document.createElement('button');
        link.className = 'chat-image-link';
        link.type = 'button';
        link.setAttribute('aria-haspopup', 'dialog');
        link.setAttribute('aria-label', 'Mở ảnh chat kích thước lớn');
        link.addEventListener('click', () => openViewer(url, link));
        const image = document.createElement('img');
        image.src = url;
        image.alt = 'Ảnh trong cuộc trò chuyện';
        image.loading = 'lazy';
        image.addEventListener('error', () => {
            image.alt = 'Chưa tải được ảnh. Bấm để thử mở lại.';
        });
        link.append(image);
        container.append(link);
    }

    function body(message, file, sessionId) {
        const data = new FormData();
        data.append('message', message);
        if (file) data.append('image', file);
        if (sessionId) data.append('session_id', sessionId);
        return data;
    }
    return { picker, render, body };
})();
